import json
import os
import psycopg
from fastapi import APIRouter, HTTPException
from app.routes.trace import _inspect, _extract_movements

router = APIRouter(prefix="/api/v1/cases", tags=["case-automatic-tracing"])

def _db():
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise HTTPException(status_code=503, detail="Banco de dados não configurado.")
    return psycopg.connect(dsn, connect_timeout=8)

@router.post("/{case_reference}/trace")
async def trace_case(case_reference: str):
    ref = case_reference.strip().upper()
    if not ref.startswith("CR-") or len(ref) != 35:
        raise HTTPException(status_code=404, detail="Caso não encontrado.")
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute("SELECT id,network,transaction_hash,asset_contract,status FROM cases WHERE public_id=%s", (ref,))
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Caso não encontrado.")
        case_id, network, tx_hash, asset_contract, case_status = row
        data = await _inspect(network, tx_hash)
        movements = _extract_movements(network, data)
        result = {
            "source": "user_requested_automatic_trace",
            "network": network,
            "transaction_hash": tx_hash,
            "status": data.get("status", "unknown"),
            "classification": data.get("classification", "unknown"),
            "movements": movements,
            "movement_count": len(movements),
            "transaction_evidence": data,
            "loss_proven": False,
            "read_only": True,
        }
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO case_evidence(case_id,evidence_type,content,is_public)
                   VALUES (%s,'analysis',%s::jsonb,TRUE)""",
                (case_id, json.dumps(result)),
            )
            cur.execute(
                """INSERT INTO audit_events(case_id,actor_type,action,details)
                   VALUES (%s,'system','automatic_trace_completed',%s::jsonb)""",
                (case_id, json.dumps({"network": network, "transaction_hash": tx_hash,
                                      "movement_count": len(movements),
                                      "classification": result["classification"]})),
            )
        return {"case_reference": ref, **result,
                "message": "Rastreamento on-chain executado. A análise não movimenta fundos e não declara perda sem prova independente."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Não foi possível concluir o rastreamento automático agora.") from exc
