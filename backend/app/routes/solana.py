from fastapi import APIRouter, HTTPException
from app.services.solana import SolanaProviderError, inspect_solana_transaction

router=APIRouter(prefix="/api/v1/public",tags=["public-blockchain-data"])

@router.get("/solana/transaction/{signature}")
async def public_solana_transaction(signature: str):
    try:
        return await inspect_solana_transaction(signature)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    except SolanaProviderError as exc:
        raise HTTPException(status_code=502,detail=str(exc)) from exc
