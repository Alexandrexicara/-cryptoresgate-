import os
import secrets
import string
from typing import Any

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["cases"])


class CaseIntake(BaseModel):
    network: str = Field(min_length=2, max_length=40)
    transaction_hash: str = Field(min_length=8, max_length=160)
    reported_issue: str = Field(min_length=5, max_length=160)
    asset_contract: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=3000)
    privacy_notice_version: str = Field(min_length=1, max_length=40)
    consent_to_privacy_notice: bool
    consent_to_analysis: bool


def _connect():
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise HTTPException(status_code=503, detail="Banco de dados ainda não configurado.")
    return psycopg.connect(dsn, connect_timeout=8)


@router.post("/cases", status_code=201)
def submit_case(payload: CaseIntake) -> dict[str, Any]:
    if not payload.consent_to_privacy_notice or not payload.consent_to_analysis:
        raise HTTPException(status_code=400, detail="É necessário aceitar o aviso de privacidade e autorizar a análise.")
    alphabet = string.ascii_uppercase + string.digits
    case_ref = "CR-" + "".join(secrets.choice(alphabet) for _ in range(32))
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO cases
                       (public_id, network, transaction_hash, asset_contract,
                        reported_issue, description, privacy_notice_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (case_ref, payload.network.strip().lower(), payload.transaction_hash.strip(),
                     payload.asset_contract, payload.reported_issue.strip(), payload.description,
                     payload.privacy_notice_version),
                )
                case_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO consents
                       (case_id, consent_type, document_version, accepted, accepted_at)
                       VALUES (%s,'privacy',%s,TRUE,now()),(%s,'analysis',%s,TRUE,now())""",
                    (case_id, payload.privacy_notice_version, case_id, payload.privacy_notice_version),
                )
                cur.execute(
                    """INSERT INTO audit_events (case_id,actor_type,action,details)
                       VALUES (%s,'user','case_submitted',jsonb_build_object('channel','api'))""",
                    (case_id,),
                )
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Já existe um caso cadastrado para essa rede e transação.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível salvar o caso no banco.") from exc
    return {
        "case_reference": case_ref,
        "status": "submitted",
        "message": "Guarde sua referência para consultar o andamento. Nunca compartilhe seed phrase ou chave privada.",
    }


@router.get("/cases/{case_reference}")
def case_status(case_reference: str) -> dict[str, str]:
    ref = case_reference.strip().upper()
    if not ref.startswith("CR-") or len(ref) != 35:
        raise HTTPException(status_code=404, detail="Caso não encontrado.")
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, network, created_at FROM cases WHERE public_id=%s",
                    (ref,),
                )
                row = cur.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível consultar o banco.") from exc
    if not row:
        raise HTTPException(status_code=404, detail="Caso não encontrado.")
    return {"status": row[0], "network": row[1], "created_at": row[2].isoformat()}
