import os
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.routes.analysis import router as analysis_router
from app.routes.cases import router as cases_router
from app.routes.blockchain import router as blockchain_router
from app.routes.bitcoin import router as bitcoin_router
from app.routes.communications import router as communications_router
from app.routes.stellar import router as stellar_router
from app.routes.solana import router as solana_router
from app.routes.tron import router as tron_router
from app.routes.wallet_authorization import router as wallet_authorization_router

app = FastAPI(
    title="CryptoResgate API",
    version="0.5.0",
    description="API para triagem consentida de casos de criptoativos.",
)

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "https://cryptoresgate.netlify.app",
)


def build_cors_origins(configured: str | None) -> list[str]:
    """Keep the production frontend allowed while preserving extra configured origins."""
    values = [*DEFAULT_CORS_ORIGINS, *(configured or "").split(",")]
    return list(dict.fromkeys(
        origin.strip().rstrip("/")
        for origin in values
        if origin.strip()
    ))


origins = build_cors_origins(os.getenv("CORS_ORIGINS"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Operator-Key"],
)

app.include_router(analysis_router)
app.include_router(cases_router)
app.include_router(blockchain_router)
app.include_router(bitcoin_router)
app.include_router(communications_router)
app.include_router(stellar_router)
app.include_router(solana_router)
app.include_router(tron_router)
app.include_router(wallet_authorization_router)


@app.on_event("startup")
def apply_additive_wallet_authorization_migration() -> None:
    """Apply only the idempotent, additive migration; never alter existing records."""
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        return
    migration_path = Path(__file__).resolve().parents[1] / "migrations" / "002_wallet_authorization.sql"
    if not migration_path.is_file():
        raise RuntimeError("Migration 002_wallet_authorization.sql não encontrada.")
    sql = migration_path.read_text(encoding="utf-8")
    with psycopg.connect(dsn, connect_timeout=8) as conn:
        conn.execute(sql)


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
