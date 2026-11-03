import os

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
from app.routes.discovery import router as discovery_router
from app.routes.admin import router as admin_router
from app.routes.trace import router as trace_router
from app.routes.trace_cases import router as trace_cases_router
from app.routes.auto_discovery import router as auto_discovery_router

app = FastAPI(
    title="CryptoResgate API",
    version="0.4.0",
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
app.include_router(discovery_router)
app.include_router(admin_router)
app.include_router(trace_router)
app.include_router(trace_cases_router)
app.include_router(auto_discovery_router)


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

import asyncio
import httpx

_monitor_task = None

async def _scheduled_case_monitor():
    """Runs read-only monitoring while the web process is awake."""
    port=os.getenv("PORT","8000")
    base=f"http://127.0.0.1:{port}"
    key=os.getenv("OPERATOR_API_KEY","").strip()
    if not key:
        return
    await asyncio.sleep(30)
    while True:
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                await client.post(base+"/api/v1/admin/monitor/run",
                                  headers={"X-Operator-Key":key})
                await client.post(base+"/api/v1/discovery/auto-scan",
                                  headers={"X-Operator-Key":key})
        except Exception:
            # A later cycle retries; service health must not depend on monitor availability.
            pass
        await asyncio.sleep(max(300,int(os.getenv("MONITOR_INTERVAL_SECONDS","900"))))

@app.on_event("startup")
async def start_scheduled_monitor():
    global _monitor_task
    if _monitor_task is None:
        _monitor_task=asyncio.create_task(_scheduled_case_monitor())

@app.on_event("shutdown")
async def stop_scheduled_monitor():
    global _monitor_task
    if _monitor_task is not None:
        _monitor_task.cancel()
        _monitor_task=None
