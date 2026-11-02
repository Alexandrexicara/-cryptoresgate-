from fastapi import APIRouter, HTTPException

from app.services.blockchain import (
    BlockchainConfigurationError,
    BlockchainProviderError,
    inspect_public_transaction,
)

router = APIRouter(prefix="/api/v1/public", tags=["public-blockchain-data"])


@router.get("/transaction/{tx_hash}")
async def public_transaction(tx_hash: str):
    try:
        return await inspect_public_transaction(tx_hash)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BlockchainConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BlockchainProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
