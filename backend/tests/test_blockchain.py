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
        "destination_is_burn_address": False,
        "destination_type": "standard_address",
    }


def test_detects_burn_destination_without_calling_it_recoverable():
    from app.services.blockchain import _is_burn_address

    assert _is_burn_address("0x" + "0" * 40) is True
    assert _is_burn_address("0x" + "0" * 39 + "1") is False
    assert _is_burn_address("0x" + "0" * 36 + "dead") is True
    assert _is_burn_address("0x" + "1" * 40) is False
    assert _is_burn_address("not-an-address") is False


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

def test_retries_missing_historical_token_metadata_at_latest(monkeypatch):
    import app.services.blockchain as blockchain

    class PrunedHistoricalMetadataClient(_FakeRPCClient):
        async def post(self, url, json, headers):
            if json["method"] == "eth_call" and json["params"][1] != "latest":
                self.calls.append(json)
                return _FakeRPCResponse({
                    "jsonrpc": "2.0",
                    "id": json["id"],
                    "error": {"code": -32000, "message": "historical state unavailable"},
                })
            return await super().post(url, json, headers)

    monkeypatch.setenv("POLYGON_RPC_URL", "https://polygon.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", PrunedHistoricalMetadataClient)
    result = asyncio.run(blockchain.inspect_public_transaction("0x" + "b" * 64, network="polygon"))

    transfer = result["token_transfers"][0]
    assert transfer["symbol"] == "USDC"
    assert transfer["decimals"] == 6
    assert transfer["amount"] == "1.2345"
    metadata_calls = [
        call for call in PrunedHistoricalMetadataClient.last_instance.calls
        if call["method"] == "eth_call"
    ]
    assert len(metadata_calls) == 4
    assert all(call["params"][1] == "0x100" for call in metadata_calls[:2])
    assert all(call["params"][1] == "latest" for call in metadata_calls[2:])



def test_classifies_confirmed_native_transfer_as_unverifiable_at_recipient(monkeypatch):
    import app.services.blockchain as blockchain

    class NativeTransferClient(_FakeRPCClient):
        async def post(self, url, json, headers):
            response = await super().post(url, json, headers)
            if json["method"] == "eth_getTransactionByHash":
                response.payload["result"]["value"] = "0xde0b6b3a7640000"
            if json["method"] == "eth_getTransactionReceipt":
                response.payload["result"]["logs"] = []
            return response

    monkeypatch.setenv("POLYGON_RPC_URL", "https://polygon.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", NativeTransferClient)
    result = asyncio.run(blockchain.inspect_public_transaction("0x" + "c" * 64, network="polygon"))

    assert result["classification"] == "confirmed_transfer_recipient_credit_unverifiable"
    assert result["recipient_credit_verification_required"] is True
    assert result["recovery_candidate"] is False
    assert result["token_transfer_count"] == 0


def test_failed_evm_transaction_is_not_a_recovery_candidate(monkeypatch):
    import app.services.blockchain as blockchain

    class FailedClient(_FakeRPCClient):
        async def post(self, url, json, headers):
            response = await super().post(url, json, headers)
            if json["method"] == "eth_getTransactionReceipt":
                response.payload["result"]["status"] = "0x0"
            return response

    monkeypatch.setenv("POLYGON_RPC_URL", "https://polygon.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", FailedClient)
    result = asyncio.run(blockchain.inspect_public_transaction("0x" + "d" * 64, network="polygon"))

    assert result["status"] == "failed"
    assert result["classification"] == "failed_on_chain"
    assert result["recipient_credit_verification_required"] is False
    assert result["recovery_candidate"] is False


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

def test_classifies_success_without_native_or_supported_token_transfer(monkeypatch):
    import app.services.blockchain as blockchain

    class NoTransferClient(_FakeRPCClient):
        async def post(self, url, json, headers):
            response = await super().post(url, json, headers)
            if json["method"] == "eth_getTransactionReceipt":
                response.payload["result"]["logs"] = []
            if json["method"] == "eth_getTransactionByHash":
                response.payload["result"]["value"] = "0x0"
            return response

    monkeypatch.setenv("POLYGON_RPC_URL", "https://polygon.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", NoTransferClient)
    result = asyncio.run(blockchain.inspect_public_transaction("0x" + "e" * 64, network="polygon"))

    assert result["status"] == "success"
    assert result["classification"] == "successful_transaction_no_supported_transfer_detected"
    assert result["recipient_credit_verification_required"] is False
    assert result["recovery_candidate"] is False


def test_retries_missing_historical_receipt_on_fallback_rpc(monkeypatch):
    import app.services.blockchain as blockchain

    class MissingReceiptOnPrimaryClient(_FakeRPCClient):
        async def post(self, url, json, headers):
            if json["method"] == "eth_getTransactionReceipt" and url == "https://polygon.example":
                self.calls.append(json)
                return _FakeRPCResponse({"jsonrpc": "2.0", "id": json["id"], "result": None})
            return await super().post(url, json, headers)

    monkeypatch.setenv("POLYGON_RPC_URL", "https://polygon.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", MissingReceiptOnPrimaryClient)
    result = asyncio.run(blockchain.inspect_public_transaction("0x" + "f" * 64, network="polygon"))

    assert result["status"] == "success"
    assert result["classification"] == "confirmed_transfer_recipient_credit_unverifiable"
    receipt_calls = [
        call for call in MissingReceiptOnPrimaryClient.last_instance.calls
        if call["method"] == "eth_getTransactionReceipt"
    ]
    assert len(receipt_calls) == 2


def test_uses_blockscout_to_decode_historical_token_transfer_when_rpc_receipt_is_missing(monkeypatch):
    import app.services.blockchain as blockchain

    tx_hash = "0x" + "f" * 64
    contract = "0x" + "a" * 40
    sender = "0x" + "1" * 40
    recipient = "0x" + "2" * 40

    async def blockscout_fallback(requested_hash):
        assert requested_hash == tx_hash
        return {
            "hash": tx_hash,
            "result": "success",
            "block_number": 256,
            "gas_used": "63197",
            "token_transfers": [{
                "type": "token_transfer",
                "token": {"address_hash": contract, "symbol": "USDT", "decimals": "6"},
                "from": {"hash": sender},
                "to": {"hash": recipient},
                "total": {"value": "9996000000", "decimals": "6"},
            }],
        }

    monkeypatch.setenv("POLYGON_RPC_URL", "https://polygon.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", _FakeRPCClient)
    monkeypatch.setattr(blockchain, "_fetch_blockscout_transaction", blockscout_fallback)
    result = asyncio.run(blockchain.inspect_public_transaction(tx_hash, network="polygon"))

    assert result["status"] == "success"
    assert result["classification"] == "confirmed_transfer_recipient_credit_unverifiable"
    assert result["receipt_source"] == "blockscout"
    assert result["gas_used"] == 63197
    assert result["token_transfer_count"] == 1
    transfer = result["token_transfers"][0]
    assert transfer["symbol"] == "USDT"
    assert transfer["amount"] == "9996"
    assert transfer["from_address"] == sender
    assert transfer["to_address"] == recipient


def test_mined_transaction_without_any_receipt_is_unknown_not_pending(monkeypatch):
    import app.services.blockchain as blockchain

    async def no_blockscout_result(_tx_hash):
        return None

    monkeypatch.setattr(blockchain, "_fetch_blockscout_transaction", no_blockscout_result)

    class MinedWithoutReceiptClient(_FakeRPCClient):
        async def post(self, url, json, headers):
            if json["method"] == "eth_getTransactionReceipt":
                self.calls.append(json)
                return _FakeRPCResponse({"jsonrpc": "2.0", "id": json["id"], "result": None})
            return await super().post(url, json, headers)

    monkeypatch.setenv("POLYGON_RPC_URL", "https://polygon.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", MinedWithoutReceiptClient)
    result = asyncio.run(blockchain.inspect_public_transaction("0x" + "f" * 64, network="polygon"))

    assert result["block_number"] == 256
    assert result["status"] == "unknown"
    assert result["classification"] == "unknown"
    assert result["recipient_credit_verification_required"] is False
    assert result["recovery_candidate"] is False


def test_transaction_without_block_and_receipt_is_pending(monkeypatch):
    import app.services.blockchain as blockchain

    class PendingClient(_FakeRPCClient):
        async def post(self, url, json, headers):
            if json["method"] == "eth_getTransactionByHash":
                response = await super().post(url, json, headers)
                response.payload["result"]["blockNumber"] = None
                return response
            if json["method"] == "eth_getTransactionReceipt":
                self.calls.append(json)
                return _FakeRPCResponse({"jsonrpc": "2.0", "id": json["id"], "result": None})
            return await super().post(url, json, headers)

    monkeypatch.setenv("POLYGON_RPC_URL", "https://polygon.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", PendingClient)
    result = asyncio.run(blockchain.inspect_public_transaction("0x" + "f" * 64, network="polygon"))

    assert result["status"] == "pending"
    assert result["classification"] == "pending_confirmation"
    assert result["recipient_credit_verification_required"] is False
    assert result["recovery_candidate"] is False


def test_burn_only_token_transfer_is_not_a_recovery_candidate(monkeypatch):
    import app.services.blockchain as blockchain

    class BurnTransferClient(_FakeRPCClient):
        async def post(self, url, json, headers):
            response = await super().post(url, json, headers)
            if json["method"] == "eth_getTransactionReceipt":
                response.payload["result"]["logs"][0]["topics"][2] = "0x" + "0" * 64
            return response

    monkeypatch.setenv("POLYGON_RPC_URL", "https://polygon.example")
    monkeypatch.setattr(blockchain.httpx, "AsyncClient", BurnTransferClient)
    result = asyncio.run(blockchain.inspect_public_transaction("0x" + "9" * 64, network="polygon"))

    assert result["classification"] == "confirmed_burn_destination_not_recoverable"
    assert result["burn_transfer_count"] == 1
    assert result["non_burn_token_transfer_count"] == 0
    assert result["recipient_credit_verification_required"] is False
    assert result["recovery_candidate"] is False
    assert "queima" in result["notice"].lower()
