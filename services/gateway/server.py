"""Loopback HTTPS health endpoint for a bounded real transport probe.

No customer requests run through this endpoint. It does not establish a
payment deployment path. Runtime keys/certificates are outside this directory.
"""
import argparse
import datetime
import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def certificate(directory):
    directory.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "api.demo.northbridge.example")])
    current = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(current - datetime.timedelta(minutes=1))
            .not_valid_after(current + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("api.demo.northbridge.example")]), critical=False)
            .sign(key, hashes.SHA256()))
    private = directory / "gateway-key.pem"
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    private.chmod(0o600)
    public = directory / "gateway-cert.pem"
    public.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (directory / "gateway-public-evidence.json").write_text(json.dumps({
        "certificate_sha256": cert.fingerprint(hashes.SHA256()).hex(),
        "scope": "ephemeral loopback health endpoint; no customer traffic", "certificate_trust": "self-signed demo"
    }, indent=2) + "\n")
    return public, private


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"status":"ok","scope":"synthetic-loopback-health"}'
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9444)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    args = parser.parse_args()
    cert, key = certificate(args.runtime_dir)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(cert), str(key))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print(f"Demo HTTPS listening on 127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
