from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.nvidia import (
    NvidiaConfigurationError,
    explain_case,
)

router = APIRouter(prefix="/api/v1", tags=["case-analysis"])


class CaseAnalysisRequest(BaseModel):
    network: str = Field(min_length=2, max_length=80)
    transaction_hash: str = Field(min_length=8, max_length=160)
    asset_contract: str | None = Field(default=None, max_length=160)
    reported_issue: str = Field(min_length=5, max_length=1000)
    public_evidence: str | None = Field(default=None, max_length=3000)


@router.post("/analyze-case")
async def analyze_case(request: CaseAnalysisRequest) -> dict[str, str]:
    try:
        explanation = await explain_case(request.model_dump())
    except NvidiaConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        # Do not leak provider credentials or internal exception details.
        raise HTTPException(
            status_code=502,
            detail="Não foi possível concluir a análise assistida por IA.",
        ) from exc

    return {
        "analysis": explanation,
        "notice": (
            "Análise automatizada preliminar. Não comprova titularidade, "
            "não garante recuperação e exige validação humana."
        ),
    }
