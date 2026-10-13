# A cryptographer's demo walkthrough

Opening: **“Which cryptography protects the bank's payments and ten-year statements, and what evidence is needed before we migrate it?”**

## 1. Establish the scenario

Start with a project and a repository asset named `qcipher-demo-bank`. Explain the source layout: gateway, identity, payment, statement archive, release signer and an unrelated public-rates service. A shared repository or ECDSA algorithm does not establish an operational dependency.

Optionally run `python verification/exercise.py` from a local clone to demonstrate execution. It exercises a synthetic token, payment, statement encryption/decryption, release verification and public-rates signature. The negative checks reject changed data and the wrong verification key. The remote source scan itself needs only the repository URL.

## 2. Discover source cryptography

In **Python source scan → GitHub repository**, paste `https://github.com/QCipher-Labs/qcipher-demo-bank`, leave the branch field empty, and start the scan. Show that the result records a GitHub commit and source locations. Inspect the service files below, build a CBOM, and review the assessment. A recorded commit can be used to repeat the exact scan later.

| Service | What the code actually does | Analyst interpretation |
| --- | --- | --- |
| Identity | RSA-3072 signs an RS256 token | Signature authenticity risk; increasing RSA key size does not remove Shor vulnerability. Token-format and verifier support constrain migration. |
| Payments | ECDSA with SECP256R1 signs a payment instruction | Integrity use; signature HNDL is not applicable. |
| Archive | AES-256-GCM protects statement content; RSA-2048-OAEP wraps its data key | The wrapping construction exposes long-lived confidentiality. Retain suitable symmetric encryption; validate a supported KEM-based key-establishment construction. ML-KEM is not a direct bulk-encryption replacement. |
| Release signer | Ed25519 authenticates a domain-separated release digest | A concrete signing migration candidate; all verifiers and key-storage dependencies must support it. |
| Public rates | ECDSA with its own distinct key signs public rates | Public data still needs authenticity. There is no payment-service dependency. |

Key generation alone does not establish the purpose of a key. A literal curve or local AES key length can be captured, while an arbitrary function argument's key size can remain unknown. Show that uncertainty rather than assigning unrelated facts to it.

## 3. Add business context

This is an optional extension after the whole-repository scan. For individual service context, create the Customer Payments and Public Market Data projects and their service assets using the CMDB guide. Scan the corresponding `scan/*` branches into those assets, import and review their CMDB files, then reassess. Show the archive's recorded owner, Regulated classification and ten-year declared protection period. Contrast it with the release signer's Public artifacts and critical integrity impact. These declarations apply to their named service; do not assign the archive's policy to the entire repository.

Keep declarations distinct from deployed exposure: source identity and a reviewed context link are not proof that every detected call protects all of the declared data. Business severity can remain unassessed while technical vulnerabilities and accountable owners are visible.

## 4. Probe TLS

Run the loopback gateway endpoint and scan it from the same collector host. Show the actual observed or negotiated results and retained evidence hashes. Treat key exchange, symmetric traffic encryption and certificate signing as separate roles.

The negotiated group depends on the installed TLS stack; do not promise a particular group. If a hybrid such as X25519MLKEM768 appears, assess its exact protocol, combiner and implementation. A classical component's Shor vulnerability does not establish a break of combined hybrid confidentiality. The self-signed certificate is a separate authentication/trust limitation.

Fingerprints, key-size scalars and version observations support the inventory; they are not themselves algorithms to migrate.

## 5. Review the migration plan

Use exact crypto objects, owners and reviewed context to discuss evidence collection, compatibility preparation, pilot gates and rollout approval. Inspect the archive's OAEP use separately from AES content encryption. Do not infer costs, HSM support, refresh opportunities or production dates from a source scan.

## 6. Exercise a signing candidate

Select the Ed25519 key-generation finding in `services/release_signer/crypto.py` from the repository scan and propose the supported ML-DSA-65 edit in the platform. Review, apply and recheck the source, then download the candidate. For optional application validation, use its release-signer file:

```sh
python verification/exercise.py --candidate-signer /path/to/candidate/crypto.py --output evidence/application-candidate.json
```

The 16 checks include new ML-DSA-65 signature verification, tamper rejection, rejection of old signatures under the new key, and explicit legacy verification of an old artifact. In the verified fixture, Ed25519 signatures are 64 bytes and ML-DSA-65 signatures are 3309 bytes. This demonstrates a compatibility consideration, not an accepted production performance budget. ML-DSA support requires the pinned cryptography provider.

## 7. Export the evidence

Export the published plan and assessment as JSON, Excel and PDF. Explain the revision, source locations, reviewed context, algorithm facts and remaining gates. Revoke a context link and reassess if demonstrating lifecycle behavior: a new revision changes while the saved previous revision and original CBOM remain intact.

Closing: **“We have a reviewable inventory and a tested local signing candidate. Production migration still depends on verified exposure, implementation support and an approved pilot.”**
