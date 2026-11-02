"""Consent-based transactional email delivery for CryptoResgate."""
import os
import smtplib
from email.message import EmailMessage

from cryptography.fernet import Fernet, InvalidToken


class CommunicationConfigurationError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = os.getenv("CONTACT_ENCRYPTION_KEY", "").strip()
    if not key:
        raise CommunicationConfigurationError("CONTACT_ENCRYPTION_KEY não configurada.")
    try:
        return Fernet(key.encode("ascii"))
    except Exception as exc:
        raise CommunicationConfigurationError("CONTACT_ENCRYPTION_KEY inválida; use uma chave Fernet.") from exc


def encrypt_contact(value: str) -> str:
    return _fernet().encrypt(value.strip().encode("utf-8")).decode("ascii")


def decrypt_contact(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise CommunicationConfigurationError("Não foi possível descriptografar o contato.") from exc


def send_transactional_email(recipient: str, subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", "").strip()
    if not all((host, username, password, sender)):
        raise CommunicationConfigurationError(
            "E-mail transacional indisponível: configure SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD e SMTP_FROM."
        )
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError as exc:
        raise CommunicationConfigurationError("SMTP_PORT inválida.") from exc

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))
    if os.getenv("SMTP_USE_SSL", "false").lower() == "true":
        with smtplib.SMTP_SSL(host, port, timeout=timeout) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(message)
