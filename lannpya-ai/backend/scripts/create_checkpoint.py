"""Save a private local source/database checkpoint without changing live data."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[3]
EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".ruff_cache", ".mypy_cache", ".next", "checkpoints", "build", "dist", "htmlcov"}
EXCLUDED_FILES = {"workspace_access.json", "private_access.json", ".coverage", "Thumbs.db", ".DS_Store"}
RESTORE = """# Restore this checkpoint

This folder is a private local backup, not a public deployment.

## Contents

- source.zip: project source, tests, documentation and original PRD.
- workspace.sqlite3: a consistent snapshot of the API database at checkpoint time.
- manifest.json: SHA-256 checksums, source listing and verification information.

Private tokens, .env files, virtual environments, caches, older backups and
browser-local prototype data are not included. The database may contain private
delivery data and hashed customer capabilities: do not publish or share it.

## Safe restoration

1. Stop the app with Ctrl+C in the launcher terminal before replacing any live
   files. Keep a separate copy of any newer work/data you may want to retain.
2. Extract source.zip into a NEW EMPTY project folder. Do not extract it over
   active work unless you explicitly intend to replace that work.
3. Create lannpya-ai/backend/data in that restored folder and copy this folder's
   workspace.sqlite3 into it. Do not replace a newer database without backing it
   up first. Do not copy old SQLite WAL/SHM sidecar files into the restored folder.
4. From the restored lannpya-ai/backend folder, use Python 3.11+ (the original
   checkout used Python 3.12) to create .venv and install requirements-dev.lock.
   See API_INTEGRATION.md. The environment is not bundled in this backup.
5. Run .venv/Scripts/python.exe -m scripts.run_workspace. It generates fresh
   per-role tokens in data/workspace_access.json without resetting saved orders.
6. Open http://127.0.0.1:8000/api.html, press Ctrl+F5 and reconnect using the new
   runtime connection details. Do not reuse or publish old access tokens.

Restoration is intentionally not automatic: the checkpoint never overwrites or
deletes live files/database records on its own. This checkpoint does not restore
unexported browser-local prototype storage.
"""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def source_files():
    for directory, folders, files in os.walk(ROOT, followlinks=False):
        base = Path(directory)
        folders[:] = [name for name in sorted(folders) if name not in EXCLUDED_DIRS and not name.startswith(".pytest") and not (base / name).is_symlink() and (base / name).resolve() != ROOT / "lannpya-ai/backend/data"]
        for name in sorted(files):
            path = base / name
            if path.is_symlink() or name in EXCLUDED_FILES:
                continue
            if name.startswith(".env") and name != ".env.example":
                continue
            if path.suffix.lower() in {".pyc", ".pyo", ".sqlite3", ".db", ".log", ".pem", ".key"} or name.endswith((".sqlite3-wal", ".sqlite3-shm", ".db-wal", ".db-shm")):
                continue
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,90}", args.label):
        raise SystemExit("Use a short lowercase alphanumeric/hyphen label.")
    parent = (ROOT / "checkpoints").resolve()
    destination = (parent / args.label).resolve()
    if not destination.is_relative_to(parent) or destination == parent:
        raise SystemExit("Checkpoint target must be a new child of checkpoints/.")
    parent.mkdir(exist_ok=True)
    destination.mkdir(exist_ok=False)  # Never replace an existing checkpoint.
    try:
        destination.chmod(0o700)
    except OSError:
        pass
    listing = []
    archive = destination / "source.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for path in source_files():
            relative = path.relative_to(ROOT).as_posix()
            content = path.read_bytes()
            output.writestr(relative, content)
            listing.append({"path": relative, "bytes": len(content), "sha256": sha256(content)})
    database = ROOT / "lannpya-ai/backend/data/workspace.sqlite3"
    snapshot = destination / "workspace.sqlite3"
    counts = {}
    if database.is_file():
        with sqlite3.connect(database.resolve().as_uri()+"?mode=ro", uri=True, timeout=10) as live:
            with sqlite3.connect(snapshot) as saved:
                live.backup(saved)
                if saved.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Database backup failed integrity validation.")
                if saved.execute("PRAGMA foreign_key_check").fetchone():
                    raise RuntimeError("Database backup has invalid foreign-key references.")
                for table in ("orders", "users", "rider_profiles", "workflow_routes"):
                    counts[table] = saved.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        try:
            snapshot.chmod(0o600)
        except OSError:
            pass
    # Check every archived file against its manifest, not just ZIP readability.
    with zipfile.ZipFile(archive) as saved:
        if saved.testzip() is not None:
            raise RuntimeError("Source ZIP failed CRC validation.")
        for item in listing:
            if sha256(saved.read(item["path"])) != item["sha256"]:
                raise RuntimeError("Archived source checksum mismatch.")
    (destination / "RESTORE.md").write_text(RESTORE, encoding="utf-8")
    manifest = {"label": args.label, "created_at_yangon": datetime.now(timezone(timedelta(hours=6, minutes=30))).isoformat(), "source_root": str(ROOT), "verified": True, "source_file_count": len(listing), "database_counts": counts, "archives": {"source.zip": sha256(archive.read_bytes())}, "files": listing, "excluded": ["private runtime tokens", ".env files", "virtual environments", "Git internals", "caches", "prior backups", "browser-local storage"], "previous_test_results": {"javascript": 74, "backend": 435, "browser_visual_qa": "outstanding"}}
    if snapshot.is_file():
        manifest["archives"]["workspace.sqlite3"] = sha256(snapshot.read_bytes())
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"checkpoint": str(destination), "source_files": len(listing), "database_snapshot": snapshot.is_file(), "verified": True}))


if __name__ == "__main__":
    main()
