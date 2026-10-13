"""Synthetic RS256 login-token fixture; not a production identity provider."""
import base64
import json
import time

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def generate_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=3072)


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=")


def decode(value):
    return base64.urlsafe_b64decode(value + b"=" * (-len(value) % 4))


def issue_token(key, subject="synthetic-customer-001"):
    header = encode(b'{"alg":"RS256","typ":"JWT"}')
    payload = encode(json.dumps({"sub": subject, "iss": "northbridge-demo", "aud": "payments",
                                 "exp": int(time.time()) + 300}, sort_keys=True).encode())
    message = header + b"." + payload
    signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return (message + b"." + encode(signature)).decode("ascii")


def verify_token(public_key, token):
    header, payload, signature = token.encode("ascii").split(b".")
    if json.loads(decode(header)) != {"alg": "RS256", "typ": "JWT"}:
        raise ValueError("Unexpected token algorithm or type")
    public_key.verify(decode(signature), header + b"." + payload, padding.PKCS1v15(), hashes.SHA256())
    claims = json.loads(decode(payload))
    if claims["iss"] != "northbridge-demo" or claims["aud"] != "payments" or claims["exp"] <= time.time():
        raise ValueError("Invalid token context or expiry")
    return claims
