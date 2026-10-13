"""Exercise the local platform's public APIs and retain its unmodified output.

Creates only the named Northbridge demo projects and their synthetic assets.
Application checks run separately; no evidence is injected into the database.
"""
import argparse
import csv
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PROJECTS = {"customer-payments": "northbridge-payments-verification-20261013",
            "public-market-data": "northbridge-market-data-verification-20261013"}


class Platform:
    def __init__(self, url, output):
        self.url = url.rstrip("/")
        if urllib.parse.urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("This runner is limited to an explicitly local platform")
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.nonce = uuid.uuid4().hex[:12]
        self.runs = []

    def request(self, path, body=None, *, raw=None, method=None):
        data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/octet-stream" if raw is not None else "application/json"}
        req = urllib.request.Request(self.url + path, data=data, headers=headers, method=method or ("POST" if data is not None else "GET"))
        try:
            with urllib.request.urlopen(req, timeout=65) as response:
                value = response.read()
                return json.loads(value) if value and "json" in response.headers.get("Content-Type", "") else value
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"{req.method} {path}: {error.code}: {error.read().decode()[:1000]}") from error

    def save(self, name, value):
        path = self.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else (json.dumps(value, indent=2) + "\n").encode())
        return path

    def config(self, project):
        return self.request(f"/projects/{project}/ingestion")

    def command(self, project, name):
        return {"idempotency_key": f"nb-{self.nonce}-{name}", "expected_generation": self.config(project)["generation"]}

    def wait_job(self, project, receipt):
        identifier = receipt.get("job_id") or receipt.get("id")
        deadline = time.monotonic() + 110
        while time.monotonic() < deadline:
            job = self.request(f"/projects/{project}/ingestion/jobs/{identifier}")
            if job["status"] == "published":
                return job
            if job["status"] in {"failed", "cancelled", "awaiting_mapping"}:
                self.save(f"jobs/{identifier}.json", job)
                raise RuntimeError(f"Import requires attention: {job['status']}; see retained job")
            time.sleep(0.4)
        raise RuntimeError("Import did not complete within the bounded wait")

    def import_file(self, project, asset, filename, content, family):
        command = self.command(project, f"upload-{uuid.uuid4().hex[:10]}")
        params = {**command, "filename": filename, "source_family": family, "source_version": "1", "asset_id": asset}
        current = self.request(f"/projects/{project}/ingestion/result") if command["expected_generation"] else {}
        matching = [key for key, value in current.get("sources", {}).items()
                    if value.get("filename") == filename and value.get("inventory_asset_id") == asset]
        if len(matching) > 1:
            raise RuntimeError("Duplicate demo source scopes require explicit resolution")
        if matching:
            params["replace_source_id"] = matching[0]
        upload = self.request(f"/projects/{project}/ingestion/uploads?" + urllib.parse.urlencode(params), raw=content)
        receipt = self.request(f"/projects/{project}/ingestion/batches",
                               {**self.command(project, f"batch-{upload['id']}"), "uploads": [upload["id"]]})
        job = self.wait_job(project, receipt)
        self.save(f"jobs/{job['id']}.json", job)
        return self.request(f"/projects/{project}/ingestion/result")

    def collection(self, project, revision, name):
        items, cursor = [], ""
        while True:
            params = urllib.parse.urlencode({"limit": 1000, "cursor": cursor})
            page = self.request(f"/projects/{project}/ingestion/results/{revision}/{name}?{params}")
            items.extend(page["items"])
            cursor = page.get("next_cursor")
            if not cursor:
                return items


def finish(api, state):
    release_run = state["source_runs"]["release_signer"]
    release = api.request(f"/python-sources/runs/{release_run}")
    proposals = [p for p in release["proposals"] if p["target"] == "ML-DSA-65" and p["status"] in {"proposed", "applied"}]
    if not proposals:
        finding = next(f for f in release["baseline"]["findings"] if f["algorithm"] == "Ed25519")
        release = api.request(f"/python-sources/runs/{release_run}/proposals",
                              {"finding_id": finding["id"], "source_sha256": finding["source_sha256"], "target_algorithm": "ML-DSA-65"})
        api.save("candidate/proposal.json", release)
        proposals = [release["proposals"][-1]]
    proposal = proposals[-1]
    if proposal["status"] != "applied":
        api.request(f"/python-sources/runs/{release_run}/proposals/{proposal['id']}/apply", {})
    validated = api.request(f"/python-sources/runs/{release_run}/recheck", {})
    api.save("candidate/platform-static-validation.json", validated)
    archive = api.save("candidate/release-signer-candidate.zip", api.request(f"/python-sources/runs/{release_run}/download/candidate"))
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        assert len(names) == 1 and Path(names[0]).name == "crypto.py", names
        candidate = zipped.read(names[0])
    api.save("candidate/crypto.py", candidate)
    print("Release edit and static check completed; application validation remains separate", flush=True)
    for key, project in PROJECTS.items():
        receipt = api.request(f"/projects/{project}/ingestion/reassess", api.command(project, "reviewed-context"))
        api.wait_job(project, receipt)
        manifest = api.request(f"/projects/{project}/ingestion/result")
        revision = manifest["revision"]
        api.save(f"published/{key}/manifest.json", manifest)
        for collection in ["nodes", "records", "references", "issues"]:
            api.save(f"published/{key}/{collection}.json", api.collection(project, revision, collection))
        for endpoint, filename in [("assessment/view?limit=250", "assessment.json"), ("migration/view?limit=250", "migration.json"),
                                   ("dashboard/view", "dashboard.json"), ("graph/view?limit=5000", "graph.json")]:
            api.save(f"published/{key}/{filename}", api.request(f"/projects/{project}/ingestion/results/{revision}/{endpoint}"))
        api.save(f"published/{key}/report.json", api.request(f"/projects/{project}/ingestion/results/{revision}/export/json"))
        for format in ("pdf", "xlsx"):
            api.save(f"published/{key}/report.{format}", api.request(f"/projects/{project}/ingestion/results/{revision}/export/{format}"))
        print(f"Retained published evidence for {key} at {revision[:12]}", flush=True)
    api.save("platform-state.json", state)


def network_scan(api, state, port):
    asset = state["assets"]["gateway"]
    project = asset["project_id"]
    scope = urllib.parse.urlencode({"project_id": project, "asset_id": asset["id"],
                                    "environment": "demo", "release": "local-loopback-health"})
    run = api.request("/network-scans/runs?" + scope, {"mode": "targets", "engines": ["custom-go", "zgrab2"],
        "protocols": ["tls"], "targets": [{"protocol": "tls", "host": "127.0.0.1", "port": port,
        "server_name": "api.demo.northbridge.example"}]})
    state["network_run"] = run["id"]
    api.save("platform-state.json", state)
    api.save("network/start.json", run)
    deadline = time.monotonic() + 100
    while run["status"] not in {"completed", "failed", "cancelled"} and time.monotonic() < deadline:
        time.sleep(0.4)
        run = api.request(f"/network-scans/runs/{run['id']}")
    api.save("network/run.json", run)
    if run["status"] != "completed":
        raise RuntimeError("Bounded network scan did not complete; inspect retained run")
    for engine in ["custom-go", "zgrab2"]:
        cbom = api.request(f"/network-scans/runs/{run['id']}/{engine}/cbom")
        api.save(f"network/{engine}-cbom.cdx.json", cbom)
        api.save(f"network/{engine}-observations.json", api.request(f"/network-scans/runs/{run['id']}/{engine}/observations"))
        api.save(f"network/{engine}-evidence.zip", api.request(f"/network-scans/runs/{run['id']}/{engine}/evidence"))
        api.save(f"network/{engine}-saved-cbom.json", api.request(f"/projects/{project}/inventory/cboms",
                  {"kind": "network", "run_id": run["id"], "engine": engine}))
        if engine == "custom-go":
            manifest = api.import_file(project, asset["id"], "gateway-network.cdx.json",
                       cbom if isinstance(cbom, bytes) else json.dumps(cbom).encode(), "cyclonedx")
            api.save("network/published-manifest.json", manifest)
    print("Bounded TLS scan retained and imported", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8001")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", choices=("github", "local"), default="github", help="Use pinned per-service GitHub snapshots or folders on the API host")
    parser.add_argument("--resume-finish", action="store_true")
    parser.add_argument("--network-port", type=int)
    args = parser.parse_args()
    api = Platform(args.api, args.output)
    if args.resume_finish:
        state = json.loads((args.output / "platform-state.json").read_text())
        if args.network_port:
            network_scan(api, state, args.network_port)
        finish(api, state)
        return
    targets = json.loads((BASE / "scan-targets.json").read_text()) if args.source == "github" else None
    rows = list(csv.DictReader((BASE / "cmdb.csv").open(newline="")))
    state = {"api": args.api, "run_nonce": api.nonce, "projects": PROJECTS, "assets": {}, "source_runs": {},
             "scope": "synthetic local cryptographic fixtures and declared CMDB; not a bank deployment"}
    api.save("health.json", api.request("/health"))
    existing = {p["id"]: p for p in api.request("/ingestion-projects")}
    for key, project in PROJECTS.items():
        if project not in existing:
            name = "Northbridge — " + ("Customer Payments" if key == "customer-payments" else "Public Market Data")
            api.request("/ingestion-projects", {"idempotency_key": f"create-{project}", "expected_generation": 0,
                "id": project, "name": name, "description": "Cryptographer verification using synthetic CMDB, real local source operations and bounded TLS evidence.", "pack": "generic@1.0.0"})
        print(f"Project ready: {project}", flush=True)
    order = ["identity", "payments", "statement_archive", "release_signer", "public_rates", "gateway"]
    by_service = {Path(row["source_path"]).name: row for row in rows}
    for service in order:
        row = by_service[service]
        project = PROJECTS[row["project_key"]]
        asset = api.request(f"/projects/{project}/inventory/assets", {"request_id": f"northbridge-{row['asset_id']}-v1",
            "name": row["name"], "kind": row["asset_type"], "owner": row["owner"], "description": row["protected_data"],
            "identities": [{"namespace": row["namespace"], "kind": "asset_id", "value": row["asset_id"]}]})
        state["assets"][service] = asset
        api.save(f"assets/{service}.json", asset)
        # Save and export each owned run before releasing its temporary slot.
        # Durable asset scan history and saved CBOMs remain available.
        if len(api.runs) == 3:
            api.request(f"/python-sources/runs/{api.runs.pop(0)}", method="DELETE")
        scope = urllib.parse.urlencode({"project_id": project, "asset_id": asset["id"], "environment": "demo", "release": "local-fixture-2026-10-13"})
        if targets:
            target = next(t for t in targets["targets"] if t["service"] == service)
            run = api.request("/python-sources/github?" + scope, {"repository": targets["repository"], "ref": target["commit"]})
        else:
            run = api.request("/python-sources/local-folder?" + scope, {"path": str(BASE / row["source_path"])})
        api.runs.append(run["id"])
        state["source_runs"][service] = run["id"]
        api.save(f"source/{service}-baseline.json", run)
        cbom = api.request(f"/python-sources/runs/{run['id']}/cbom", {})
        api.save(f"source/{service}-cbom-build.json", cbom)
        saved = api.request(f"/projects/{project}/inventory/cboms", {"kind": "python", "run_id": run["id"]})
        state["assets"][service]["saved_cbom_id"] = saved["id"]
        api.save(f"source/{service}-saved-cbom.json", saved)
        api.save(f"source/{service}-original.zip", api.request(f"/python-sources/runs/{run['id']}/download/original"))
        document = json.dumps(cbom["document"]).encode()
        baseline_manifest = api.import_file(project, asset["id"], service + "-source.cdx.json", document, "cyclonedx")
        before = api.request(f"/projects/{project}/ingestion/results/{baseline_manifest['revision']}/assessment/view?limit=250")
        api.save(f"comparison/{service}-before-cmdb.json", before)
        after_manifest = api.import_file(project, asset["id"], service + "-cmdb.csv",
                                        (BASE / "imports/by-asset" / (service + ".csv")).read_bytes(), "cryptograph.inventory.v1")
        after = api.request(f"/projects/{project}/ingestion/results/{after_manifest['revision']}/assessment/view?limit=250")
        api.save(f"comparison/{service}-after-cmdb.json", after)
        records = api.collection(project, after_manifest["revision"], "records")
        record = next(r for r in records if r.get("inventory_asset_id") == asset["id"] and r["kind"] == "asset" and r["fields"].get("asset_id") == row["asset_id"])
        body = {"revision": after_manifest["revision"], "record_id": record["id"], "scope": "asset"}
        preview = api.request(f"/projects/{project}/inventory/cboms/{saved['id']}/context/preview", body)
        link = api.request(f"/projects/{project}/inventory/cboms/{saved['id']}/context",
                           {**body, "preview_digest": preview["preview_digest"],
                            "rationale": "Exact demo CMDB asset identifier; applies only as declared asset business context, not proof of deployment or cryptographic use."})
        api.save(f"context/{service}-preview.json", preview)
        api.save(f"context/{service}-link.json", link)
        api.save("platform-state.json", state)
        print(f"Scanned and imported {service}: {len(run['baseline']['findings'])} source findings; context match {preview['match']}", flush=True)
    if args.network_port:
        network_scan(api, state, args.network_port)
    finish(api, state)


if __name__ == "__main__":
    main()
