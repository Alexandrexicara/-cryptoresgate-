import hashlib
import os
import secrets
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

from app.services.notifications import (
    CommunicationConfigurationError,
    decrypt_contact,
    encrypt_contact,
    send_transactional_email,
)

router = APIRouter(prefix="/api/v1", tags=["communications"])


class CaseUpdateNotice(BaseModel):
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=5, max_length=4000)


class ContactEnrollment(BaseModel):
    email: EmailStr
    consent_to_email: bool
    consent_version: str = Field(min_length=1, max_length=40)


def _connect():
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise HTTPException(status_code=503, detail="Banco de dados ainda não configurado.")
    return psycopg.connect(dsn, connect_timeout=8)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.post("/cases/{case_reference}/contact", status_code=202)
def enroll_contact(case_reference: str, payload: ContactEnrollment) -> dict[str, str]:
    ref = case_reference.strip().upper()
    if not ref.startswith("CR-") or len(ref) != 35:
        raise HTTPException(status_code=404, detail="Caso não encontrado.")
    if payload.consent_to_email is not True:
        raise HTTPException(status_code=400, detail="É necessário autorizar expressamente o contato por e-mail.")
    try:
        encrypted = encrypt_contact(str(payload.email))
    except CommunicationConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    token = secrets.token_urlsafe(32)
    token_hash = _hash(token)
    expires = datetime.now(timezone.utc) + timedelta(minutes=30)
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM cases WHERE public_id=%s", (ref,))
                case = cur.fetchone()
                if not case:
                    raise HTTPException(status_code=404, detail="Caso não encontrado.")
                case_id = case[0]
                cur.execute(
                    """SELECT count(*) FROM contact_preferences
                       WHERE case_id=%s AND created_at > now() - interval '1 hour'""",
                    (case_id,),
                )
                if cur.fetchone()[0] >= 3:
                    raise HTTPException(status_code=429, detail="Limite de solicitações de confirmação atingido. Tente mais tarde.")
                cur.execute(
                    """INSERT INTO contact_preferences
                       (case_id,email_ciphertext,email_lookup_hash,consent_version,
                        consent_at,verification_token_hash,verification_expires_at,created_at)
                       VALUES (%s,%s,%s,%s,now(),%s,%s,now())
                       ON CONFLICT (case_id) DO UPDATE SET
                         email_ciphertext=EXCLUDED.email_ciphertext,
                         email_lookup_hash=EXCLUDED.email_lookup_hash,
                         consent_version=EXCLUDED.consent_version,
                         consent_at=now(),
                         verification_token_hash=EXCLUDED.verification_token_hash,
                         verification_expires_at=EXCLUDED.verification_expires_at,
                         verified_at=NULL, created_at=now()""",
                    (case_id, encrypted, _hash(str(payload.email).lower()), payload.consent_version, token_hash, expires),
                )
                cur.execute(
                    """INSERT INTO consents
                       (case_id,consent_type,document_version,accepted,accepted_at)
                       VALUES (%s,'contact',%s,TRUE,now())""",
                    (case_id, payload.consent_version),
                )
                cur.execute(
                    """INSERT INTO audit_events (case_id,actor_type,action,details)
                       VALUES (%s,'user','email_verification_requested',
                         jsonb_build_object('channel','email','destination_hash',%s))""",
                    (case_id, _hash(str(payload.email).lower())),
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível registrar a preferência de contato.") from exc

    base_url = os.getenv("PUBLIC_APP_URL", "https://cryptoresgate.netlify.app").rstrip("/")
    verify_url = f"{base_url}/?verify_email={token}"
    try:
        send_transactional_email(
            str(payload.email),
            "Confirme seu e-mail — CryptoResgate",
            "Você solicitou receber atualizações do seu caso CryptoResgate. "
            "Confirme seu endereço em até 30 minutos pelo link abaixo:\n\n"
            f"{verify_url}\n\n"
            "Se você não fez esta solicitação, ignore esta mensagem. "
            "Nenhuma carteira será conectada e nenhum ativo será movimentado.",
        )
    except CommunicationConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="O provedor de e-mail não confirmou o envio.") from exc
    return {"status": "verification_sent", "message": "Enviamos um link de confirmação. O contato só será ativado após a verificação."}


@router.get("/contact/verify")
def verify_contact(token: str = Query(min_length=20, max_length=200)) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE contact_preferences cp
                       SET verified_at=now(), verification_token_hash=NULL, verification_expires_at=NULL
                       FROM cases c
                       WHERE cp.case_id=c.id AND cp.verification_token_hash=%s
                         AND cp.verification_expires_at > %s AND cp.verified_at IS NULL
                       RETURNING c.id,c.public_id,cp.email_ciphertext,cp.email_lookup_hash,cp.consent_at""",
                    (_hash(token), now),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=400, detail="Link inválido, expirado ou já utilizado.")
                case_id, case_ref, encrypted, email_hash, consent_at = row
                cur.execute(
                    """UPDATE cases SET contact_ciphertext=%s,contact_lookup_hash=%s,
                       contact_channel='email',contact_consent_at=%s,updated_at=now()
                       WHERE id=%s""",
                    (encrypted, email_hash, consent_at, case_id),
                )
                cur.execute(
                    """INSERT INTO audit_events (case_id,actor_type,action,details)
                       VALUES (%s,'user','email_verified',jsonb_build_object('channel','email'))""",
                    (case_id,),
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível confirmar o e-mail.") from exc
    return {"status": "verified", "case_reference": case_ref, "message": "E-mail confirmado. Você receberá somente atualizações relacionadas ao seu caso."}


@router.delete("/cases/{case_reference}/contact")
def revoke_contact(case_reference: str) -> dict[str, str]:
    ref = case_reference.strip().upper()
    if not ref.startswith("CR-") or len(ref) != 35:
        raise HTTPException(status_code=404, detail="Caso não encontrado.")
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM cases WHERE public_id=%s", (ref,))
                case = cur.fetchone()
                if not case:
                    raise HTTPException(status_code=404, detail="Caso não encontrado.")
                case_id = case[0]
                cur.execute("DELETE FROM contact_preferences WHERE case_id=%s", (case_id,))
                cur.execute(
                    """UPDATE cases SET contact_ciphertext=NULL,contact_lookup_hash=NULL,
                       contact_channel=NULL,contact_consent_at=NULL,updated_at=now() WHERE id=%s""",
                    (case_id,),
                )
                cur.execute(
                    """INSERT INTO consents
                       (case_id,consent_type,document_version,accepted,accepted_at)
                       VALUES (%s,'contact','revocation',FALSE,now())""",
                    (case_id,),
                )
                cur.execute(
                    """INSERT INTO audit_events (case_id,actor_type,action,details)
                       VALUES (%s,'user','email_consent_revoked',jsonb_build_object('channel','email'))""",
                    (case_id,),
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível revogar o contato.") from exc
    return {"status": "revoked", "message": "Consentimento de e-mail revogado e contato removido."}


@router.post("/cases/{case_reference}/notifications", status_code=202)
def send_case_update(
    case_reference: str,
    payload: CaseUpdateNotice,
    x_operator_key: str | None = Header(default=None),
) -> dict[str, str]:
    configured_key = os.getenv("OPERATOR_API_KEY", "")
    if not configured_key or not x_operator_key or not hmac.compare_digest(configured_key, x_operator_key):
        raise HTTPException(status_code=401, detail="Autenticação de operador inválida.")
    ref = case_reference.strip().upper()
    if not ref.startswith("CR-") or len(ref) != 35:
        raise HTTPException(status_code=404, detail="Caso não encontrado.")
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.id,c.contact_ciphertext
                       FROM cases c
                       JOIN contact_preferences cp ON cp.case_id=c.id
                       WHERE c.public_id=%s AND cp.verified_at IS NOT NULL
                         AND c.contact_consent_at IS NOT NULL""",
                    (ref,),
                )
                row = cur.fetchone()
                if not row or not row[1]:
                    raise HTTPException(status_code=409, detail="O caso não possui e-mail verificado e consentimento ativo.")
                case_id, encrypted = row
                cur.execute(
                    """SELECT count(*) FROM audit_events
                       WHERE case_id=%s AND action='case_update_email_sent'
                         AND created_at > now() - interval '24 hours'""",
                    (case_id,),
                )
                if cur.fetchone()[0] >= 5:
                    raise HTTPException(status_code=429, detail="Limite diário de notificações deste caso atingido.")
                recipient = decrypt_contact(encrypted)
                send_transactional_email(recipient, payload.subject, payload.message)
                cur.execute(
                    """INSERT INTO audit_events (case_id,actor_type,action,details)
                       VALUES (%s,'operator','case_update_email_sent',
                         jsonb_build_object('channel','email','subject',%s))""",
                    (case_id, payload.subject),
                )
    except HTTPException:
        raise
    except CommunicationConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Não foi possível enviar a atualização pelo provedor de e-mail.") from exc
    return {"status": "sent_to_provider", "message": "Atualização enviada ao provedor de e-mail para o contato verificado."}
