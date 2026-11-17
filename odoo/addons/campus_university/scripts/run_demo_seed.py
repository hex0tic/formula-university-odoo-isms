#!/usr/bin/env python3
"""Provision local demo accounts without exposing credentials in tool output."""
import json
import os
from pathlib import Path
import secrets
import subprocess


def main():
    root = Path(__file__).resolve().parents[4]
    private = root / "evidence" / "private"
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(private, 0o700)
    path = private / "campus-demo-credentials.json"
    if path.exists():
        credentials = json.loads(path.read_text())
    else:
        credentials = {
            role: {"login": "campus." + role + "@orgil.example", "password": secrets.token_urlsafe(20)}
            for role in ["student", "other_student", "lecturer", "other_lecturer", "registrar", "reviewer", "auditor"]
        }
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(credentials, stream, ensure_ascii=False, indent=2)
    os.chmod(path, 0o600)
    script = "CAMPUS_DEMO_CREDENTIALS = " + repr(credentials) + "\n"
    script += Path(__file__).with_name("seed_demo.py").read_text()
    result = subprocess.run([
        "docker", "exec", "-i", "isms-odoo", "odoo", "shell",
        "-c", "/etc/odoo/odoo.conf", "-d", "orgil_isms", "--no-http",
        "--logfile=/tmp/campus-seed.log",
    ], input=script, text=True, capture_output=True)
    print(result.stdout)
    if result.returncode:
        print(result.stderr)
        raise SystemExit(result.returncode)
    print("Local credentials saved with mode 0600; excluded from distributable artifacts.")


if __name__ == "__main__":
    main()
