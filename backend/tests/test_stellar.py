import asyncio

from app.services.stellar import (
    _extract_payments,
    _memo_required,
    inspect_stellar_transaction,
)


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


def test_extract_classic_stellar_payment():
    payments = _extract_payments([{
        "type": "payment",
        "from": "G_SOURCE",
        "to": "G_DESTINATION",
        "amount": "25.5",
        "asset_type": "native",
    }])
    assert len(payments) == 1
    assert payments[0]["to_address"] == "G_DESTINATION"
    assert payments[0]["asset_code"] == "XLM"
    assert payments[0]["amount"] == "25.5"


def test_extract_soroban_asset_balance_changes():
    payments = _extract_payments([{
        "type": "invoke_host_function",
        "source_account": "G_SOURCE",
        "asset_balance_changes": [
            {
                "type": "mint",
                "asset_type": "credit_alphanum4",
                "asset_code": "KALE",
                "asset_issuer": "G_ISSUER",
                "to": "G_MINTED",
                "amount": "1.25",
            },
            {
                "type": "transfer",
                "asset_type": "credit_alphanum4",
                "asset_code": "KALE",
                "asset_issuer": "G_ISSUER",
                "from": "G_SOURCE",
                "to": "G_DESTINATION",
                "amount": "0.5",
            },
        ],
    }])
    assert len(payments) == 1
    assert payments[0]["operation_type"] == "invoke_host_function:transfer"
    assert payments[0]["to_address"] == "G_DESTINATION"
    assert payments[0]["asset_code"] == "KALE"
    assert payments[0]["amount"] == "0.5"


def test_extract_deduplicates_same_balance_change():
    operation = {
        "type": "payment",
        "from": "G_SOURCE",
        "to": "G_DESTINATION",
        "amount": "10",
        "asset_type": "native",
        "asset_balance_changes": [{
            "type": "transfer",
            "to": "G_DESTINATION",
            "amount": "10",
            "asset_type": "native",
        }],
    }
    assert len(_extract_payments([operation])) == 1


def test_ignore_self_directed_path_payment():
    payments = _extract_payments([{
        "type": "path_payment_strict_send",
        "from": "G_SAME",
        "to": "G_SAME",
        "amount": "1",
        "asset_type": "native",
        "source_account": "G_SAME",
    }])
    assert payments == []
