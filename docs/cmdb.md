# Import the bank's business context

Create **Customer Payments** and **Public Market Data** projects using the Generic template. Then create each asset with its owner from the table below. In the asset's identity tab add namespace `urn:northbridge:cmdb:demo:v1`, identifier kind `asset_id`, and its exact external ID.

| Project | Asset | External ID | Owner | Import |
| --- | --- | --- | --- | --- |
| Customer Payments | Customer API Gateway | `NB-CI-GATEWAY-001` | Digital Channels | [gateway.csv](../imports/by-asset/gateway.csv) |
| Customer Payments | Customer Identity Service | `NB-CI-IDENTITY-001` | Identity and Access Management | [identity.csv](../imports/by-asset/identity.csv) |
| Customer Payments | Payment Authorisation Service | `NB-CI-PAYMENTS-001` | Payments Engineering | [payments.csv](../imports/by-asset/payments.csv) |
| Customer Payments | Customer Statement Archive | `NB-CI-ARCHIVE-001` | Records and Data Platforms | [statement_archive.csv](../imports/by-asset/statement_archive.csv) |
| Customer Payments | Payment Release Signer | `NB-CI-RELEASE-001` | Platform Security | [release_signer.csv](../imports/by-asset/release_signer.csv) |
| Public Market Data | Public Market Rates Service | `NB-CI-RATES-001` | Market Data Engineering | [public_rates.csv](../imports/by-asset/public_rates.csv) |

For each asset:

1. Save and import its GitHub scan's CBOM into that asset.
2. Select **Import data for this asset** and its matching CSV above.
3. Choose source family **Asset inventory (CSV / JSON)** (`cryptograph.inventory.v1`) and exporter version `1`.
4. Review the parsed fields and publish the import.
5. Preview the CMDB record's association with the saved CBOM. Confirm the appropriate asset, CBOM or component scope and record your review rationale.
6. Reassess the project so the reviewed context appears in a new published assessment and migration plan.

The master [cmdb.csv](../cmdb.csv) contains all six rows. The platform's imports are asset-scoped: use the one-row files for this demonstration rather than uploading all assets into one service's workspace. [imports/index.json](../imports/index.json) is a reference manifest, not a bulk-import API command.

## Read the fields correctly

Classification is numeric: **0 Public, 1 Internal, 2 Confidential, 3 Restricted, 4 Regulated**. The built-in inventory mapping supports `asset_id`, `name`, `namespace`, `owner`, `hostname`, `classification`, `protection_years`, `integrity_impact`, `signature_role`, and `operational_state`. Additional columns are retained as raw context and do not automatically become graph edges.

- The archive declares Regulated data and a **ten-year confidentiality horizon**.
- Payments declare seven years for their protected records; identity's one-year declaration describes its named metadata, not the token's five-minute expiry.
- Published release artifacts and public rates declare Public data and zero confidentiality horizon while retaining critical/high integrity impact. Their private signing keys are not public.
- `signature_role=code_signing` applies to the release signer. Blank roles elsewhere remain unspecified.
- `declared_dependencies` describes intended topology. These strings do not prove executed service calls.
- `.example` hostnames are identity labels. The only implemented network target is the explicitly started loopback endpoint.

All context is declared and synthetic. There are no algorithm claims, key sizes, private keys or computed risk scores in the CMDB. Reviewed context supplies business information; a production risk tier or confidentiality HNDL eligibility still needs eligible operational exposure evidence.
