"""Check that the published source snapshots and CMDB describe the same six assets."""
import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

BASE = Path(__file__).resolve().parents[1]
SERVICES = {"gateway", "identity", "payments", "statement_archive", "release_signer", "public_rates"}
CLASSIFICATIONS = {"0": "Public", "1": "Internal", "2": "Confidential", "3": "Restricted", "4": "Regulated"}


def rows(path):
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def check(check_refs=False):
    master = rows(BASE / "cmdb.csv")
    assert len(master) == 6 and len({r["asset_id"] for r in master}) == 6
    by_service = {Path(r["source_path"]).name: r for r in master}
    assert set(by_service) == SERVICES
    index = json.loads((BASE / "imports/index.json").read_text())
    assert index["source_family"] == "cryptograph.inventory.v1"
    assert index["source_version"] == "1"
    assert index["namespace"] == "urn:northbridge:cmdb:demo:v1"
    assert len(index["imports"]) == 6
    imported_ids = set()
    for item in index["imports"]:
        scoped = rows(BASE / "imports" / item["file"])
        assert len(scoped) == 1
        row = scoped[0]
        assert row == next(r for r in master if r["asset_id"] == item["asset_id"])
        assert row["namespace"] == index["namespace"]
        assert row["name"] == item["asset_name"]
        for field in ("project_key", "project_name", "owner", "asset_type"):
            assert row[field] == item[field]
        assert CLASSIFICATIONS[row["classification"]] == row["classification_label"]
        assert row["operational_state"] == "declared" and row["environment"] == "demo"
        assert row["hostname"].endswith(".example")
        assert int(row["protection_years"]) >= 0
        dependencies = set(filter(None, row["declared_dependencies"].split("|")))
        assert dependencies <= {r["asset_id"] for r in master if r["project_key"] == row["project_key"]}
        assert row["asset_id"] not in imported_ids
        imported_ids.add(row["asset_id"])
    assert by_service["public_rates"]["project_key"] == "public-market-data"
    assert not by_service["public_rates"]["declared_dependencies"]
    assert by_service["statement_archive"]["protection_years"] == "10"
    assert by_service["release_signer"]["signature_role"] == "code_signing"
    assert by_service["release_signer"]["classification"] == "0"
    targets = json.loads((BASE / "scan-targets.json").read_text())
    assert targets["repository"] == "https://github.com/QCipher-Labs/qcipher-demo-bank"
    assert re.fullmatch(r"[0-9a-f]{40}", targets["source_revision"])
    assert len(targets["targets"]) == 6
    assert {t["service"] for t in targets["targets"]} == SERVICES
    for target in targets["targets"]:
        service = target["service"]
        row = by_service[service]
        expected_path = f"{row['source_path']}/{'server.py' if service == 'gateway' else 'crypto.py'}"
        assert target["path"] == expected_path
        assert target["asset_id"] == row["asset_id"]
        assert target["project_key"] == row["project_key"]
        assert target["ref"] == f"scan/{service}"
        assert re.fullmatch(r"[0-9a-f]{40}", target["commit"])
        source = (BASE / target["path"]).read_bytes()
        assert hashlib.sha256(source).hexdigest() == target["source_sha256"]
        ast.parse(source, filename=target["path"])
        if check_refs:
            commit = target["commit"]
            paths = subprocess.check_output(
                ["git", "ls-tree", "-r", "--name-only", commit], cwd=BASE, text=True
            ).splitlines()
            assert set(paths) == {target["path"], "README.md"}, (service, paths)
            published = subprocess.check_output(
                ["git", "show", f"{commit}:{target['path']}"], cwd=BASE
            )
            assert published == source
    for path in [*BASE.glob("verification/*.py"), *BASE.glob("scripts/*.py")]:
        ast.parse(path.read_bytes(), filename=str(path))
    for path in [BASE / "README.md", *BASE.glob("docs/*.md")]:
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if not link.startswith(("https://", "http://", "#")):
                assert (path.parent / link.split("#", 1)[0]).exists(), (path.name, link)
    print("Verified six isolated scan targets, CMDB identities/context, Python syntax and demo links.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-refs", action="store_true", help="Also check local scan-branch trees and contents")
    check(parser.parse_args().check_refs)
