"""Incremental, read-only discovery of funded EVM addresses from public blocks.

This is a bounded scanner, not a claim that dormant balances are lost. It walks
backward from the chain tip so the first observed transfer for an address is its
latest on-chain activity once newer ranges have been scanned.
"""
import asyncio
import json
import os
from datetime import datetime, timezone

import httpx
import psycopg
from fastapi import APIRouter, Header, HTTPException

from app.routes.discovery import NETWORKS

router = APIRouter(prefix="/api/v1/discovery", tags=["asset-discovery"])

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _db():
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise HTTPException(status_code=503, detail="DATABASE_URL não configurada.")
    return psycopg.connect(dsn, connect_timeout=8)


def _authorize(key: str | None):
    expected = os.getenv("OPERATOR_API_KEY", "").strip()
    if not expected or not key or not __import__("hmac").compare_digest(key, expected):
        raise HTTPException(status_code=401, detail="Chave de operador inválida.")


async def _rpc(client: httpx.AsyncClient, url: str, method: str, params: list):
    response = await client.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    response.raise_for_status()
    payload = response.json()
    if payload.get("error") or "result" not in payload:
        raise RuntimeError(str(payload.get("error", "RPC sem resultado"))[:240])
    return payload["result"]


def _num(value):
    try:
        return int(value, 16)
    except (TypeError, ValueError):
        return 0


def _ensure_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS discovery_scan_state (
            network TEXT PRIMARY KEY,
            next_block BIGINT NOT NULL,
            tip_block BIGINT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS discovery_candidates (
            network TEXT NOT NULL,
            wallet_address TEXT NOT NULL,
            asset_symbol TEXT NOT NULL,
            native_balance_wei NUMERIC NOT NULL,
            last_seen_block BIGINT NOT NULL,
            last_seen_at TIMESTAMPTZ NOT NULL,
            classification TEXT NOT NULL,
            evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (network, wallet_address, asset_symbol)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS discovery_candidates_age_idx ON discovery_candidates(last_seen_at)")


async def _scan_network(client, network, url, chain_id, blocks_per_network):
    tip = _num(await _rpc(client, url, "eth_blockNumber", []))
    with _db() as conn, conn.cursor() as cur:
        _ensure_tables(cur)
        cur.execute("SELECT next_block FROM discovery_scan_state WHERE network=%s", (network,))
        row = cur.fetchone()
        cursor = min(row[0], tip) if row else tip
        if cursor < 0:
            return {"network": network, "status": "history_range_complete", "blocks_scanned": 0, "candidates_saved": 0}
        start = max(0, cursor - blocks_per_network + 1)

    semaphore = asyncio.Semaphore(6)
    async def get_block(number):
        async with semaphore:
            return await _rpc(client, url, "eth_getBlockByNumber", [hex(number), True])

    block_numbers = list(range(cursor, start - 1, -1))
    blocks = await asyncio.gather(*(get_block(n) for n in block_numbers), return_exceptions=True)
    latest_activity = {}
    errors = 0
    for expected_number, block in zip(block_numbers, blocks):
        if isinstance(block, Exception) or not isinstance(block, dict):
            errors += 1
            continue
        timestamp = datetime.fromtimestamp(_num(block.get("timestamp")), tz=timezone.utc)
        for tx in block.get("transactions") or []:
            if not isinstance(tx, dict):
                continue
            # Track both sides of every transaction, including outgoing activity.
            for address in (tx.get("from"), tx.get("to")):
                if not isinstance(address, str) or not address.startswith("0x"):
                    continue
                address = address.lower()
                latest_activity.setdefault(address, {
                    "block": expected_number,
                    "timestamp": timestamp.isoformat(),
                    "tx_hash": tx.get("hash"),
                    "from": (tx.get("from") or "").lower(),
                    "to": (tx.get("to") or "").lower(),
                })

    symbol = "ETH" if network in ("ethereum", "arbitrum", "optimism", "base") else ("BNB" if network == "bsc" else "POL")
    addresses = list(latest_activity.items())
    async def balance(address, activity):
        async with semaphore:
            try:
                raw = await _rpc(client, url, "eth_getBalance", [address, "latest"])
                return address, activity, _num(raw), None
            except Exception as exc:
                return address, activity, 0, str(exc)[:160]

    balances = await asyncio.gather(*(balance(a, v) for a, v in addresses))
    saved = 0
    now = datetime.now(timezone.utc)
    with _db() as conn, conn.cursor() as cur:
        _ensure_tables(cur)
        for address, activity, wei, error in balances:
            if error or wei <= 0:
                continue
            last_seen = datetime.fromisoformat(activity["timestamp"])
            age_days = max(0, (now - last_seen).days)
            classification = "dormant_candidate" if age_days >= 365 else "funded_active_or_recent"
            evidence = {
                "method": "public_evm_block_history",
                "chain_id": chain_id,
                "last_observed_transaction": activity["tx_hash"],
                "transaction_from": activity["from"],
                "transaction_to": activity["to"],
                "age_days_since_latest_observed_activity": age_days,
                "history_scan_direction": "newest_to_oldest",
                "loss_proven": False,
            }
            cur.execute("""
                INSERT INTO discovery_candidates
                    (network,wallet_address,asset_symbol,native_balance_wei,last_seen_block,last_seen_at,classification,evidence)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (network,wallet_address,asset_symbol) DO UPDATE SET
                    native_balance_wei=EXCLUDED.native_balance_wei,
                    last_seen_block=GREATEST(discovery_candidates.last_seen_block,EXCLUDED.last_seen_block),
                    last_seen_at=CASE WHEN EXCLUDED.last_seen_block > discovery_candidates.last_seen_block
                                      THEN EXCLUDED.last_seen_at ELSE discovery_candidates.last_seen_at END,
                    classification=CASE WHEN EXCLUDED.last_seen_block > discovery_candidates.last_seen_block
                                        THEN EXCLUDED.classification ELSE discovery_candidates.classification END,
                    evidence=CASE WHEN EXCLUDED.last_seen_block > discovery_candidates.last_seen_block
                                  THEN EXCLUDED.evidence ELSE discovery_candidates.evidence END,
                    updated_at=now()
            """, (network,address,symbol,str(wei),activity["block"],last_seen,classification,json.dumps(evidence)))
            saved += 1
        # Never skip a failed block range; retry the same batch next cycle.
        next_block = cursor if errors else start - 1
        cur.execute("""
            INSERT INTO discovery_scan_state(network,next_block,tip_block,updated_at)
            VALUES (%s,%s,%s,now())
            ON CONFLICT(network) DO UPDATE SET next_block=EXCLUDED.next_block,
                tip_block=EXCLUDED.tip_block,updated_at=now()
        """, (network,next_block,tip))
        cur.execute("""
            INSERT INTO audit_events(actor_type,action,details)
            VALUES ('system','automatic_discovery_batch',%s::jsonb)
        """, (json.dumps({"network":network,"from_block":cursor,"to_block":start,
                          "blocks_requested":len(block_numbers),"block_errors":errors,
                          "funded_addresses_seen":len(addresses),"candidates_saved":saved,
                          "next_block":next_block}),))
    return {"network":network,"status":"completed","chain_tip":tip,
            "blocks_scanned":len(block_numbers)-errors,"block_errors":errors,
            "funded_addresses_seen":len(addresses),"candidates_saved":saved,
            "next_block":next_block,"history_complete":next_block < 0}


@router.post("/auto-scan")
async def automatic_discovery_scan(x_operator_key: str | None = Header(default=None)):
    """Scan public EVM blocks in bounded batches; no user wallet address required."""
    _authorize(x_operator_key)
    blocks_per_network = max(1, min(250, int(os.getenv("AUTO_DISCOVERY_BLOCKS_PER_NETWORK", "20"))))
    timeout = httpx.Timeout(35.0, connect=8.0)
    results = []
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for network, (url, chain_id) in NETWORKS.items():
            try:
                results.append(await _scan_network(client, network, url, chain_id, blocks_per_network))
            except Exception as exc:
                results.append({"network":network,"status":"provider_error","error":str(exc)[:240]})
    return {
        "status":"completed",
        "mode":"incremental_public_chain_discovery",
        "user_wallet_address_required":False,
        "networks_scanned":len(results),
        "blocks_per_network_limit":blocks_per_network,
        "results":results,
        "classification_note":"dormant_candidate significa apenas saldo nativo positivo e última entrada observada há pelo menos 365 dias; não prova perda, abandono ou titularidade.",
        "read_only":True,
    }


@router.get("/candidates")
def list_discovery_candidates(limit: int = 100, x_operator_key: str | None = Header(default=None)):
    _authorize(x_operator_key)
    limit = max(1, min(500, limit))
    try:
        with _db() as conn, conn.cursor() as cur:
            _ensure_tables(cur)
            cur.execute("""
                SELECT network,wallet_address,asset_symbol,native_balance_wei,last_seen_block,
                       last_seen_at,classification,evidence,updated_at
                FROM discovery_candidates
                ORDER BY last_seen_at ASC LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            cur.execute("SELECT network,next_block,tip_block,updated_at FROM discovery_scan_state ORDER BY network")
            states = cur.fetchall()
        return {
            "count":len(rows),
            "scan_progress":[{"network":r[0],"next_block":r[1],"tip_block":r[2],"updated_at":r[3].isoformat()} for r in states],
            "candidates":[{
                "network":r[0],"wallet_address":r[1],"asset":r[2],
                "balance_wei":str(r[3]),"last_seen_block":r[4],
                "last_seen_at":r[5].isoformat(),"classification":r[6],
                "evidence":r[7],"updated_at":r[8].isoformat()
            } for r in rows],
            "warning":"Candidatos são pistas públicas para investigação; saldo e inatividade não provam perda nem autorizam movimentação."
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Falha ao consultar candidatos de descoberta.") from exc
