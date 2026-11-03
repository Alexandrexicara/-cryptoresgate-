import os
import re
from typing import Any

import httpx

DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com"
PUBLIC_RPC_FALLBACKS = (
    "https://solana-rpc.publicnode.com",
    "https://solana.drpc.org",
)


def _rpc_urls() -> tuple[str, ...]:
    configured = os.getenv("SOLANA_RPC_URL", "").strip()
    candidates = [configured or DEFAULT_RPC_URL, DEFAULT_RPC_URL, *PUBLIC_RPC_FALLBACKS]
    return tuple(dict.fromkeys(url for url in candidates if url))
_SIG_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{80,100}$")


class SolanaProviderError(RuntimeError):
    pass


def _token_deltas(meta: dict[str, Any]) -> list[dict[str, Any]]:
    balances: dict[str, dict[tuple[Any, Any, Any], tuple[int, Any]]] = {"pre": {}, "post": {}}
    for field, target in (("preTokenBalances", balances["pre"]), ("postTokenBalances", balances["post"])):
        for item in meta.get(field) or []:
            if not isinstance(item, dict):
                continue
            ui = item.get("uiTokenAmount") or {}
            key = (item.get("accountIndex"), item.get("mint"), item.get("owner"))
            try:
                target[key] = (int(ui.get("amount", "0")), ui.get("decimals"))
            except (TypeError, ValueError):
                continue
    result = []
    for key in set(balances["pre"]) | set(balances["post"]):
        old, old_decimals = balances["pre"].get(key, (0, None))
        new, new_decimals = balances["post"].get(key, (0, None))
        delta = new - old
        if not delta:
            continue
        result.append({
            "account_index": key[0], "mint": key[1], "owner": key[2],
            "amount_raw": str(abs(delta)),
            "decimals": new_decimals if new_decimals is not None else old_decimals,
            "direction": "received" if delta > 0 else "sent",
        })
    return result


def _format_sol(lamports: int) -> str:
    whole, fraction = divmod(lamports, 1_000_000_000)
    fractional = str(fraction).rjust(9, "0").rstrip("0")
    return f"{whole}.{fractional}" if fractional else str(whole)


def _instructions(transaction: dict[str, Any]) -> list[dict[str, Any]]:
    message = transaction.get("transaction", {}).get("message", {})
    meta = transaction.get("meta") or {}
    result = [ix for ix in message.get("instructions") or [] if isinstance(ix, dict)]
    for group in meta.get("innerInstructions") or []:
        result.extend(ix for ix in group.get("instructions") or [] if isinstance(ix, dict))
    return result


def _token_transfer_operations(transaction: dict[str, Any]) -> int:
    return sum(
        1 for ix in _instructions(transaction)
        if ix.get("program") in {"spl-token", "spl-token-2022"}
        and isinstance(ix.get("parsed"), dict)
        and ix["parsed"].get("type") in {"transfer", "transferChecked"}
    )


def _burn_operations(transaction: dict[str, Any]) -> int:
    return sum(
        1 for ix in _instructions(transaction)
        if ix.get("program") in {"spl-token", "spl-token-2022"}
        and isinstance(ix.get("parsed"), dict)
        and ix["parsed"].get("type") in {"burn", "burnChecked"}
    )


def _parsed_native_transfers(transaction: dict[str, Any]) -> list[dict[str, Any]]:
    transfers = []
    for ix in _instructions(transaction):
        parsed = ix.get("parsed")
        if not isinstance(parsed, dict) or parsed.get("type") not in {"transfer", "transferWithSeed"}:
            continue
        info = parsed.get("info") or {}
        lamports = info.get("lamports")
        if not isinstance(lamports, int) or lamports <= 0:
            continue
        transfers.append({
            "from_address": info.get("source"), "to_address": info.get("destination"),
            "amount_lamports": lamports, "amount_sol": _format_sol(lamports),
        })
    return transfers


async def inspect_solana_transaction(signature: str) -> dict[str, Any]:
    if not _SIG_RE.fullmatch(signature):
        raise ValueError("Informe uma assinatura Solana válida em Base58.")
    timeout = httpx.Timeout(15.0, connect=6.0)
    request_body = {
        "jsonrpc": "2.0", "id": 1, "method": "getTransaction",
        "params": [signature, {
            "encoding": "jsonParsed", "commitment": "finalized",
            "maxSupportedTransactionVersion": 0,
        }],
    }
    payload: dict[str, Any] | None = None
    last_error: Exception | None = None
    saw_not_found = False
    async with httpx.AsyncClient(timeout=timeout) as client:
        for rpc_url in _rpc_urls():
            try:
                response = await client.post(rpc_url, json=request_body)
                response.raise_for_status()
                candidate = response.json()
                if not isinstance(candidate, dict):
                    last_error = SolanaProviderError("Resposta inválida do RPC Solana.")
                    continue
                if candidate.get("error"):
                    last_error = SolanaProviderError("Um RPC Solana recusou a consulta.")
                    continue
                if candidate.get("result") is None:
                    # Some public nodes do not retain older transaction history.
                    # Check the next provider before reporting the signature absent.
                    saw_not_found = True
                    continue
                payload = candidate
                break
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                continue
    if payload is None and not saw_not_found:
        raise SolanaProviderError("Não foi possível consultar os RPCs públicos Solana.") from last_error
    tx = payload.get("result") if payload is not None else None
    if tx is None:
        return {
            "found": False, "network": "solana", "transaction_hash": signature,
            "status": "not_found", "classification": "unknown", "recovery_candidate": False,
            "notice": "Assinatura não encontrada ou ainda não disponível no RPC consultado. Isso não prova perda.",
        }
    meta = tx.get("meta") or {}
    status = "failed" if meta.get("err") is not None else "confirmed" if tx.get("slot") is not None else "pending"
    token_deltas = _token_deltas(meta)
    native_transfers = _parsed_native_transfers(tx)
    burn_count = _burn_operations(tx)
    token_transfer_count = _token_transfer_operations(tx)
    if status == "failed":
        classification = "failed_on_chain"
    elif status == "pending":
        classification = "pending_confirmation"
    elif burn_count and token_transfer_count == 0 and not native_transfers:
        classification = "confirmed_burn_destination_not_recoverable"
    elif token_deltas or native_transfers:
        classification = "confirmed_transfer_requires_recipient_verification"
    else:
        classification = "successful_transaction_no_supported_transfer_detected"
    notice = (
        "Operação de queima identificada; não classificar o ativo como perdido ou recuperável."
        if classification == "confirmed_burn_destination_not_recoverable"
        else "Consulta pública somente leitura. Alterações de saldo não provam crédito interno em exchange nem possibilidade de recuperação; movimentos não interpretados podem não aparecer nesta análise."
    )
    return {
        "found": True, "network": "solana", "transaction_hash": signature, "status": status,
        "slot": tx.get("slot"), "fee_lamports": meta.get("fee"), "error": meta.get("err"),
        "token_balance_changes": token_deltas, "native_transfers": native_transfers,
        "burn_operation_count": burn_count, "token_transfer_operation_count": token_transfer_count, "classification": classification,
        "recovery_candidate": False, "notice": notice,
    }
