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
    assert _format_token_amount("1000000", 6) == "1"
    assert _format_token_amount("0", 18) == "0"
    assert _format_token_amount("123456789012345678901234567890123456789", 18) == "123456789012345678901.234567890123456789"
    assert _format_token_amount("1234500", None) is None


class _FakeRPCResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _FakeRPCClient:
    last_instance = None

    def __init__(self, *args, **kwargs):
        self.calls = []
        type(self).last_instance = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json, headers):
        self.calls.append(json)
        method = json["method"]
        params = json["params"]
        if method == "eth_getTransactionByHash":
            result = {
                "hash": params[0],
                "blockNumber": "0x100",
                "from": "0x" + "1" * 40,
                "to": "0x" + "2" * 40,
                "value": "0x0",
            }
        elif method == "eth_getTransactionReceipt":
            result = {
                "status": "0x1",
                "gasUsed": "0x5208",
                "logs": [{
                    "address": "0x" + "a" * 40,
                    "topics": [
                        TRANSFER_TOPIC,
                        "0x" + "0" * 24 + "1" * 40,
                        "0x" + "0" * 24 + "2" * 40,
                    ],
                    "data": "0x" + format(1234500, "064x"),
                }],
            }
        elif method == "eth_chainId":
            result = "0x89"
        elif method == "eth_blockNumber":
            result = "0x105"
        elif method == "eth_call" and params[0]["data"] == "0x95d89b41":
            encoded = format(32, "064x") + format(4, "064x") + b"USDC".hex().ljust(64, "0")
            result = "0x" + encoded
        elif method == "eth_call" and params[0]["data"] == "0x313ce567":
            result = "0x" + format(6, "064x")
        else:
            result = None
        return _FakeRPCResponse({"jsonrpc": "2.0", "id": json["id"], "result": result})


def test_inspects_confirmed_transaction_and_decodes_token_transfer(monkeypatch):
    import app.services.blockchain as blockchain

    monkeypatch.setenv("POLYGON_RPC_URL", "https://polygon.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", _FakeRPCClient)
    tx_hash = "0x" + "b" * 64

    result = asyncio.run(blockchain.inspect_public_transaction(tx_hash, network="polygon"))

    assert result["found"] is True
    assert result["network"] == "polygon"
    assert result["status"] == "success"
    assert result["classification"] == "confirmed_transfer_recipient_credit_unverifiable"
    assert result["recipient_credit_verification_required"] is True
    assert result["recovery_candidate"] is False
    assert result["block_number"] == 256
    assert result["confirmations"] == 6
    assert result["gas_used"] == 21000
    assert result["token_transfer_count"] == 1
    transfer = result["token_transfers"][0]
    assert transfer["symbol"] == "USDC"
    assert transfer["decimals"] == 6
    assert transfer["amount_raw"] == "1234500"
    assert transfer["amount"] == "1.2345"
    metadata_calls = [
        call for call in _FakeRPCClient.last_instance.calls
        if call["method"] == "eth_call"
    ]
    assert len(metadata_calls) == 2
    assert all(call["params"][1] == "0x100" for call in metadata_calls)


def test_rejects_rpc_configured_for_wrong_chain(monkeypatch):
    import app.services.blockchain as blockchain

    class WrongChainClient(_FakeRPCClient):
        async def post(self, url, json, headers):
            if json["method"] == "eth_chainId":
                return _FakeRPCResponse({"jsonrpc": "2.0", "id": json["id"], "result": "0x1"})
            return await super().post(url, json, headers)

    monkeypatch.setenv("POLYGON_RPC_URL", "https://wrong-chain.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", WrongChainClient)
    with pytest.raises(blockchain.BlockchainProviderError, match="outra rede"):
        asyncio.run(blockchain.inspect_public_transaction("0x" + "c" * 64, network="polygon"))


def test_rejects_transfer_topics_with_nonzero_address_padding():
    malformed_topic = "0x" + "1" * 24 + "2" * 40
    event = {
        "address": "0x" + "a" * 40,
        "topics": [TRANSFER_TOPIC, malformed_topic, "0x" + "0" * 24 + "3" * 40],
        "data": "0x" + format(1, "064x"),
    }
    assert _decode_transfer_log(event) is None
