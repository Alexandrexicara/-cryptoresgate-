from fastapi import APIRouter, HTTPException

from app.services.bitcoin import BitcoinProviderError, inspect_bitcoin_transaction

router = APIRouter(prefix="/api/v1/public", tags=["public-blockchain-data"])


@router.get("/bitcoin/transaction/{txid}")
async def public_bitcoin_transaction(txid: str):
    try:
        return await inspect_bitcoin_transaction(txid)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BitcoinProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
