"""Wallet-control proof and explicit case-specific service authorization.

A valid EVM signature proves control of an address at signing time only. It does
not establish a person's civil identity, ownership of exchange accounts, or
authority over assets held by a third party.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/api/v1", tags=["wallet-authorization"])
SUPPORTED_CHAINS = {1, 56, 137, 42161, 10, 8453}
DEFAULT_FEE_BPS = 5000  # Existing experimental split contract is 50/50.


class WalletChallengeRequest(BaseModel):
    wallet_address: str = Field(min_length=42, max_length=42)
    chain_id: int = Field(gt=0, le=2**63 - 1)

    @field_validator("wallet_address")
    @classmethod
    def valid_address(cls, value: str) -> str:
        if not value.startswith("0x") or len(value) != 42:
            raise ValueError("Informe um endereço EVM válido.")
        try:
            int(value[2:], 16)
        except ValueError as exc:
            raise ValueError("Endereço EVM inválido.") from exc
        return value.lower()


class WalletChallengeVerify(BaseModel):
    wallet_address: str = Field(min_length=42, max_length=42)
    nonce: str = Field(min_length=32, max_length=128)
    signature: str = Field(min_length=20, max_length=200)

    @field_validator("wallet_address")
    @classmethod
    def valid_address(cls, value: str) -> str:
        if not value.startswith("0x") or len(value) != 42:
            raise ValueError("Informe um endereço EVM válido.")
        try:
            int(value[2:], 16)
        except ValueError as exc:
            raise ValueError("Endereço EVM inválido.") from exc
        return value.lower()


class ServiceAuthorization(BaseModel):
    wallet_address: str = Field(min_length=42, max_length=42)
    institution: str = Field(min_length=2, max_length=120)
    authorized_scope: list[str] = Field(min_length=1, max_length=5)
    service_fee_bps: int = Field(ge=0, le=10000)
    terms_version: str = Field(min_length=1, max_length=40)
    consent_to_represent: bool
    consent_to_fee: bool

    @field_validator("wallet_address")
    @classmethod
    def valid_address(cls, value: str) -> str:
        if not value.startswith("0x") or len(value) != 42:
            raise ValueError("Informe um endereço EVM válido.")
        try:
            int(value[2:], 16)
        except ValueError as exc:
            raise ValueError("Endereço EVM inválido.") from exc
        return value.lower()

    @field_validator("authorized_scope")
    @classmethod
    def valid_scope(cls, values: list[str]) -> list[str]:
        allowed = {"prepare_report", "prepare_exchange_request", "submit_when_institution_allows", "track_case"}
        normalized = list(dict.fromkeys(v.strip() for v in values))
        if not normalized or any(v not in allowed for v in normalized):
            raise ValueError("Escopo de autorização inválido.")
        return normalized


def _connect():
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise HTTPException(status_code=503, detail="Banco de dados ainda não configurado.")
    return psycopg.connect(dsn, connect_timeout=8)


def _case_id(cur, reference: str):
    ref = reference.strip().upper()
    if not ref.startswith("CR-") or len(ref) != 35:
        raise HTTPException(status_code=404, detail="Caso não encontrado.")
    cur.execute("SELECT id FROM cases WHERE public_id=%s", (ref,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Caso não encontrado.")
    return row[0], ref


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def recover_wallet_signer(message: str, signature: str) -> str:
    """Recover the EVM address that signed an EIP-191 personal_sign message."""
    return Account.recover_message(
        encode_defunct(text=message), signature=signature
    ).lower()


@router.post("/cases/{case_reference}/wallet/challenge", status_code=201)
def create_wallet_challenge(case_reference: str, payload: WalletChallengeRequest) -> dict[str, Any]:
    if payload.chain_id not in SUPPORTED_CHAINS:
        raise HTTPException(status_code=422, detail="Rede ainda não suportada para prova de carteira EVM.")
    nonce = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=10)
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                case_id, ref = _case_id(cur, case_reference)
                cur.execute(
                    """SELECT count(*) FROM wallet_challenges
                       WHERE case_id=%s AND created_at > now() - interval '1 hour'""",
                    (case_id,),
                )
                if cur.fetchone()[0] >= 5:
                    raise HTTPException(status_code=429, detail="Limite de provas de carteira atingido. Tente mais tarde.")
                message = (
                    "CryptoResgate — Prova de controle de carteira\n"
                    f"Caso: {ref}\nCarteira: {payload.wallet_address}\n"
                    f"Chain ID: {payload.chain_id}\nNonce: {nonce}\n"
                    f"Emitido em: {now.isoformat()}\nExpira em: {expires.isoformat()}\n\n"
                    "Assinar esta mensagem não envia uma transação e não autoriza movimentação de fundos."
                )
                cur.execute(
                    """INSERT INTO wallet_challenges
                       (case_id,wallet_address,chain_id,nonce_hash,message,expires_at)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (case_id, payload.wallet_address, payload.chain_id, _hash(nonce), message, expires),
                )
                cur.execute(
                    """INSERT INTO audit_events(case_id,actor_type,action,details)
                       VALUES (%s,'user','wallet_challenge_created',
                         jsonb_build_object('chain_id',%s,'wallet_address',%s))""",
                    (case_id, payload.chain_id, payload.wallet_address),
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível criar a prova de carteira.") from exc
    return {"status": "challenge_created", "nonce": nonce, "message": message, "expires_at": expires.isoformat()}


@router.post("/cases/{case_reference}/wallet/verify")
def verify_wallet_challenge(case_reference: str, payload: WalletChallengeVerify) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                case_id, ref = _case_id(cur, case_reference)
                cur.execute(
                    """SELECT id,chain_id,message FROM wallet_challenges
                       WHERE case_id=%s AND wallet_address=%s AND nonce_hash=%s
                         AND expires_at>%s AND verified_at IS NULL
                       ORDER BY created_at DESC LIMIT 1""",
                    (case_id, payload.wallet_address, _hash(payload.nonce), now),
                )
                challenge = cur.fetchone()
                if not challenge:
                    raise HTTPException(status_code=400, detail="Desafio inválido, expirado ou já utilizado.")
                challenge_id, chain_id, message = challenge
                try:
                    recovered = recover_wallet_signer(message, payload.signature)
                except Exception as exc:
                    raise HTTPException(status_code=400, detail="Assinatura de carteira inválida.") from exc
                if recovered != payload.wallet_address:
                    raise HTTPException(status_code=400, detail="A assinatura não corresponde à carteira informada.")
                cur.execute(
                    """UPDATE wallet_challenges SET verified_at=%s,signature=%s WHERE id=%s""",
                    (now, payload.signature, challenge_id),
                )
                cur.execute(
                    """INSERT INTO wallet_proofs
                       (case_id,wallet_address,chain_id,message_nonce_hash,signed_message,
                        signature,verified,signed_at,expires_at)
                       VALUES (%s,%s,%s,%s,%s,%s,TRUE,%s,%s)
                       RETURNING id""",
                    (case_id, payload.wallet_address, chain_id, _hash(payload.nonce),
                     message, payload.signature, now, now + timedelta(days=3650)),
                )
                proof_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO audit_events(case_id,actor_type,action,details)
                       VALUES (%s,'user','wallet_control_verified',
                         jsonb_build_object('chain_id',%s,'wallet_address',%s,'proof_id',%s))""",
                    (case_id, chain_id, payload.wallet_address, str(proof_id)),
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível verificar a assinatura da carteira.") from exc
    return {
        "status": "wallet_control_verified",
        "case_reference": ref,
        "wallet_address": payload.wallet_address,
        "chain_id": chain_id,
        "notice": "A assinatura comprova controle desta carteira, não identidade civil, titularidade de conta em exchange ou propriedade de outros ativos.",
    }


@router.post("/cases/{case_reference}/authorization", status_code=201)
def authorize_service(case_reference: str, payload: ServiceAuthorization) -> dict[str, Any]:
    if not payload.consent_to_represent or not payload.consent_to_fee:
        raise HTTPException(status_code=400, detail="É necessário aceitar separadamente a representação e a remuneração.")
    if payload.service_fee_bps != DEFAULT_FEE_BPS:
        raise HTTPException(status_code=422, detail="A remuneração configurada nesta versão é de 50%; não aceite valores diferentes.")
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                case_id, ref = _case_id(cur, case_reference)
                cur.execute(
                    """SELECT id FROM wallet_proofs
                       WHERE case_id=%s AND lower(wallet_address)=lower(%s)
                         AND verified=TRUE ORDER BY signed_at DESC LIMIT 1""",
                    (case_id, payload.wallet_address),
                )
                proof = cur.fetchone()
                if not proof:
                    raise HTTPException(status_code=409, detail="Comprove primeiro o controle da carteira vinculada ao caso.")
                proof_id = proof[0]
                cur.execute(
                    """UPDATE case_authorizations SET revoked_at=now()
                       WHERE case_id=%s AND revoked_at IS NULL""",
                    (case_id,),
                )
                cur.execute(
                    """INSERT INTO case_authorizations
                       (case_id,wallet_proof_id,institution,authorized_scope,service_fee_bps,terms_version)
                       VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (case_id, proof_id, payload.institution.strip(),
                     payload.authorized_scope, payload.service_fee_bps, payload.terms_version),
                )
                authorization_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO consents(case_id,consent_type,document_version,accepted,accepted_at)
                       VALUES (%s,'service_terms',%s,TRUE,now()),(%s,'fee_agreement',%s,TRUE,now()),
                              (%s,'data_sharing',%s,TRUE,now())""",
                    (case_id, payload.terms_version, case_id, payload.terms_version,
                     case_id, payload.terms_version),
                )
                cur.execute(
                    """INSERT INTO audit_events(case_id,actor_type,action,details)
                       VALUES (%s,'user','service_authorization_accepted',
                         jsonb_build_object('institution',%s,'fee_bps',%s,'scope',%s,'authorization_id',%s))""",
                    (case_id, payload.institution, payload.service_fee_bps,
                     payload.authorized_scope, str(authorization_id)),
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível registrar a autorização.") from exc
    return {
        "status": "authorization_recorded",
        "case_reference": ref,
        "authorization_id": str(authorization_id),
        "service_fee_percent": payload.service_fee_bps / 100,
        "client_percent": 100 - payload.service_fee_bps / 100,
        "notice": "A autorização não permite movimentar ativos nem garante que a exchange aceite representação. A remuneração só pode ser liquidada por mecanismo separado e autorizado.",
    }


@router.delete("/cases/{case_reference}/authorization")
def revoke_service_authorization(case_reference: str, wallet_address: str) -> dict[str, str]:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                case_id, _ = _case_id(cur, case_reference)
                cur.execute(
                    """UPDATE case_authorizations ca SET revoked_at=now()
                       FROM wallet_proofs wp
                       WHERE ca.wallet_proof_id=wp.id AND ca.case_id=%s
                         AND lower(wp.wallet_address)=lower(%s) AND ca.revoked_at IS NULL
                       RETURNING ca.id""",
                    (case_id, wallet_address),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Autorização ativa não encontrada.")
                cur.execute(
                    """INSERT INTO audit_events(case_id,actor_type,action,details)
                       VALUES (%s,'user','service_authorization_revoked',jsonb_build_object('authorization_id',%s))""",
                    (case_id, str(row[0])),
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível revogar a autorização.") from exc
    return {"status": "revoked", "message": "Autorização revogada. Novas ações externas ficam bloqueadas."}
