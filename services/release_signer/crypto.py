"""Sign a domain-separated release digest; this call supports a platform edit."""
import hashlib

from cryptography.hazmat.primitives.asymmetric import ed25519


def generate_key():
    return ed25519.Ed25519PrivateKey.generate()


def signing_message(artifact):
    return b"northbridge/release/v1\x00" + hashlib.sha256(artifact).digest()


def sign_release(key, artifact):
    return key.sign(signing_message(artifact))


def verify_release(public_key, artifact, signature):
    public_key.verify(signature, signing_message(artifact))
