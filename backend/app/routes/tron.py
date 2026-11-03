from fastapi import APIRouter, HTTPException
from app.services.tron import TronProviderError, inspect_tron_transaction

router=APIRouter(prefix="/api/v1/public",tags=["public-blockchain-data"])

@router.get("/tron/transaction/{txid}")
async def public_tron_transaction(txid: str):
    try:
        return await inspect_tron_transaction(txid)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    except TronProviderError as exc:
        raise HTTPException(status_code=502,detail=str(exc)) from exc
