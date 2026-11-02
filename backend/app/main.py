import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.analysis import router as analysis_router
from app.routes.cases import router as cases_router
from app.routes.blockchain import router as blockchain_router

app = FastAPI(
    title="CryptoResgate API",
    version="0.4.0",
    description="API para triagem consentida de casos de criptoativos.",
)

origins = [
    item.strip()
    for item in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(analysis_router)
app.include_router(cases_router)
app.include_router(blockchain_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "cryptoresgate-api"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "CryptoResgate",
        "status": "development",
        "version": app.version,
        "message": "API de triagem; nenhuma movimentação automática está habilitada.",
        "docs": "/docs",
    }
