import base64
import re
from typing import Any

import httpx


HORIZON_URL = "https://horizon.stellar.org"
_HASH_RE = re.compile(r"^[a-fA-F0-9]{64}$")
_PAYMENT_TYPES = {"payment", "path_payment_strict_send", "path_payment_strict_receive"}


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


def _extract_payments(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract classic payments and Soroban asset balance changes from Horizon."""
    payments: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add_payment(
        operation_type: str,
        destination: str | None,
        amount: Any,
        asset_type: str | None,
        asset_code: str | None,
        asset_issuer: str | None,
        source: str | None,
    ) -> None:
        if not destination or amount is None:
            return
        code = asset_code or ("XLM" if asset_type == "native" else None)
        key = (destination, str(amount), code or "", asset_issuer or "")
        if key in seen:
            return
        seen.add(key)
        payments.append({
            "operation_type": operation_type,
            "from_address": source,
            "to_address": destination,
            "amount": str(amount),
            "asset_code": code,
            "asset_issuer": asset_issuer,
            "memo_required": False,
        })

    for op in operations:
        op_type = op.get("type") or "unknown"
        if op_type in _PAYMENT_TYPES:
            add_payment(
                op_type,
                op.get("to") or op.get("destination"),
                op.get("amount") or op.get("destination_amount") or op.get("source_amount"),
                op.get("asset_type") or op.get("destination_asset_type") or op.get("source_asset_type"),
                op.get("asset_code") or op.get("destination_asset_code") or op.get("source_asset_code"),
                op.get("asset_issuer") or op.get("destination_asset_issuer") or op.get("source_asset_issuer"),
                op.get("from") or op.get("source_account"),
            )

        # Soroban contract invocations can move assets without being a classic
        # payment operation. Horizon exposes these movements as balance changes.
        for change in op.get("asset_balance_changes") or []:
            if not isinstance(change, dict) or change.get("type") == "burn":
                continue
            add_payment(
                f"{op_type}:{change.get('type') or 'balance_change'}",
                change.get("to") or change.get("account"),
                change.get("amount"),
                change.get("asset_type"),
                change.get("asset_code"),
                change.get("asset_issuer"),
                change.get("from") or op.get("source_account"),
            )

    return payments


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
        payments = _extract_payments(operations)

        for payment in payments:
            account_response = await get_json(f"/accounts/{payment['to_address']}")
            if account_response.status_code == 200:
                payment["memo_required"] = _memo_required(account_response.json())

    successful = bool(tx.get("successful"))
    memo_type = tx.get("memo_type", "none")
    memo_present = memo_type not in {"none", None} and tx.get("memo") not in {None, ""}
    missing_required_memo = successful and not memo_present and any(p["memo_required"] for p in payments)

    if not successful:
        classification = "failed_on_chain"
    elif missing_required_memo:
        classification = "possible_uncredited_missing_memo"
    elif not payments:
        classification = "successful_transaction_no_supported_payment_detected"
    else:
        classification = "confirmed_transfer_requires_recipient_verification"

    if missing_required_memo:
        notice = (
            "Indício técnico de possível depósito não creditado por ausência de memo. "
            "A blockchain não confirma o crédito interno da exchange; o titular deve comprovar "
            "o depósito e solicitar a recuperação ao destinatário."
        )
    elif not successful:
        notice = "A transação falhou na rede. Verifique o status e o histórico da carteira de origem."
    elif not payments:
        notice = (
            "A transação foi confirmada, mas esta versão não identificou uma transferência de ativo "
            "compatível nas operações públicas. Isso não prova perda nem recebimento."
        )
    else:
        notice = (
            "Transferência confirmada. A blockchain não comprova o crédito interno da exchange "
            "nem a identidade do titular. É necessária evidência do destinatário."
        )

    return {
        "found": True,
        "network": "stellar",
        "transaction_hash": tx_hash,
        "status": "success" if successful else "failed",
        "created_at": tx.get("created_at"),
        "source_account": tx.get("source_account"),
        "memo_type": memo_type,
        "memo_present": memo_present,
        "operation_count": len(operations),
        "payments": payments,
        "classification": classification,
        "recovery_candidate": bool(missing_required_memo),
        "notice": notice,
    }
