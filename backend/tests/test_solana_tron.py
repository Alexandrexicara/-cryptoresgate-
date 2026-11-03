import asyncio

import pytest

from app.services.solana import _token_deltas, _parsed_native_transfers, _burn_operations, _token_transfer_operations, _format_sol, inspect_solana_transaction
from app.services.tron import _decode_trc20, _is_burn, _format_trx, inspect_tron_transaction


def test_solana_token_balance_delta_uses_integer_amounts():
    meta = {
        "preTokenBalances": [{"accountIndex": 2, "mint": "Mint111", "owner": "Owner111",
                              "uiTokenAmount": {"amount": "9007199254740993", "decimals": 6}}],
        "postTokenBalances": [{"accountIndex": 2, "mint": "Mint111", "owner": "Owner111",
                               "uiTokenAmount": {"amount": "9007199254741993", "decimals": 6}}],
    }
    changes = _token_deltas(meta)
    assert len(changes) == 1
    assert changes[0]["amount_raw"] == "1000"
    assert changes[0]["direction"] == "received"


def test_solana_ignores_unchanged_token_balances():
    meta = {
        "preTokenBalances": [{"accountIndex": 0, "mint": "Mint111", "owner": "Owner111",
                              "uiTokenAmount": {"amount": "10", "decimals": 0}}],
        "postTokenBalances": [{"accountIndex": 0, "mint": "Mint111", "owner": "Owner111",
                               "uiTokenAmount": {"amount": "10", "decimals": 0}}],
    }
    assert _token_deltas(meta) == []


def test_solana_parses_system_transfer_instruction():
    tx = {"transaction": {"message": {"instructions": [
        {"program": "system", "parsed": {"type": "transfer", "info": {
            "source": "Sender111", "destination": "Recipient111", "lamports": 1500000000
        }}}
    ]}}}
    transfers = _parsed_native_transfers(tx)
    assert transfers[0]["amount_lamports"] == 1500000000
    assert transfers[0]["amount_sol"] == "1.5"


def test_solana_rejects_invalid_signature():
    with pytest.raises(ValueError):
        import asyncio
        asyncio.run(inspect_solana_transaction("not-a-signature"))


def test_tron_decodes_standard_trc20_transfer_log():
    topic0 = "0x" + "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    sender = "1" * 40
    recipient = "2" * 40
    log = {"address": "41" + "3" * 40,
           "topics": [topic0, "0x" + "0" * 24 + sender, "0x" + "0" * 24 + recipient],
           "data": "0x" + format(123456789, "064x")}
    decoded = _decode_trc20(log)
    assert decoded["amount_raw"] == "123456789"
    assert decoded["from_address_hex"] == "41" + sender
    assert decoded["to_address_hex"] == "41" + recipient


def test_tron_ignores_non_transfer_logs():
    assert _decode_trc20({"topics": ["0x" + "0" * 64], "data": "0x" + "0" * 64}) is None


def test_tron_rejects_invalid_transaction_id():
    with pytest.raises(ValueError):
        import asyncio
        asyncio.run(inspect_tron_transaction("invalid"))


def test_solana_formats_lamports_without_float_rounding():
    assert _format_sol(1_234_567_891) == "1.234567891"


def test_solana_detects_burn_instruction_separately():
    tx = {"transaction": {"message": {"instructions": [
        {"program": "spl-token", "parsed": {"type": "burn", "info": {"amount": "100"}}}
    ]}}}
    assert _burn_operations(tx) == 1


def test_tron_formats_sun_without_float_rounding():
    assert _format_trx(1_234_567) == "1.234567"


def test_tron_zero_and_dead_addresses_are_burn_but_normal_address_is_not():
    assert _is_burn("41" + "0" * 40)
    assert _is_burn("41" + "0" * 36 + "dead")
    assert not _is_burn("41" + "1" * 40)


def test_solana_counts_token_transfer_instructions_separately_from_burns():
    tx = {"transaction": {"message": {"instructions": [
        {"program": "spl-token", "parsed": {"type": "burn", "info": {}}},
        {"program": "spl-token", "parsed": {"type": "transferChecked", "info": {}}},
    ]}}}
    assert _burn_operations(tx) == 1
    assert _token_transfer_operations(tx) == 1



def test_solana_does_not_count_native_system_transfer_as_spl_transfer():
    tx = {"transaction": {"message": {"instructions": [
        {"program": "system", "parsed": {"type": "transfer", "info": {}}}
    ]}}}
    assert _token_transfer_operations(tx) == 0


def test_solana_counts_spl_token_2022_transfer():
    tx = {"transaction": {"message": {"instructions": [
        {"program": "spl-token-2022", "parsed": {"type": "transferChecked", "info": {}}}
    ]}}}
    assert _token_transfer_operations(tx) == 1


def test_solana_successful_transaction_includes_transfer_count(monkeypatch):
    import app.services.solana as solana

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": {
                "slot": 123,
                "meta": {
                    "err": None,
                    "fee": 5000,
                    "preTokenBalances": [
                        {"accountIndex": 1, "mint": "Mint111", "owner": "Sender111",
                         "uiTokenAmount": {"amount": "1000", "decimals": 2}}
                    ],
                    "postTokenBalances": [
                        {"accountIndex": 1, "mint": "Mint111", "owner": "Sender111",
                         "uiTokenAmount": {"amount": "900", "decimals": 2}},
                        {"accountIndex": 2, "mint": "Mint111", "owner": "Receiver111",
                         "uiTokenAmount": {"amount": "100", "decimals": 2}}
                    ]
                },
                "transaction": {"message": {"instructions": [
                    {"program": "spl-token", "parsed": {"type": "transfer", "info": {}}}
                ]}}
            }}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(solana.httpx, "AsyncClient", FakeClient)
    result = asyncio.run(solana.inspect_solana_transaction("1" * 88))
    assert result["status"] == "confirmed"
    assert result["token_transfer_operation_count"] == 1
    assert result["classification"] == "confirmed_transfer_requires_recipient_verification"
