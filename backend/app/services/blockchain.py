import asyncio
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx


class BlockchainConfigurationError(RuntimeError):
    pass


class BlockchainProviderError(RuntimeError):
    pass


_HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")
_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
_NETWORKS = {
    "ethereum": ("ETHEREUM_RPC_URL", 1, "https://ethereum-rpc.publicnode.com"),
    "bsc": ("BSC_RPC_URL", 56, "https://bsc-rpc.publicnode.com"),
    "polygon": ("POLYGON_RPC_URL", 137, "https://polygon-bor-rpc.publicnode.com"),
    "arbitrum": ("ARBITRUM_RPC_URL", 42161, "https://arbitrum-one-rpc.publicnode.com"),
    "optimism": ("OPTIMISM_RPC_URL", 10, "https://optimism-rpc.publicnode.com"),
    "base": ("BASE_RPC_URL", 8453, "https://base-rpc.publicnode.com"),
}


def _resolve_network(requested: str | None) -> tuple[str, str, int | None]:
    configured_default = os.getenv("EVM_NETWORK", "evm").strip().lower() or "evm"
    name = (requested or configured_default).strip().lower()
    if name == "evm":
        url = os.getenv("EVM_RPC_URL", "").strip()
        expected_chain_id = None
    elif name in _NETWORKS:
        env_name, expected_chain_id, public_default = _NETWORKS[name]
        url = os.getenv(env_name, "").strip()
        if not url and (name == configured_default or (name == "ethereum" and configured_default == "evm")):
            url = os.getenv("EVM_RPC_URL", "").strip()
        if not url:
            url = public_default
    else:
        raise ValueError("Rede EVM não suportada. Use ethereum, bsc, polygon, arbitrum, optimism ou base.")
    if not url:
        raise BlockchainConfigurationError(f"Configure {name.upper()}_RPC_URL para consultar essa rede.")
    return name, url, expected_chain_id


def _quantity(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value, 16)
    except (TypeError, ValueError):
        return None


def _decode_transfer_log(log: dict[str, Any]) -> dict[str, Any] | None:
    """Decode the standard ERC-20 Transfer(address,address,uint256) event."""
    topics = log.get("topics")
    data = log.get("data")
    contract = log.get("address")
    if (
        not isinstance(topics, list)
        or len(topics) < 3
        or str(topics[0]).lower() != _TRANSFER_TOPIC
        or not isinstance(data, str)
        or not re.fullmatch(r"0x[0-9a-fA-F]{64}", data)
        or not isinstance(contract, str)
        or not _ADDRESS_RE.fullmatch(contract)
    ):
        return None
    if not all(isinstance(topic, str) and re.fullmatch(r"0x[0-9a-fA-F]{64}", topic) for topic in topics[1:3]):
        return None
    return {
        "token_contract": contract.lower(),
        "from_address": "0x" + topics[1][-40:].lower(),
        "to_address": "0x" + topics[2][-40:].lower(),
        "amount_raw": str(int(data, 16)),
    }


def _decode_abi_string(value: str) -> str | None:
    """Decode common ABI string and bytes32 symbol() responses."""
    if not isinstance(value, str) or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})+", value):
        return None
    raw = bytes.fromhex(value[2:])
    try:
        if len(raw) == 32:
            return raw.rstrip(b"\x00").decode("utf-8") or None
        if len(raw) >= 64:
            offset = int.from_bytes(raw[:32], "big")
            if offset + 32 > len(raw):
                return None
            length = int.from_bytes(raw[offset:offset + 32], "big")
            if length > 128 or offset + 32 + length > len(raw):
                return None
            return raw[offset + 32:offset + 32 + length].decode("utf-8") or None
    except (UnicodeDecodeError, ValueError):
        return None
    return None


def _format_token_amount(raw: str, decimals: int | None) -> str | None:
    if decimals is None or decimals < 0 or decimals > 255:
        return None
    try:
        amount = Decimal(raw) / (Decimal(10) ** decimals)
        return format(amount, "f")
    except (InvalidOperation, ValueError):
        return None


async def inspect_public_transaction(tx_hash: str, network: str | None = None) -> dict[str, Any]:
    """Read-only EVM lookup including standard ERC-20 Transfer receipt logs."""
    if not _HASH_RE.fullmatch(tx_hash):
        raise ValueError("Informe um hash EVM válido de 32 bytes (0x + 64 caracteres hexadecimais).")

    network_name, rpc_url, expected_chain_id = _resolve_network(network)

    timeout = httpx.Timeout(12.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def rpc(method: str, params: list[Any]) -> Any:
            try:
                response = await client.post(
                    rpc_url,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise BlockchainProviderError("Não foi possível consultar o explorador RPC configurado.") from exc
            if not isinstance(payload, dict):
                raise BlockchainProviderError("O provedor RPC retornou uma resposta inválida.")
            if payload.get("error"):
                raise BlockchainProviderError("O provedor RPC recusou a consulta.")
            return payload.get("result")

        tx, receipt = await asyncio.gather(
            rpc("eth_getTransactionByHash", [tx_hash]),
            rpc("eth_getTransactionReceipt", [tx_hash]),
        )
        chain_id_raw, latest_block = await asyncio.gather(
            rpc("eth_chainId", []),
            rpc("eth_blockNumber", []),
        )
        actual_chain_id = _quantity(chain_id_raw)
        if expected_chain_id is not None and actual_chain_id != expected_chain_id:
            raise BlockchainProviderError(
                f"O RPC configurado para {network_name} pertence a outra rede (chain ID inesperado)."
            )

        if tx is None:
            return {
                "found": False,
                "transaction_hash": tx_hash,
                "status": "not_found",
                "notice": "A transação não foi encontrada neste RPC. Isso não prova perda de ativos.",
            }
        if not isinstance(tx, dict):
            raise BlockchainProviderError("O provedor RPC retornou dados de transação inválidos.")

        status = "pending"
        if isinstance(receipt, dict):
            receipt_status = receipt.get("status")
            status = "success" if receipt_status == "0x1" else "failed" if receipt_status == "0x0" else "unknown"

        block_number = _quantity(tx.get("blockNumber"))
        latest_number = _quantity(latest_block)
        confirmations = max(0, latest_number - block_number + 1) if latest_number is not None and block_number is not None else 0

        transfers: list[dict[str, Any]] = []
        if status == "success" and isinstance(receipt, dict):
            logs = receipt.get("logs")
            if isinstance(logs, list):
                for log in logs[:1000]:
                    if isinstance(log, dict):
                        transfer = _decode_transfer_log(log)
                        if transfer:
                            transfers.append(transfer)

        # Token metadata is best-effort: a non-standard token must not break the
        # transaction lookup. All calls remain read-only eth_call requests.
        contracts = list(dict.fromkeys(item["token_contract"] for item in transfers))[:100]
        metadata_semaphore = asyncio.Semaphore(10)
        async def token_metadata(contract: str) -> tuple[str, dict[str, Any]]:
            async with metadata_semaphore:
                symbol_result, decimals_result = await asyncio.gather(
                    rpc("eth_call", [{"to": contract, "data": "0x95d89b41"}, "latest"]),
                    rpc("eth_call", [{"to": contract, "data": "0x313ce567"}, "latest"]),
                    return_exceptions=True,
                )
            symbol = _decode_abi_string(symbol_result) if isinstance(symbol_result, str) else None
            decimals_raw = _quantity(decimals_result) if isinstance(decimals_result, str) else None
            decimals = decimals_raw if decimals_raw is not None and 0 <= decimals_raw <= 255 else None
            return contract, {"symbol": symbol, "decimals": decimals}

        metadata_results = await asyncio.gather(*(token_metadata(contract) for contract in contracts))
        metadata = dict(metadata_results)
        for transfer in transfers:
            token = metadata.get(transfer["token_contract"], {})
            transfer.update(token)
            transfer["amount"] = _format_token_amount(transfer["amount_raw"], token.get("decimals"))

    return {
        "found": True,
        "transaction_hash": tx_hash,
        "network": network_name,
        "status": status,
        "block_number": block_number,
        "confirmations": confirmations,
        "from_address": tx.get("from"),
        "to_address": tx.get("to"),
        "value_wei": _quantity(tx.get("value")),
        "gas_used": _quantity(receipt.get("gasUsed")) if isinstance(receipt, dict) else None,
        "token_transfers": transfers,
        "token_transfer_count": len(transfers),
        "notice": "Dados públicos da blockchain. Transferências de tokens são eventos registrados no recibo; endereços não revelam identidade civil e status não garante recuperação.",
    }
