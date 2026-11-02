import asyncio

import pytest

from app.services.blockchain import (
    BlockchainConfigurationError,
    _quantity,
    inspect_public_transaction,
)


def test_rejects_invalid_evm_hash():
    with pytest.raises(ValueError):
        asyncio.run(inspect_public_transaction("0x1234"))


def test_requires_rpc_configuration(monkeypatch):
    monkeypatch.delenv("EVM_RPC_URL", raising=False)
    valid_hash = "0x" + "a" * 64
    with pytest.raises(BlockchainConfigurationError):
        asyncio.run(inspect_public_transaction(valid_hash))


def test_hex_quantity_conversion():
    assert _quantity("0x10") == 16
    assert _quantity("0x0") == 0
    assert _quantity(None) is None
    assert _quantity("invalid") is None
