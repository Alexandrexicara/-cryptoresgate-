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

import asyncio
from urllib.parse import quote
import httpx

@router.post("/monitor/run")
async def run_monitor(x_operator_key: str | None = Header(default=None)):
    _auth(x_operator_key)
    api_base=os.getenv("PUBLIC_API_BASE_URL","https://cryptoresgate.onrender.com").rstrip("/")
    routes={
        "bitcoin": lambda tx: f"/api/v1/public/bitcoin/transaction/{quote(tx,safe='')}",
        "stellar": lambda tx: f"/api/v1/public/stellar/transaction/{quote(tx,safe='')}",
        "solana": lambda tx: f"/api/v1/public/solana/transaction/{quote(tx,safe='')}",
        "tron": lambda tx: f"/api/v1/public/tron/transaction/{quote(tx,safe='')}",
    }
    evm={"ethereum","bsc","polygon","arbitrum","optimism","base"}
    with _db() as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,public_id,network,transaction_hash FROM cases
                       WHERE status NOT IN ('closed','ineligible')
                       ORDER BY updated_at ASC LIMIT 100""")
        cases=cur.fetchall()
    timeout=httpx.Timeout(25.0,connect=8.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async def inspect(case):
            case_id,ref,network,tx=case
            try:
                if network in evm:
                    path=f"/api/v1/public/transaction/{quote(tx,safe='')}?network={quote(network)}"
                elif network in routes:
                    path=routes[network](tx)
                else:
                    return (case_id,ref,network,{"status":"unsupported_network","network":network})
                response=await client.get(api_base+path)
                data=response.json()
                if response.status_code>=400:
                    return (case_id,ref,network,{"status":"provider_error","http_status":response.status_code,"detail":data.get("detail","Consulta indisponível")})
                return (case_id,ref,network,{"status":"checked","data":data})
            except Exception as exc:
                return (case_id,ref,network,{"status":"provider_error","detail":str(exc)[:200]})
        results=await asyncio.gather(*(inspect(c) for c in cases))
    saved=0
    with _db() as conn, conn.cursor() as cur:
        for case_id,ref,network,result in results:
            cur.execute("""INSERT INTO case_evidence(case_id,evidence_type,content,is_public)
                           VALUES (%s,'analysis',%s::jsonb,TRUE)""",(case_id,__import__("json").dumps({"source":"scheduled_public_chain_monitor","reference":ref,"network":network,**result})))
            saved+=1
        cur.execute("""INSERT INTO audit_events(actor_type,action,details)
                       VALUES ('system','scheduled_monitor_completed',%s::jsonb)""",
                    (__import__("json").dumps({"cases_checked":len(results),"records_saved":saved}),))
    return {"status":"completed","cases_checked":len(results),"evidence_records_saved":saved,
            "note":"Monitoramento somente leitura dos hashes já cadastrados; não localiza carteiras desconhecidas nem movimenta fundos."}
