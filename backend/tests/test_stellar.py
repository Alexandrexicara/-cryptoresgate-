import asyncio

from app.services.stellar import _memo_required, inspect_stellar_transaction


def test_stellar_memo_required_flag():
    assert _memo_required({"data": {"config.memo_required": "MQ=="}}) is True
    assert _memo_required({"data": {}}) is False
    assert _memo_required({"data": {"config.memo_required": "bm8="}}) is False


def test_stellar_hash_validation():
    try:
        asyncio.run(inspect_stellar_transaction("invalid"))
    except ValueError as exc:
        assert "64 caracteres" in str(exc)
    else:
        raise AssertionError("Hash inválido deveria ser rejeitado")
