from fastapi import APIRouter, HTTPException, Query

from app.services.blockchain import (
    BlockchainConfigurationError,
    BlockchainProviderError,
    inspect_public_transaction,
)

router = APIRouter(prefix="/api/v1/public", tags=["public-blockchain-data"])


@router.get("/transaction/{tx_hash}")
async def public_transaction(
    tx_hash: str,
    network: str | None = Query(default=None, description="ethereum, bsc, polygon, arbitrum, optimism, base ou rede EVM padrão configurada"),
):
    try:
        return await inspect_public_transaction(tx_hash, network=network)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BlockchainConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BlockchainProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
