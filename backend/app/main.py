from fastapi import FastAPI

from app.routes.analysis import router as analysis_router

app = FastAPI(
    title="CryptoResgate API",
    version="0.2.0",
    description="API para triagem consentida de casos de criptoativos.",
)

app.include_router(analysis_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "cryptoresgate-api"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "CryptoResgate",
        "status": "development",
        "message": "API em desenvolvimento; nenhuma movimentação automática está habilitada.",
    }
