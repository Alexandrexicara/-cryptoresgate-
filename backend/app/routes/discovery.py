import asyncio
import re
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/discovery", tags=["asset-discovery"])

NETWORKS = {
    "ethereum": ("https://ethereum-rpc.publicnode.com", 1),
    "bsc": ("https://bsc-rpc.publicnode.com", 56),
    "polygon": ("https://polygon-bor-rpc.publicnode.com", 137),
    "arbitrum": ("https://arb1.arbitrum.io/rpc", 42161),
    "optimism": ("https://optimism-rpc.publicnode.com", 10),
    "base": ("https://base-rpc.publicnode.com", 8453),
}
ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
OWNER_CALLS = {
    "owner": "0x8da5cb5b",
    "admin": "0xf851a440",
    "getOwner": "0x893d20e8",
}


class DiscoveryRequest(BaseModel):
    addresses: list[str] = Field(min_length=1, max_length=20)
    networks: list[Literal["ethereum", "bsc", "polygon", "arbitrum", "optimism", "base"]] = Field(
        default_factory=lambda: ["ethereum", "bsc", "polygon", "arbitrum", "optimism", "base"],
        min_length=1,
        max_length=6,
    )


def _hex_int(value: str) -> int:
    try:
        return int(value, 16)
    except (TypeError, ValueError):
        return 0


async def _rpc(client: httpx.AsyncClient, url: str, method: str, params: list) -> object:
    response = await client.post(
        url,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("error") or "result" not in payload:
        raise RuntimeError("RPC retornou resposta inválida.")
    return payload["result"]


async def _inspect_address(client: httpx.AsyncClient, address: str, network: str) -> dict:
    url, expected_chain_id = NETWORKS[network]
    try:
        chain_raw, balance_raw, code, block_raw = await asyncio.gather(
            _rpc(client, url, "eth_chainId", []),
            _rpc(client, url, "eth_getBalance", [address, "latest"]),
            _rpc(client, url, "eth_getCode", [address, "latest"]),
            _rpc(client, url, "eth_blockNumber", []),
        )
        chain_id = _hex_int(chain_raw) if isinstance(chain_raw, str) else 0
        if chain_id != expected_chain_id:
            raise RuntimeError("O RPC respondeu com chain ID inesperado.")
        if not isinstance(balance_raw, str) or not isinstance(code, str):
            raise RuntimeError("Resposta de saldo/código inválida.")
        is_contract = code not in ("0x", "0x0", "")
        controller_checks = {}
        if is_contract:
            calls = await asyncio.gather(*[
                _rpc(client, url, "eth_call", [{"to": address, "data": selector}, "latest"])
                for selector in OWNER_CALLS.values()
            ], return_exceptions=True)
            for (label, _), result in zip(OWNER_CALLS.items(), calls):
                if isinstance(result, str) and re.fullmatch(r"0x[0-9a-fA-F]{64}", result):
                    candidate = "0x" + result[-40:]
                    if int(candidate, 16) != 0:
                        controller_checks[label] = candidate
        wei = _hex_int(balance_raw)
        return {
            "network": network,
            "chain_id": chain_id,
            "address": address,
            "native_balance_wei": str(wei),
            "native_balance": f"{wei / 10**18:.18f}".rstrip("0").rstrip("."),
            "native_asset_unit": "ETH" if network in ("ethereum", "arbitrum", "optimism", "base") else ("BNB" if network == "bsc" else "POL"),
            "is_contract": is_contract,
            "contract_bytecode_bytes": max(0, (len(code) - 2) // 2),
            "possible_public_controllers": controller_checks,
            "block_number": _hex_int(block_raw) if isinstance(block_raw, str) else None,
            "authority_hint": (
                "contract_owner_or_admin_candidate_found"
                if controller_checks else
                "contract_requires_manual_source_and_admin_review"
                if is_contract else
                "address_key_holder_controls_signing_authority"
            ),
            "status": "inspected",
        }
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        return {
            "network": network,
            "address": address,
            "status": "provider_error",
            "error": str(exc)[:240],
        }


@router.post("/scan")
async def scan_candidates(payload: DiscoveryRequest):
    invalid = [address for address in payload.addresses if not ADDRESS_RE.fullmatch(address)]
    if invalid:
        raise HTTPException(status_code=422, detail="Todos os endereços devem ser EVM válidos (0x + 40 caracteres hexadecimais).")
    addresses = list(dict.fromkeys(address.lower() for address in payload.addresses))
    timeout = httpx.Timeout(15.0, connect=6.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        results = await asyncio.gather(*[
            _inspect_address(client, address, network)
            for address in addresses
            for network in payload.networks
        ])
    inspected = [item for item in results if item["status"] == "inspected"]
    candidates = [
        item for item in inspected
        if int(item.get("native_balance_wei", "0")) > 0 or item.get("is_contract")
    ]
    return {
        "mode": "read_only_candidate_investigation",
        "addresses_received": len(addresses),
        "networks_requested": payload.networks,
        "checks_completed": len(inspected),
        "provider_errors": len(results) - len(inspected),
        "candidate_count": len(candidates),
        "results": results,
        "candidates": candidates,
        "limitations": [
            "Esta etapa investiga somente os endereços informados; não é uma varredura global de todas as blockchains.",
            "Saldo ou inatividade não provam perda, abandono ou autorização para movimentar ativos.",
            "A leitura de owner/admin é heurística: contratos podem usar controles diferentes, multisig ou proxy.",
            "Não são consultados saldos de todos os tokens ERC-20 nesta etapa.",
            "Nenhuma chave privada é solicitada e nenhuma transação é assinada ou enviada.",
        ],
    }
