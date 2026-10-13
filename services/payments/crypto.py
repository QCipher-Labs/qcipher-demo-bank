"""A payment instruction signature, independent of transport confidentiality."""
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec


def generate_key():
    return ec.generate_private_key(ec.SECP256R1())


def canonical(instruction):
    return json.dumps(instruction, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sign_instruction(key, instruction):
    return key.sign(canonical(instruction), ec.ECDSA(hashes.SHA256()))


def verify_instruction(public_key, instruction, signature):
    public_key.verify(signature, canonical(instruction), ec.ECDSA(hashes.SHA256()))
