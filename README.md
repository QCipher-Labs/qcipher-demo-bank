# Northbridge Bank — PQC migration demo

A fictional bank with **real, runnable cryptography**, an importable CMDB, and a repeatable QCipher demonstration. All customers, payments, records, business declarations and hostnames are synthetic.

The story: a customer receives an RSA-signed login token, approves an ECDSA-signed payment, and receives an AES-encrypted statement whose data key is wrapped with RSA. A separate signer authenticates software releases. An unrelated public-rates service uses its own ECDSA key.

The application verifier exercises these operations together. These are source fixtures rather than deployed HTTP microservices. The gateway is a separate loopback HTTPS health endpoint for collecting real TLS evidence.

## Run the banking scenario

Use Python 3.12 or later:

```sh
git clone https://github.com/QCipher-Labs/qcipher-demo-bank.git
cd qcipher-demo-bank
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python verification/exercise.py --output evidence/application-baseline.json
```

The verifier performs **12 checks**, including token/payment/archive/release round trips, tamper rejection, and rejection of a public-rates signature under the payment service's different key. Keys are generated in memory for each run.

## Scan directly from GitHub in QCipher

Create the two projects and six assets listed in [the CMDB import guide](docs/cmdb.md). In each asset's Python source scan, enter:

**Repository:** `https://github.com/QCipher-Labs/qcipher-demo-bank`

**Branch, tag or commit:** the matching scan branch below, or its immutable commit in [scan-targets.json](scan-targets.json).

| Project | Asset | Scan branch | Cryptography to inspect |
| --- | --- | --- | --- |
| Customer Payments | Customer API Gateway | `scan/gateway` | TLS configuration and generated RSA certificate; probe the running endpoint for negotiated evidence |
| Customer Payments | Customer Identity Service | `scan/identity` | RSA-3072 / RS256 login signatures |
| Customer Payments | Payment Authorisation Service | `scan/payments` | ECDSA / P-256 payment signatures |
| Customer Payments | Customer Statement Archive | `scan/statement_archive` | AES-256-GCM plus RSA-2048-OAEP data-key wrapping |
| Customer Payments | Payment Release Signer | `scan/release_signer` | Ed25519 release signatures; candidate change to ML-DSA-65 |
| Public Market Data | Public Market Rates Service | `scan/public_rates` | ECDSA / P-256 with an independent key |

Each scan branch contains only that service's source and a description. Scanning `main` discovers the entire repository, including verification helpers; it does not establish which individual asset uses every finding. Use the service branches for asset-scoped CMDB enrichment.

Save the scan's CBOM, import it into the same asset, import the matching one-row CMDB CSV, review and confirm the context link, then **reassess**. Inspect the graph, algorithm assessment, declared business context, migration work items and exports. The ten-year archive and public-but-integrity-critical release signer make the confidentiality/authenticity distinction visible.

## Collect real TLS evidence

Start the endpoint **on the machine running the QCipher collector**:

```sh
python services/gateway/server.py --port 9444 --runtime-dir runtime
```

Scan `127.0.0.1:9444` with SNI `api.demo.northbridge.example`, selecting the gateway asset. Inspect TLS versions, negotiated key exchange and ciphers, and the presented certificate separately. The certificate is deliberately self-signed; this endpoint carries only a health response. Stop it after collection. Runtime keys and evidence are ignored by Git.

## Optional automated QCipher walkthrough

For an existing local QCipher development installation with its normal local principal and ingestion worker:

```sh
python verification/platform_run.py --api http://127.0.0.1:8001 --source github --output evidence/platform-demo --network-port 9444
python verification/exercise.py --candidate-signer evidence/platform-demo/candidate/crypto.py --output evidence/application-candidate.json
```

The runner scans the six pinned GitHub snapshots, creates/reuses the named demo projects and assets, imports source and CMDB evidence, records context links, reassesses, generates the release-signing candidate, and saves JSON/PDF/Excel reports. It replaces only matching demo source scopes and preserves their published history. The generated signing candidate adds **four checks** for ML-DSA-65, tampering, and explicit legacy verification.

Use `--source local` to scan this clone's service folders instead; those folders must be accessible on the QCipher API host. The runner is limited to a loopback API and assumes the existing local-development authentication configuration. For another installation, use its normal authenticated UI.

## Demo materials

- [Demo walkthrough and expected results](docs/demo.md)
- [CMDB master export](cmdb.csv) and [asset-scoped import files](imports/by-asset)
- [CMDB import guide](docs/cmdb.md)
- [Immutable GitHub scan targets](scan-targets.json)
- [Independent application verifier](verification/exercise.py)

Business lifetimes are illustrative declarations, not legal retention advice. Shared algorithms, project membership and repository membership do not prove operational dependencies. Source scans and a bounded TLS probe do not prove production deployment, private-key custody or complete inventory coverage. Migration targets remain conditional on protocol, provider, verifier and key-management compatibility. QCipher platform code is not included in this repository.
