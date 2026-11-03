import asyncio

from app.services.bitcoin import _extract_outputs, inspect_bitcoin_transaction


def test_rejects_invalid_bitcoin_txid():
    try:
        asyncio.run(inspect_bitcoin_transaction("invalid"))
    except ValueError as exc:
        assert "64 caracteres" in str(exc)
    else:
        raise AssertionError("TXID inválido deveria ser rejeitado")


def test_extracts_bitcoin_outputs_in_satoshis_and_btc():
    outputs = _extract_outputs({
        "vout": [
            {"value": 125000000, "scriptpubkey_address": "bc1qexample"},
            {"value": "invalid"},
        ]
    })
    assert len(outputs) == 1
    assert outputs[0]["address"] == "bc1qexample"
    assert outputs[0]["value_sats"] == 125000000
    assert outputs[0]["value_btc"] == 1.25


def test_coinbase_input_is_marked_as_mining_reward():
    from app.services.bitcoin import _extract_inputs

    inputs = _extract_inputs({"vin": [{"is_coinbase": True}]})
    assert inputs[0]["is_coinbase"] is True
