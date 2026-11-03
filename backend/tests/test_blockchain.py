import asyncio

import pytest

from app.services.blockchain import (
    BlockchainConfigurationError,
    _decode_abi_string,
    _decode_transfer_log,
    _format_token_amount,
    _quantity,
    _resolve_network,
    inspect_public_transaction,
)


TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def test_rejects_invalid_evm_hash():
    with pytest.raises(ValueError):
        asyncio.run(inspect_public_transaction("0x1234"))


def test_requires_rpc_configuration(monkeypatch):
    monkeypatch.delenv("EVM_RPC_URL", raising=False)
    monkeypatch.setenv("EVM_NETWORK", "evm")
    valid_hash = "0x" + "a" * 64
    with pytest.raises(BlockchainConfigurationError):
        asyncio.run(inspect_public_transaction(valid_hash))


def test_resolves_supported_network_and_expected_chain_id(monkeypatch):
    monkeypatch.setenv("BSC_RPC_URL", "https://rpc.example")
    assert _resolve_network("bsc") == ("bsc", "https://rpc.example", 56)
    with pytest.raises(ValueError):
        _resolve_network("unknown-chain")


def test_uses_public_rpc_default_when_no_override_is_set(monkeypatch):
    monkeypatch.delenv("POLYGON_RPC_URL", raising=False)
    name, url, chain_id = _resolve_network("polygon")
    assert name == "polygon"
    assert url == "https://polygon-bor-rpc.publicnode.com"
    assert chain_id == 137


def test_hex_quantity_conversion():
    assert _quantity("0x10") == 16
    assert _quantity("0x0") == 0
    assert _quantity(None) is None
    assert _quantity("invalid") is None


def test_decodes_standard_erc20_transfer_event():
    sender = "1" * 40
    recipient = "2" * 40
    contract = "0x" + "a" * 40
    event = {
        "address": contract,
        "topics": [TRANSFER_TOPIC, "0x" + "0" * 24 + sender, "0x" + "0" * 24 + recipient],
        "data": "0x" + format(1234500, "064x"),
    }
    decoded = _decode_transfer_log(event)
    assert decoded == {
        "token_contract": contract,
        "from_address": "0x" + sender,
        "to_address": "0x" + recipient,
        "amount_raw": "1234500",
    }


def test_ignores_non_transfer_or_malformed_logs():
    assert _decode_transfer_log({"topics": [], "data": "0x0"}) is None
    assert _decode_transfer_log({
        "address": "0x" + "a" * 40,
        "topics": ["0x" + "0" * 64],
        "data": "0x" + "0" * 64,
    }) is None


def test_decodes_abi_symbol_and_formats_token_amount():
    assert _decode_abi_string("0x" + "5553444300000000000000000000000000000000000000000000000000000000") == "USDC"
    assert _format_token_amount("1234500", 6) == "1.2345"
    assert _format_token_amount("1234500", None) is None
