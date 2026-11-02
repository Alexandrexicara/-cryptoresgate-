"""CryptoResgate MCP server.

Only exposes opt-in case intake and non-sensitive status for a high-entropy
case reference. Never exposes wallet-owner identity, private exchange data,
credentials, signing keys, or transaction execution.
"""
from __future__ import annotations

import os
import secrets
import string
from typing import Any

import psycopg
from mcp.server.fastmcp import FastMCP

os.environ.setdefault("FASTMCP_HOST", "0.0.0.0")
os.environ.setdefault("FASTMCP_PORT", os.environ.get("PORT", "8000"))

mcp = FastMCP(
    "CryptoResgate",
    instructions=(
        "Assist users with voluntary crypto-asset recovery case intake and "
        "status checks. Never request seed phrases, private keys, passwords, "
        "or 2FA codes. Explain that analysis is preliminary and recovery is "
        "not guaranteed. Never claim to identify wallet owners."
    ),
)


def _connect():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not configured on the server.")
    return psycopg.connect(dsn, connect_timeout=8)


@mcp.tool()
def recovery_guidance(issue_type: str, network: str = "unspecified") -> dict[str, Any]:
    """Explain safe next steps for a crypto recovery issue; no wallet scanning or transfers."""
    issue = issue_type.strip().lower()
    guidance = {
        "exchange_deposit": [
            "Contact the exchange through its official support channel.",
            "The account holder may need to open the ticket and complete identity checks.",
            "Provide transaction hash, network, asset and deposit address; never share wallet secrets.",
        ],
        "wrong_network": [
            "Do not send additional funds to test recovery.",
            "Ask the receiving platform or wallet provider whether it controls the destination and supports recovery.",
            "Recovery depends on destination control and provider policy; it is not guaranteed.",
        ],
        "lost_access": [
            "Use the wallet provider's official recovery process.",
            "Never give a seed phrase or private key to a recovery service or chatbot.",
            "A public address alone cannot prove identity or ownership.",
        ],
        "unknown": [
            "Collect the public transaction hash, network and a description of the issue.",
            "Do not share seed phrases, private keys, passwords or 2FA codes.",
            "A technical review can determine whether a legitimate recovery path may exist.",
        ],
    }
    key = issue if issue in guidance else "unknown"
    return {
        "network": network,
        "issue_type": key,
        "next_steps": guidance[key],
        "limitations": "Preliminary information only. No recovery is guaranteed; no funds are moved.",
    }


@mcp.tool()
def submit_recovery_case(
    network: str,
    transaction_hash: str,
    reported_issue: str,
    asset_contract: str = "",
    description: str = "",
    consent_to_privacy_notice: bool = False,
    consent_to_analysis: bool = False,
) -> dict[str, str]:
    """Submit a voluntary case. Requires explicit analysis consent; returns a private case reference."""
    if not consent_to_privacy_notice or not consent_to_analysis:
        return {"error": "Explicit consent_to_privacy_notice=true and consent_to_analysis=true are both required."}
    network = network.strip().lower()
    tx_hash = transaction_hash.strip()
    issue = reported_issue.strip()
    if not network or len(network) > 40 or not tx_hash or len(tx_hash) > 160 or not issue or len(issue) > 160:
        return {"error": "Invalid or missing network, transaction hash, or issue description."}
    if len(description) > 3000 or len(asset_contract) > 160:
        return {"error": "Description or asset contract exceeds the allowed length."}
    alphabet = string.ascii_uppercase + string.digits
    case_ref = "CR-" + "".join(secrets.choice(alphabet) for _ in range(32))
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cases
                  (public_id, network, transaction_hash, asset_contract, reported_issue,
                   description, privacy_notice_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (case_ref, network, tx_hash, asset_contract or None, issue,
                 description or None, "2026-11-02"),
            )
            case_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO consents
                   (case_id, consent_type, document_version, accepted, accepted_at)
                   VALUES (%s, 'privacy', '2026-11-02', TRUE, now()),
                          (%s, 'analysis', '2026-11-02', TRUE, now())""",
                (case_id, case_id),
            )
            cur.execute(
                """INSERT INTO audit_events (case_id, actor_type, action, details)
                   VALUES (%s, 'mcp_client', 'case_submitted', jsonb_build_object('channel','mcp'))""",
                (case_id,),
            )
    return {
        "case_reference": case_ref,
        "status": "submitted",
        "message": "Guarde esta referência. Ela permite consultar apenas o status não sensível deste caso.",
    }


@mcp.tool()
def get_recovery_case_status(case_reference: str) -> dict[str, str]:
    """Retrieve only non-sensitive status using the secret case reference returned at intake."""
    ref = case_reference.strip().upper()
    if not ref.startswith("CR-") or len(ref) != 35:
        return {"error": "Invalid case reference."}
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, network, created_at FROM cases WHERE public_id = %s",
                (ref,),
            )
            row = cur.fetchone()
    if not row:
        return {"error": "Case not found. Check the reference."}
    return {
        "status": row[0],
        "network": row[1],
        "created_at": row[2].isoformat(),
        "privacy": "No contact details, wallet ownership claims, or private evidence are returned.",
    }


if __name__ == "__main__":
    # Configure the Render service to expose streamable HTTP on its assigned port.
    mcp.run(transport="streamable-http")
