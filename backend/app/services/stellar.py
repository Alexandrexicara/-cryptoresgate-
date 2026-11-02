import base64
import re
from typing import Any

import httpx


HORIZON_URL = "https://horizon.stellar.org"
_HASH_RE = re.compile(r"^[a-fA-F0-9]{64}$")


class StellarProviderError(RuntimeError):
    pass


def _memo_required(account: dict[str, Any]) -> bool:
    """SEP-29: config.memo_required is stored as a base64-encoded data value."""
    data = account.get("data") or {}
    encoded = data.get("config.memo_required")
    if not encoded:
        return False
    try:
        return base64.b64decode(encoded).decode("utf-8").strip() == "1"
    except (ValueError, UnicodeDecodeError):
        return False


async def inspect_stellar_transaction(tx_hash: str) -> dict[str, Any]:
    if not _HASH_RE.fullmatch(tx_hash):
        raise ValueError("Informe um hash Stellar válido com 64 caracteres hexadecimais.")

    timeout = httpx.Timeout(15.0, connect=7.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        async def get_json(path: str) -> httpx.Response:
            try:
                response = await client.get(f"{HORIZON_URL}{path}")
            except httpx.HTTPError as exc:
                raise StellarProviderError("Não foi possível consultar a rede Stellar.") from exc
            return response

        tx_response = await get_json(f"/transactions/{tx_hash}")
        if tx_response.status_code == 404:
            return {
                "found": False,
                "network": "stellar",
                "transaction_hash": tx_hash,
                "status": "not_found",
                "classification": "unknown",
                "notice": "Hash não encontrado na Stellar pública. Isso não prova perda de ativos.",
            }
        if tx_response.status_code == 429 or tx_response.status_code >= 500:
            raise StellarProviderError("O explorador Stellar está temporariamente indisponível.")
        if tx_response.is_error:
            raise StellarProviderError("O explorador Stellar recusou a consulta.")
        tx = tx_response.json()

        ops_response = await get_json(f"/transactions/{tx_hash}/operations?limit=200&order=asc")
        if ops_response.status_code >= 400:
            raise StellarProviderError("Não foi possível consultar as operações da transação.")
        operations = ops_response.json().get("_embedded", {}).get("records", [])

        payments = []
        for op in operations:
            if op.get("type") not in {"payment", "path_payment_strict_send", "path_payment_strict_receive"}:
                continue
            destination = op.get("to") or op.get("destination")
            if not destination:
                continue
            asset_type = op.get("asset_type") or op.get("source_asset_type")
            asset_code = op.get("asset_code") or op.get("source_asset_code") or ("XLM" if asset_type == "native" else None)
            payment = {
                "operation_type": op.get("type"),
                "from_address": op.get("from") or op.get("source_account"),
                "to_address": destination,
                "amount": op.get("amount") or op.get("source_amount"),
                "asset_code": asset_code,
                "asset_issuer": op.get("asset_issuer") or op.get("source_asset_issuer"),
                "memo_required": False,
            }
            account_response = await get_json(f"/accounts/{destination}")
            if account_response.status_code == 200:
                payment["memo_required"] = _memo_required(account_response.json())
            payments.append(payment)

    successful = bool(tx.get("successful"))
    memo_type = tx.get("memo_type", "none")
    memo_present = memo_type not in {"none", None} and tx.get("memo") not in {None, ""}
    missing_required_memo = successful and not memo_present and any(p["memo_required"] for p in payments)

    if not successful:
        classification = "failed_on_chain"
    elif missing_required_memo:
        classification = "possible_uncredited_missing_memo"
    else:
        classification = "confirmed_transfer_requires_recipient_verification"

    return {
        "found": True,
        "network": "stellar",
        "transaction_hash": tx_hash,
        "status": "success" if successful else "failed",
        "created_at": tx.get("created_at"),
        "source_account": tx.get("source_account"),
        "memo_type": memo_type,
        "memo_present": memo_present,
        "payments": payments,
        "classification": classification,
        "recovery_candidate": bool(missing_required_memo),
        "notice": (
            "Indício técnico de possível depósito não creditado por ausência de memo. "
            "A blockchain não confirma o crédito interno da exchange; o titular deve comprovar "
            "o depósito e solicitar a recuperação ao destinatário."
            if missing_required_memo else
            "Transferência confirmada ou falha on-chain. A blockchain não comprova o crédito interno "
            "da exchange nem a identidade do titular. É necessária evidência do destinatário."
        ),
    }
