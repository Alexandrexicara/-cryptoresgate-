from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.blockchain import inspect_public_transaction, BlockchainProviderError
from app.services.bitcoin import inspect_bitcoin_transaction, BitcoinProviderError
from app.services.solana import inspect_solana_transaction, SolanaProviderError
from app.services.tron import inspect_tron_transaction, TronProviderError

router = APIRouter(prefix="/api/v1/trace", tags=["automatic-asset-tracing"])

EVM_NETWORKS = {"ethereum", "bsc", "polygon", "arbitrum", "optimism", "base"}


class TraceRequest(BaseModel):
    network: str = Field(min_length=2, max_length=30)
    transaction_hash: str = Field(min_length=8, max_length=160)
    final_destination_wallet: str | None = Field(default=None, min_length=20, max_length=128)
    asset_contract: str | None = Field(default=None, min_length=20, max_length=128)


def _normal(value: Any) -> str | None:
    return value.lower().strip() if isinstance(value, str) else None


def _extract_movements(network: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    movements: list[dict[str, Any]] = []
    if network in EVM_NETWORKS:
        sender, recipient = _normal(data.get("from_address")), _normal(data.get("to_address"))
        value = data.get("value_wei")
        if sender and recipient and value and int(value) > 0:
            movements.append({"asset": "native", "from": sender, "to": recipient, "amount_raw": str(value)})
        for transfer in data.get("token_transfers") or []:
            movements.append({
                "asset": _normal(transfer.get("token_contract")) or "token",
                "symbol": transfer.get("symbol"),
                "from": _normal(transfer.get("from_address")),
                "to": _normal(transfer.get("to_address")),
                "amount_raw": str(transfer.get("amount_raw", "")),
                "amount": transfer.get("amount"),
            })
    elif network == "bitcoin":
        for output in data.get("outputs") or []:
            if output.get("address"):
                movements.append({"asset": "BTC", "to": output["address"], "amount_raw": str(output.get("value_sats", "")), "amount": output.get("value_btc")})
    elif network == "solana":
        for transfer in data.get("native_transfers") or []:
            movements.append({"asset": "SOL", "from": transfer.get("from_address"), "to": transfer.get("to_address"), "amount_raw": str(transfer.get("amount_lamports", "")), "amount": transfer.get("amount_sol")})
        for delta in data.get("token_balance_changes") or []:
            if delta.get("direction") == "received":
                movements.append({"asset": delta.get("mint"), "to": delta.get("owner"), "amount_raw": str(delta.get("amount_raw", "")), "decimals": delta.get("decimals")})
    elif network == "tron":
        for transfer in data.get("native_transfers") or []:
            movements.append({"asset": "TRX", "from": transfer.get("from_address_hex"), "to": transfer.get("to_address_hex"), "amount_raw": str(transfer.get("amount_sun", "")), "amount": transfer.get("amount_trx")})
        for transfer in data.get("token_transfers") or []:
            movements.append({"asset": _normal(transfer.get("token_contract")) or "TRC20", "from": transfer.get("from_address_hex"), "to": transfer.get("to_address_hex"), "amount_raw": str(transfer.get("amount_raw", ""))})
    return movements


async def _inspect(network: str, tx_hash: str) -> dict[str, Any]:
    if network in EVM_NETWORKS:
        return await inspect_public_transaction(tx_hash, network=network)
    if network == "bitcoin":
        return await inspect_bitcoin_transaction(tx_hash)
    if network == "solana":
        return await inspect_solana_transaction(tx_hash)
    if network == "tron":
        return await inspect_tron_transaction(tx_hash)
    raise HTTPException(status_code=422, detail="Rede não suportada para rastreamento automático.")


@router.post("")
async def trace_transaction(request: TraceRequest):
    network = request.network.strip().lower()
    try:
        data = await _inspect(network, request.transaction_hash.strip())
    except (ValueError,) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (BlockchainProviderError, BitcoinProviderError, SolanaProviderError, TronProviderError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    status = data.get("status", "unknown")
    movements = _extract_movements(network, data)
    expected = _normal(request.final_destination_wallet)
    contract = _normal(request.asset_contract)
    if status in {"failed"}:
        classification = "transaction_failed_on_chain"
    elif status in {"pending"}:
        classification = "awaiting_confirmation"
    elif status in {"not_found"} or not data.get("found", True):
        classification = "transaction_not_found_or_not_indexed"
    elif not expected:
        classification = "movement_detected_destination_not_supplied"
    else:
        relevant = [
            movement for movement in movements
            if (not contract or movement.get("asset") == contract)
        ]
        matches = [movement for movement in relevant if _normal(movement.get("to")) == expected]
        if matches:
            classification = "destination_seen_in_transaction"
        elif relevant:
            classification = "destination_not_seen_in_submitted_transaction"
        else:
            classification = "no_supported_asset_movement_decoded"

    return {
        "network": network,
        "transaction_hash": request.transaction_hash.strip(),
        "status": status,
        "classification": classification,
        "final_destination_wallet": request.final_destination_wallet,
        "asset_contract": request.asset_contract,
        "movements": movements,
        "movement_count": len(movements),
        "transaction_evidence": data,
        "automatic": True,
        "read_only": True,
        "loss_proven": False,
        "limitations": [
            "A análise consulta a transação informada e seus movimentos registrados; não varre todas as carteiras da rede.",
            "O endereço de destino final precisa ser informado para comparar o recebimento esperado.",
            "Destino diferente, ausência de evento ou saldo atual não provam perda: podem existir roteadores, pontes, exchanges e etapas intermediárias.",
            "Este rastreador ainda não percorre automaticamente transações posteriores em múltiplos saltos nem confirma crédito interno em exchanges.",
            "Nenhuma chave privada é solicitada e nenhum ativo é movimentado."
        ]
    }
