import os
import re
from typing import Any

import httpx


class BlockchainConfigurationError(RuntimeError):
    pass


class BlockchainProviderError(RuntimeError):
    pass


_HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


def _quantity(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value, 16)
    except (TypeError, ValueError):
        return None


async def inspect_public_transaction(tx_hash: str) -> dict[str, Any]:
    """Read-only EVM transaction lookup. Never identifies wallet owners or signs transactions."""
    if not _HASH_RE.fullmatch(tx_hash):
        raise ValueError("Informe um hash EVM válido de 32 bytes (0x + 64 caracteres hexadecimais).")

    rpc_url = os.getenv("EVM_RPC_URL", "").strip()
    if not rpc_url:
        raise BlockchainConfigurationError("Configure EVM_RPC_URL com um endpoint RPC público somente leitura.")

    timeout = httpx.Timeout(12.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def rpc(method: str, params: list[Any]) -> Any:
            response = await client.post(
                rpc_url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise BlockchainProviderError("O provedor RPC recusou a consulta.")
            return payload.get("result")

        try:
            tx, receipt = await __import__("asyncio").gather(
                rpc("eth_getTransactionByHash", [tx_hash]),
                rpc("eth_getTransactionReceipt", [tx_hash]),
            )
            latest_block = await rpc("eth_blockNumber", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise BlockchainProviderError("Não foi possível consultar o explorador RPC configurado.") from exc

    if tx is None:
        return {"found": False, "transaction_hash": tx_hash, "status": "not_found",
                "notice": "A transação não foi encontrada neste RPC. Isso não prova perda de ativos."}

    status = "pending"
    if receipt is not None:
        status = "success" if receipt.get("status") == "0x1" else "failed"

    return {
        "found": True,
        "transaction_hash": tx_hash,
        "network": "evm",
        "status": status,
        "block_number": _quantity(tx.get("blockNumber")),
        "confirmations": max(0, (_quantity(latest_block) or 0) - (_quantity(tx.get("blockNumber")) or 0) + 1)
            if tx.get("blockNumber") else 0,
        "from_address": tx.get("from"),
        "to_address": tx.get("to"),
        "value_wei": _quantity(tx.get("value")),
        "gas_used": _quantity(receipt.get("gasUsed")) if receipt else None,
        "notice": "Dados públicos da blockchain. Endereços não revelam identidade civil; status não garante recuperação.",
    }
