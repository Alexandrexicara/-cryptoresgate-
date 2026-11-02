import os

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.routes.analysis import router as analysis_router
from app.routes.cases import router as cases_router
from app.routes.blockchain import router as blockchain_router
from app.routes.communications import router as communications_router

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
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(analysis_router)
app.include_router(cases_router)
app.include_router(blockchain_router)
app.include_router(communications_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "cryptoresgate-api"}


@app.get("/ready")
def readiness() -> dict[str, str]:
    """Readiness check: confirms DB connectivity separately from process liveness."""
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise HTTPException(status_code=503, detail="DATABASE_URL ainda não foi configurada.")
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível ou inacessível.") from exc
    return {"status": "ready", "database": "connected"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "CryptoResgate",
        "status": "development",
        "version": app.version,
        "message": "API de triagem; nenhuma movimentação automática está habilitada.",
        "docs": "/docs",
    }
