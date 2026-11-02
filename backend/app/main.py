from fastapi import FastAPI

app = FastAPI(
    title="CryptoResgate API",
    version="0.1.0",
    description="API inicial para triagem consentida de casos de criptoativos.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "cryptoresgate-api"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "CryptoResgate",
        "status": "development",
        "message": "A API está em desenvolvimento. Nenhuma recuperação automática está habilitada.",
    }
