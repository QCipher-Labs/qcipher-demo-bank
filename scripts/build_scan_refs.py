"""Build one-source Git branches from committed main, then write pinned scan targets.

This changes local refs only. Review/commit scan-targets.json and push main plus
the listed scan branches to publish an updated scenario.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

BASE = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/QCipher-Labs/qcipher-demo-bank"


def git(*args, input=None, env=None):
    return subprocess.check_output(
        ["git", *args], cwd=BASE, input=input, env=env
    ).decode().strip()


def main():
    if git("branch", "--show-current") != "main":
        raise SystemExit("Run this on main after committing the source and CMDB changes.")
    if git("status", "--porcelain"):
        raise SystemExit("Commit or resolve local changes before building scan branches.")
    source_revision = git("rev-parse", "HEAD")
    rows = list(csv.DictReader(git("show", "HEAD:cmdb.csv").splitlines()))
    targets = []
    for row in rows:
        service = Path(row["source_path"]).name
        filename = "server.py" if service == "gateway" else "crypto.py"
        source_path = f"{row['source_path']}/{filename}"
        source = subprocess.check_output(
            ["git", "show", f"{source_revision}:{source_path}"], cwd=BASE
        )
        digest = hashlib.sha256(source).hexdigest()
        ref = f"refs/heads/scan/{service}"
        previous = subprocess.run(
            ["git", "rev-parse", "--verify", ref], cwd=BASE,
            capture_output=True, text=True
        )
        parent = previous.stdout.strip() if previous.returncode == 0 else None
        readme = (
            f"# Northbridge Bank — {row['name']}\n\n"
            f"This branch contains only the source for **{row['name']}**.\n\n"
            f"Scan it into the matching asset `{row['asset_id']}` in the "
            f"**{row['project_name']}** project. CMDB identity namespace: "
            f"`{row['namespace']}`.\n\n"
            f"[Full scenario, CMDB and walkthrough]({REPOSITORY}/tree/main)\n\n"
            f"Source revision: `{source_revision}`\n\n"
            f"Source SHA-256: `{digest}`\n\n"
            "These are synthetic source fixtures. Source discovery does not "
            "establish production deployment or inter-service dependencies.\n"
        ).encode()
        with tempfile.TemporaryDirectory(prefix="northbridge-scan-index-") as temp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(temp) / "index")}
            git("read-tree", "--empty", env=env)
            for path, content in [(source_path, source), ("README.md", readme)]:
                blob = git("hash-object", "-w", "--stdin", input=content)
                git("update-index", "--add", "--cacheinfo", "100644", blob, path, env=env)
            tree = git("write-tree", env=env)
        args = ["commit-tree", tree]
        if parent:
            args.extend(["-p", parent])
        commit = git(*args, input=f"Publish isolated {service} scan fixture\n".encode())
        git("update-ref", ref, commit, parent or "0" * 40)
        targets.append({
            "service": service, "asset_id": row["asset_id"],
            "project_key": row["project_key"], "ref": f"scan/{service}",
            "commit": commit, "path": source_path, "source_sha256": digest,
        })
        print(f"scan/{service}: {commit}")
    (BASE / "scan-targets.json").write_text(json.dumps({
        "repository": REPOSITORY, "source_revision": source_revision,
        "targets": targets,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
