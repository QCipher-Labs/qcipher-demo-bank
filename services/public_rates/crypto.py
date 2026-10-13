"""Public rates use a distinct ECDSA key and have no payment-system imports."""
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec


def generate_key():
    return ec.generate_private_key(ec.SECP256R1())


def canonical(rates):
    return json.dumps(rates, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sign_rates(key, rates):
    return key.sign(canonical(rates), ec.ECDSA(hashes.SHA256()))


def verify_rates(public_key, rates, signature):
    public_key.verify(signature, canonical(rates), ec.ECDSA(hashes.SHA256()))
