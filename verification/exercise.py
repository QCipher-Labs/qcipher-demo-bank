"""Independent application checks; the platform's source validator does not run these."""
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import serialization

BASE = Path(__file__).resolve().parents[1]


def load(name, path=None):
    path = path or BASE / "services" / name / "crypto.py"
    spec = importlib.util.spec_from_file_location("northbridge_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_fingerprint(key):
    value = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(value).hexdigest()


def reject(operation):
    try:
        operation()
    except (InvalidSignature, InvalidTag, ValueError):
        return True
    raise AssertionError("Tampered or wrong-key input was accepted")


def exercise(candidate_signer=None):
    identity, payments, archive, signer, rates = [load(name) for name in
        ["identity", "payments", "statement_archive", "release_signer", "public_rates"]]
    identity_key, payment_key, archive_key, signing_key, rates_key = [module.generate_key() for module in
        [identity, payments, archive, signer, rates]]
    checks = {}
    token = identity.issue_token(identity_key)
    assert identity.verify_token(identity_key.public_key(), token)["sub"] == "synthetic-customer-001"
    checks["rs256_token_roundtrip"] = True
    parts = token.split(".")
    parts[1] = identity.encode(b'{"sub":"attacker"}').decode()
    checks["changed_token_rejected"] = reject(lambda: identity.verify_token(identity_key.public_key(), ".".join(parts)))
    instruction = {"payment_id": "synthetic-payment-001", "customer": "synthetic-customer-001", "amount_eur": 42}
    signature = payments.sign_instruction(payment_key, instruction)
    payments.verify_instruction(payment_key.public_key(), instruction, signature)
    checks["ecdsa_payment_roundtrip"] = True
    checks["changed_payment_rejected"] = reject(lambda: payments.verify_instruction(payment_key.public_key(),
        {**instruction, "amount_eur": 42000}, signature))
    plaintext = json.dumps({"statement_id": "synthetic-statement-001", "instruction": instruction}, sort_keys=True).encode()
    envelope = archive.seal(archive_key.public_key(), plaintext)
    assert archive.open_record(archive_key, envelope) == plaintext
    checks["rsa_oaep_aes256_archive_roundtrip"] = True
    changed = copy.deepcopy(envelope)
    ciphertext = bytearray(base64.b64decode(changed["ciphertext"]))
    ciphertext[0] ^= 1
    changed["ciphertext"] = base64.b64encode(ciphertext).decode()
    checks["changed_archive_ciphertext_rejected"] = reject(lambda: archive.open_record(archive_key, changed))
    changed_key = copy.deepcopy(envelope)
    wrapped = bytearray(base64.b64decode(changed_key["wrapped_key"]))
    wrapped[0] ^= 1
    changed_key["wrapped_key"] = base64.b64encode(wrapped).decode()
    checks["changed_wrapped_key_rejected"] = reject(lambda: archive.open_record(archive_key, changed_key))
    artifact = b"synthetic northbridge payment release v1"
    release_signature = signer.sign_release(signing_key, artifact)
    signer.verify_release(signing_key.public_key(), artifact, release_signature)
    checks["ed25519_release_roundtrip"] = True
    checks["changed_release_rejected"] = reject(lambda: signer.verify_release(signing_key.public_key(), artifact + b"tampered", release_signature))
    public_document = {"EUR_USD": "1.10", "scope": "synthetic-public-rates"}
    rates_signature = rates.sign_rates(rates_key, public_document)
    rates.verify_rates(rates_key.public_key(), public_document, rates_signature)
    checks["public_rates_roundtrip"] = True
    checks["payment_key_cannot_verify_rates"] = reject(lambda: rates.verify_rates(payment_key.public_key(), public_document, rates_signature))
    fingerprints = {name: public_fingerprint(key) for name, key in [("identity", identity_key), ("payments", payment_key),
        ("archive", archive_key), ("release", signing_key), ("public_rates", rates_key)]}
    assert fingerprints["payments"] != fingerprints["public_rates"]
    checks["same_algorithm_distinct_keys"] = True
    candidate = None
    if candidate_signer:
        candidate_module = load("candidate_signer", candidate_signer)
        new_key = candidate_module.generate_key()
        new_signature = candidate_module.sign_release(new_key, artifact)
        candidate_module.verify_release(new_key.public_key(), artifact, new_signature)
        assert type(new_key).__name__ == "MLDSA65PrivateKey"
        checks["mldsa65_candidate_roundtrip"] = True
        checks["changed_candidate_release_rejected"] = reject(lambda: candidate_module.verify_release(new_key.public_key(), artifact + b"tampered", new_signature))
        checks["old_ed25519_signature_rejected_by_new_key"] = reject(lambda: candidate_module.verify_release(new_key.public_key(), artifact, release_signature))
        signer.verify_release(signing_key.public_key(), artifact, release_signature)
        checks["explicit_legacy_verifier_still_reads_old_release"] = True
        candidate = {"signature_bytes": len(new_signature), "key_type": type(new_key).__name__,
                     "source_sha256": hashlib.sha256(candidate_signer.read_bytes()).hexdigest()}
    return {"scope": "local synthetic cryptographic fixture; no deployed inter-service path established",
            "checks": checks, "passed": len(checks), "public_key_fingerprints": fingerprints,
            "archive_suite": archive.SUITE, "baseline_signature_bytes": len(release_signature), "candidate": candidate}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-signer", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = exercise(args.candidate_signer)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text)
