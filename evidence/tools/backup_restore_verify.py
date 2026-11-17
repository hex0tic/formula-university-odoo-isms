#!/usr/bin/env python3
"""Back up the local coursework stack and restore into a separate verification DB.

Never overwrites the primary database. Private backup files remain on this host.
The only deleted database is the temporary one this invocation just created.
"""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import time


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "odoo"
TABLES = ["campus_student", "campus_enrollment", "campus_grade_change", "isms_asset", "isms_risk",
          "isms_control", "isms_incident", "isms_policy", "isms_audit_log", "helpdesk_ticket"]


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, **kwargs)


def query(database, sql):
    return run(["docker", "exec", "isms-db", "psql", "-U", "odoo", "-d", database,
                "-At", "-c", sql], capture_output=True, text=True).stdout.strip()


def counts(database):
    return {table: int(query(database, "SELECT count(*) FROM " + table)) for table in TABLES}


def main():
    started = time.monotonic()
    tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    private = ROOT / "evidence" / "private" / "backups" / tag
    private.mkdir(parents=True, mode=0o700)
    os.chmod(private, 0o700)
    restored_db = "orgil_restore_" + tag
    lock = (ROOT / "management" / "runtime.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX)
    was_running = "odoo" in run(["docker", "compose", "ps", "--status", "running", "--services"],
                               cwd=COMPOSE, text=True, capture_output=True).stdout.splitlines()
    created = False
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "primary_database": "orgil_isms",
              "verification_database": restored_db, "scope": "Local database and filestore restore rehearsal"}
    try:
        if was_running:
            run(["docker", "compose", "stop", "odoo"], cwd=COMPOSE, capture_output=True)
        report["original_counts"] = counts("orgil_isms")
        with (private / "database.dump").open("wb") as stream:
            run(["docker", "exec", "isms-db", "pg_dump", "-U", "odoo", "-Fc", "orgil_isms"], stdout=stream)
        with (private / "filestore.tar.gz").open("wb") as stream:
            run(["docker", "run", "--rm", "--user", "0", "--entrypoint", "tar",
                 "-v", "/data/sembee/odoo-isms/filestore:/source:ro", "odoo:18.0",
                 "-czf", "-", "-C", "/source", "filestore/orgil_isms"], stdout=stream)
        for file in private.iterdir():
            os.chmod(file, 0o600)
        run(["docker", "exec", "isms-db", "createdb", "-U", "odoo", "-O", "odoo", restored_db])
        created = True
        restore_started = time.monotonic()
        with (private / "database.dump").open("rb") as stream:
            run(["docker", "exec", "-i", "isms-db", "pg_restore", "--exit-on-error", "-U", "odoo",
                 "-d", restored_db], stdin=stream)
        report["restored_counts"] = counts(restored_db)
        if report["restored_counts"] != report["original_counts"]:
            raise RuntimeError("Restored table counts differ")
        # Match every stored attachment in the restored DB to a file extracted
        # from the backup archive; Odoo's checksum is the file's SHA-1.
        attachments = query(restored_db,
                            "SELECT store_fname || '|' || checksum FROM ir_attachment "
                            "WHERE store_fname IS NOT NULL AND checksum IS NOT NULL")
        restore_dir = private / "filestore-restored"
        restore_dir.mkdir(mode=0o700)
        with tarfile.open(private / "filestore.tar.gz") as archive:
            archive.extractall(restore_dir, filter="data")
        checked = 0
        for line in attachments.splitlines():
            filename, checksum = line.split("|", 1)
            target = restore_dir / "filestore" / "orgil_isms" / filename
            if not target.is_file() or hashlib.sha1(target.read_bytes()).hexdigest() != checksum:
                raise RuntimeError("Restored attachment is missing or checksum differs: " + filename)
            checked += 1
        report.update({"attachments_verified": checked, "restore_seconds": round(time.monotonic()-restore_started, 3),
                       "backup_sizes_bytes": {name: (private/name).stat().st_size for name in ["database.dump", "filestore.tar.gz"]},
                       "backup_sha256": {name: hashlib.sha256((private/name).read_bytes()).hexdigest()
                                         for name in ["database.dump", "filestore.tar.gz"]}, "result": "PASS"})
    finally:
        if created:
            run(["docker", "exec", "isms-db", "dropdb", "-U", "odoo", restored_db])
        if was_running:
            run(["docker", "compose", "start", "odoo"], cwd=COMPOSE, capture_output=True)
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["verification_database_removed"] = created
        result = ROOT / "evidence" / "tests" / ("backup-restore-" + tag + ".json")
        result.parent.mkdir(exist_ok=True)
        result.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
