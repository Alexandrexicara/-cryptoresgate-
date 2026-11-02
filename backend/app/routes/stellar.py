from fastapi import APIRouter, HTTPException

from app.services.stellar import StellarProviderError, inspect_stellar_transaction

router = APIRouter(prefix="/api/v1/public", tags=["public-blockchain-data"])


@router.get("/stellar/transaction/{tx_hash}")
async def public_stellar_transaction(tx_hash: str):
    try:
        return await inspect_stellar_transaction(tx_hash)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StellarProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
