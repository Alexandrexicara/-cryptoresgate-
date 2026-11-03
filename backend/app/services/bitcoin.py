import re
from typing import Any

import httpx


MEMPOOL_API = "https://mempool.space/api"
_TXID_RE = re.compile(r"^[a-fA-F0-9]{64}$")


class BitcoinProviderError(RuntimeError):
    pass


def _format_btc(satoshis: int) -> str:
    """Format satoshis as an exact BTC decimal string (never a float)."""
    whole, fraction = divmod(satoshis, 100_000_000)
    fractional_text = str(fraction).rjust(8, "0").rstrip("0")
    return f"{whole}.{fractional_text}" if fractional_text else str(whole)


def _extract_outputs(tx: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = []
    for index, output in enumerate(tx.get("vout") or []):
        if not isinstance(output, dict):
            continue
        value = output.get("value")
        if not isinstance(value, int):
            continue
        outputs.append({
            "index": index,
            "address": output.get("scriptpubkey_address"),
            "value_sats": value,
            "value_btc": _format_btc(value),
        })
    return outputs


def _extract_inputs(tx: dict[str, Any]) -> list[dict[str, Any]]:
    inputs = []
    for item in tx.get("vin") or []:
        if not isinstance(item, dict):
            continue
        prevout = item.get("prevout") or {}
        value = prevout.get("value")
        inputs.append({
            "address": prevout.get("scriptpubkey_address"),
            "value_sats": value if isinstance(value, int) else None,
            "is_coinbase": bool(item.get("is_coinbase")),
        })
    return inputs


async def inspect_bitcoin_transaction(txid: str) -> dict[str, Any]:
    if not _TXID_RE.fullmatch(txid):
        raise ValueError("Informe um TXID Bitcoin válido com 64 caracteres hexadecimais.")

    timeout = httpx.Timeout(15.0, connect=7.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(f"{MEMPOOL_API}/tx/{txid}")
        except httpx.HTTPError as exc:
            raise BitcoinProviderError("Não foi possível consultar o explorador Bitcoin.") from exc

    if response.status_code == 404:
        return {
            "found": False,
            "network": "bitcoin",
            "transaction_hash": txid,
            "status": "not_found",
            "classification": "unknown",
            "recovery_candidate": False,
            "notice": "TXID não encontrado no explorador consultado. Isso não prova perda de BTC.",
        }
    if response.status_code == 429 or response.status_code >= 500:
        raise BitcoinProviderError("O explorador Bitcoin está temporariamente indisponível.")
    if response.is_error:
        raise BitcoinProviderError("O explorador Bitcoin recusou a consulta.")

    tx = response.json()
    if not isinstance(tx, dict):
        raise BitcoinProviderError("O explorador Bitcoin retornou dados inválidos.")

    status_data = tx.get("status") or {}
    confirmed = bool(status_data.get("confirmed"))
    outputs = _extract_outputs(tx)
    inputs = _extract_inputs(tx)
    is_coinbase = any(item.get("is_coinbase") for item in inputs)

    if is_coinbase:
        classification = "coinbase_mining_reward_not_user_transfer"
        status = "confirmed" if confirmed else "pending"
        notice = (
            "Esta é uma recompensa de mineração (coinbase), não uma transferência comum enviada "
            "por um usuário. Não deve ser tratada como caso de recuperação."
        )
    elif confirmed:
        classification = "confirmed_transfer_requires_recipient_verification"
        status = "confirmed"
        notice = (
            "A transação foi confirmada na rede Bitcoin. Isso comprova a inclusão dos outputs, "
            "mas não identifica o titular nem confirma crédito interno em uma exchange."
        )
    else:
        classification = "pending_confirmation"
        status = "pending"
        notice = (
            "A transação ainda não aparece confirmada em bloco. A ausência de confirmação não "
            "significa perda; acompanhe o mempool e eventuais substituições por taxa."
        )

    return {
        "found": True,
        "network": "bitcoin",
        "transaction_hash": txid,
        "status": status,
        "confirmed": confirmed,
        "block_height": status_data.get("block_height"),
        "block_time": status_data.get("block_time"),
        "fee_sats": tx.get("fee"),
        "size_bytes": tx.get("size"),
        "inputs": inputs,
        "outputs": outputs,
        "classification": classification,
        "recovery_candidate": False,
        "notice": notice,
    }
