import os
import hmac
import psycopg
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

def _db():
    dsn=os.getenv("DATABASE_URL","").strip()
    if not dsn:
        raise HTTPException(status_code=503, detail="Banco de dados não configurado.")
    return psycopg.connect(dsn, connect_timeout=8)

def _auth(key: str | None):
    expected=os.getenv("OPERATOR_API_KEY","").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Painel admin ainda não foi ativado: configure OPERATOR_API_KEY no Render.")
    if not key or not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=401, detail="Chave administrativa inválida.")

@router.get("/overview")
def overview(x_operator_key: str | None = Header(default=None)):
    _auth(x_operator_key)
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*), count(*) FILTER (WHERE status='submitted'), count(*) FILTER (WHERE status IN ('triage','under_review')), count(*) FILTER (WHERE status='recovered'), count(*) FILTER (WHERE status='closed') FROM cases")
            totals=cur.fetchone()
            cur.execute("""SELECT public_id,status,network,transaction_hash,reported_issue,created_at,updated_at
                           FROM cases ORDER BY created_at DESC LIMIT 200""")
            rows=cur.fetchall()
            cur.execute("""SELECT action,actor_type,details,created_at FROM audit_events
                           ORDER BY created_at DESC LIMIT 100""")
            events=cur.fetchall()
        def iso(v): return v.isoformat() if v else None
        return {
            "totals":{"cases":totals[0],"submitted":totals[1],"in_review":totals[2],"recovered":totals[3],"closed":totals[4]},
            "cases":[{"reference":r[0],"status":r[1],"network":r[2],"transaction_hash":r[3],"issue":r[4],"created_at":iso(r[5]),"updated_at":iso(r[6])} for r in rows],
            "events":[{"action":e[0],"actor":e[1],"details":e[2],"created_at":iso(e[3])} for e in events],
            "monitoring":{"mode":"dashboard_read_only","continuous_scan_enabled":False,
                          "note":"Este painel mostra os casos já cadastrados. Monitoramento contínuo ainda requer worker/agendador e fontes de dados configuradas."}
        }
    except HTTPException: raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Falha ao consultar os dados administrativos.") from exc
