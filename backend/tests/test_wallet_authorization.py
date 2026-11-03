from eth_account import Account
from eth_account.messages import encode_defunct

from app.routes.wallet_authorization import recover_wallet_signer


def test_recovers_address_from_valid_personal_sign_message():
    account = Account.create()
    message = "CryptoResgate wallet proof test; no transaction is sent."
    signature = Account.sign_message(encode_defunct(text=message), account.key).signature.hex()

    assert recover_wallet_signer(message, signature) == account.address.lower()


def test_signature_cannot_be_replayed_for_a_different_message():
    account = Account.create()
    signature = Account.sign_message(
        encode_defunct(text="case A nonce 123"), account.key
    ).signature.hex()

    assert recover_wallet_signer("case B nonce 456", signature) != account.address.lower()
