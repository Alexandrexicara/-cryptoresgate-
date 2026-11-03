import os
import hmac
import psycopg
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from urllib.parse import urlparse

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class LossAssessment(BaseModel):
    proof_type: Literal["exchange_written_confirmation", "bridge_or_contract_terminal_failure", "destination_rejection_with_trace"]
    evidence_url: str = Field(min_length=12, max_length=1000)
    evidence_summary: str = Field(min_length=30, max_length=2000)
    operator_review_note: str = Field(min_length=30, max_length=2000)
    operator_verified: bool


def _valid_https_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password

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
            cur.execute("""SELECT details,created_at FROM audit_events
                           WHERE action='scheduled_monitor_completed'
                           ORDER BY created_at DESC LIMIT 1""")
            last_scan=cur.fetchone()
            cur.execute("""SELECT c.public_id, e.content, e.created_at
                           FROM case_evidence e JOIN cases c ON c.id=e.case_id
                           WHERE e.content->>'source'='operator_loss_assessment'
                             AND e.content->>'classification'='confirmed_lost'
                             AND e.content->>'operator_verified'='true'
                           ORDER BY e.created_at DESC LIMIT 500""")
            confirmed_loss_rows=cur.fetchall()
            cur.execute("""SELECT c.public_id, e.content, e.created_at
                           FROM case_evidence e JOIN cases c ON c.id=e.case_id
                           WHERE e.evidence_type='analysis'
                             AND e.content->>'source'='scheduled_verified_wallet_discovery'
                             AND e.content->>'status'='inspected'
                             AND (COALESCE((e.content->>'native_balance_wei')::numeric,0)>0
                                  OR COALESCE((e.content->>'is_contract')::boolean,FALSE)=TRUE)
                           ORDER BY e.created_at DESC LIMIT 500""")
            asset_rows=cur.fetchall()
        def iso(v): return v.isoformat() if v else None
        return {
            "totals":{"cases":totals[0],"submitted":totals[1],"in_review":totals[2],"recovered":totals[3],"closed":totals[4]},
            "cases":[{"reference":r[0],"status":r[1],"network":r[2],"transaction_hash":r[3],"issue":r[4],"created_at":iso(r[5]),"updated_at":iso(r[6])} for r in rows],
            "events":[{"action":e[0],"actor":e[1],"details":e[2],"created_at":iso(e[3])} for e in events],
            "confirmed_lost_assets":[{"case_reference":r[0],"network":r[1].get("network"),
                "transaction_hash":r[1].get("transaction_hash"),"proof_type":r[1].get("proof_type"),
                "evidence_url":r[1].get("evidence_url"),"evidence_summary":r[1].get("evidence_summary"),
                "operator_review_note":r[1].get("operator_review_note"),"verified_at":iso(r[2]),
                "classification":"confirmed_lost"} for r in confirmed_loss_rows],
            "unconfirmed_findings":[{"case_reference":r[0],"wallet_address":r[1].get("wallet_address"),
                "network":r[1].get("network"),"native_balance":r[1].get("native_balance"),
                "asset_unit":r[1].get("native_asset_unit"),"is_contract":r[1].get("is_contract"),
                "checked_at":iso(r[2]),"classification":"unconfirmed_not_listed_as_lost"} for r in asset_rows],
            "monitoring":{"mode":"scheduled_read_only","continuous_scan_enabled":True,
                          "interval_seconds":int(os.getenv("MONITOR_INTERVAL_SECONDS","900")),
                          "last_scan":({"details":last_scan[0],"created_at":iso(last_scan[1])} if last_scan else None),
                          "note":"Verificação periódica dos hashes cadastrados. Em instâncias gratuitas, o ciclo pausa quando o serviço entra em suspensão."}
        }
    except HTTPException: raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Falha ao consultar os dados administrativos.") from exc


@router.post("/cases/{case_reference}/loss-assessment")
def register_loss_assessment(case_reference: str, payload: LossAssessment,
                             x_operator_key: str | None = Header(default=None)):
    """Only an operator-reviewed external proof can place a case in confirmed-lost list."""
    _auth(x_operator_key)
    if not payload.operator_verified:
        raise HTTPException(status_code=400, detail="A confirmação exige revisão humana explícita.")
    if not _valid_https_url(payload.evidence_url):
        raise HTTPException(status_code=422, detail="A evidência precisa ser um endereço HTTPS válido.")
    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute("SELECT id,network,transaction_hash FROM cases WHERE public_id=%s",
                        (case_reference.strip().upper(),))
            case = cur.fetchone()
            if not case:
                raise HTTPException(status_code=404, detail="Caso não encontrado.")
            case_id, network, tx_hash = case
            cur.execute("""SELECT content FROM case_evidence
                           WHERE case_id=%s AND evidence_type='analysis'
                             AND content->>'source'='scheduled_public_chain_monitor'
                           ORDER BY created_at DESC LIMIT 1""", (case_id,))
            latest = cur.fetchone()
            if not latest:
                raise HTTPException(status_code=409, detail="Ainda não existe consulta on-chain registrada para este caso.")
            snapshot = latest[0]
            chain_data = snapshot.get("data") if isinstance(snapshot, dict) else None
            chain_status = chain_data.get("status") if isinstance(chain_data, dict) else None
            if chain_status not in {"success", "confirmed"}:
                raise HTTPException(status_code=409, detail="A transação não está comprovadamente confirmada na rede.")
            assessment = {
                "source": "operator_loss_assessment",
                "classification": "confirmed_lost",
                "operator_verified": True,
                "network": network,
                "transaction_hash": tx_hash,
                "proof_type": payload.proof_type,
                "evidence_url": payload.evidence_url.strip(),
                "evidence_summary": payload.evidence_summary.strip(),
                "operator_review_note": payload.operator_review_note.strip(),
            }
            cur.execute("""INSERT INTO case_evidence(case_id,evidence_type,content,is_public)
                           VALUES (%s,'other',%s::jsonb,FALSE)""",
                        (case_id, __import__("json").dumps(assessment)))
            cur.execute("""INSERT INTO audit_events(case_id,actor_type,action,details)
                           VALUES (%s,'operator','loss_assessment_confirmed',%s::jsonb)""",
                        (case_id, __import__("json").dumps({"proof_type": payload.proof_type,
                                                            "evidence_url": payload.evidence_url.strip()})))
        return {"status":"confirmed_lost","case_reference":case_reference.strip().upper(),
                "message":"Incluído na lista após confirmação on-chain e revisão humana da evidência externa."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível registrar a avaliação.") from exc

import asyncio
from urllib.parse import quote
import httpx
from app.routes.discovery import _inspect_address, NETWORKS as DISCOVERY_NETWORKS

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
        cur.execute("""SELECT wp.case_id,c.public_id,wp.wallet_address,wp.chain_id
                       FROM wallet_proofs wp JOIN cases c ON c.id=wp.case_id
                       WHERE wp.verified=TRUE AND wp.expires_at > now()
                         AND c.status NOT IN ('closed','ineligible')
                       ORDER BY wp.created_at ASC LIMIT 100""")
        verified_wallets=cur.fetchall()
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
        chain_to_network={chain_id:name for name,(url,chain_id) in DISCOVERY_NETWORKS.items()}
        async def inspect_wallet(wallet):
            case_id,ref,address,chain_id=wallet
            network=chain_to_network.get(chain_id)
            if not network:
                return (case_id,ref,address,chain_id,None,{"status":"unsupported_chain_id"})
            data=await _inspect_address(client,address,network)
            return (case_id,ref,address,chain_id,network,data)
        wallet_results=await asyncio.gather(*(inspect_wallet(w) for w in verified_wallets),return_exceptions=False)
    saved=0
    wallet_saved=0
    with _db() as conn, conn.cursor() as cur:
        for case_id,ref,network,result in results:
            cur.execute("""INSERT INTO case_evidence(case_id,evidence_type,content,is_public)
                           VALUES (%s,'analysis',%s::jsonb,TRUE)""",(case_id,__import__("json").dumps({"source":"scheduled_public_chain_monitor","reference":ref,"network":network,**result})))
            saved+=1
        for case_id,ref,address,chain_id,network,result in wallet_results:
            content={"source":"scheduled_verified_wallet_discovery","reference":ref,
                     "wallet_address":address,"chain_id":chain_id,"network":network,**result}
            cur.execute("""SELECT 1 FROM case_evidence
                           WHERE case_id=%s AND evidence_type='analysis'
                             AND content=%s::jsonb LIMIT 1""",
                        (case_id,__import__("json").dumps(content)))
            if cur.fetchone():
                continue
            cur.execute("""INSERT INTO case_evidence(case_id,evidence_type,content,is_public)
                           VALUES (%s,'analysis',%s::jsonb,FALSE)""",
                        (case_id,__import__("json").dumps(content)))
            wallet_saved+=1
        cur.execute("""INSERT INTO audit_events(actor_type,action,details)
                       VALUES ('system','scheduled_monitor_completed',%s::jsonb)""",
                    (__import__("json").dumps({"cases_checked":len(results),"records_saved":saved,
                                               "verified_wallets_checked":len(wallet_results),
                                               "wallet_evidence_saved":wallet_saved}),))
    return {"status":"completed","cases_checked":len(results),"evidence_records_saved":saved,
            "verified_wallets_checked":len(wallet_results),"wallet_evidence_saved":wallet_saved,
            "note":"Monitoramento somente leitura dos hashes e dos endereços com comprovação verificada; não localiza carteiras desconhecidas nem movimenta fundos."}
