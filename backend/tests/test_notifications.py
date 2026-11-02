import os
import pytest
from cryptography.fernet import Fernet

from app.services.notifications import (
    CommunicationConfigurationError,
    decrypt_contact,
    encrypt_contact,
    send_transactional_email,
)


def test_contact_encryption_round_trip(monkeypatch):
    monkeypatch.setenv("CONTACT_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    encrypted = encrypt_contact("titular@example.com")
    assert encrypted != "titular@example.com"
    assert decrypt_contact(encrypted) == "titular@example.com"


def test_encryption_requires_key(monkeypatch):
    monkeypatch.delenv("CONTACT_ENCRYPTION_KEY", raising=False)
    with pytest.raises(CommunicationConfigurationError):
        encrypt_contact("titular@example.com")


def test_email_requires_smtp_configuration(monkeypatch):
    for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(CommunicationConfigurationError):
        send_transactional_email("titular@example.com", "Assunto", "Corpo")
