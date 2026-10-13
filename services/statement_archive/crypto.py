"""AES-256-GCM records whose data keys are wrapped with RSA-2048-OAEP."""
import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SUITE = "RSA-2048-OAEP-SHA256+AES-256-GCM"


def generate_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def oaep():
    return padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(),
                        label=b"northbridge/statement/v1")


def b64(value):
    return base64.b64encode(value).decode("ascii")


def unb64(value):
    return base64.b64decode(value, validate=True)


def aad(header):
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode()


def seal(public_key, statement):
    data_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    header = {"version": 1, "suite": SUITE, "record_id": "synthetic-statement-001"}
    return {"header": header, "wrapped_key": b64(public_key.encrypt(data_key, oaep())),
            "nonce": b64(nonce), "ciphertext": b64(AESGCM(data_key).encrypt(nonce, statement, aad(header)))}


def open_record(key, envelope):
    if set(envelope) != {"header", "wrapped_key", "nonce", "ciphertext"}:
        raise ValueError("Invalid record fields")
    if envelope["header"] != {"version": 1, "suite": SUITE, "record_id": "synthetic-statement-001"}:
        raise ValueError("Unexpected archive suite or record identity")
    data_key = key.decrypt(unb64(envelope["wrapped_key"]), oaep())
    return AESGCM(data_key).decrypt(unb64(envelope["nonce"]), unb64(envelope["ciphertext"]), aad(envelope["header"]))
