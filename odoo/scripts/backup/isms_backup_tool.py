#!/usr/bin/env python3
"""ISMS backup helper (Python 3 standard library only).

Subcommands:
  write-manifest   build manifest.json and SHA256SUMS for a backup directory
  verify-manifest  recheck stored file sizes and SHA-256 against manifest.json
  get              print one manifest value (dotted path), used by shell scripts
  modules-tsv      print manifest module list as TSV (name, version, state)
  counts-tsv       print manifest row counts as TSV
  compare-counts   compare manifest row counts with a TSV of counts from a restored DB
  check-attach     verify ir_attachment store files (SHA-1 = checksum); run inside the Odoo container
  retention        keep newest backup per day (N days) and per ISO week (M weeks); prune the rest

Run with `python3 -I` so that no file in the current directory shadows the stdlib.
This file never reads or prints encryption keys.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys

SCHEMA = "isms-backup-manifest/1"
DUMP_STORED = ("db.dump", "db.dump.enc")
FS_STORED = ("filestore.tar.gz", "filestore.tar.gz.enc")
TS_FORMAT = "%Y%m%dT%H%M%SZ"
ENC_ITERATIONS = 310000  # openssl enc -pbkdf2 -iter; must match backup.sh and restore_verify.sh


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line:
                rows.append(line.split("\t"))
    return rows


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def cmd_write_manifest(args):
    d = args.dir
    encrypted = args.encrypted == "1"
    stored_names = [DUMP_STORED[1 if encrypted else 0], FS_STORED[1 if encrypted else 0]]
    plain = {}
    for kind, sha, size in read_tsv(args.plain_tsv):
        plain[kind] = {"plain_sha256": sha, "plain_size": int(size)}
    files = []
    for name, kind in zip(stored_names, ("database_dump", "filestore_archive")):
        path = os.path.join(d, name)
        entry = {
            "kind": kind,
            "name": name,
            "stored_size": os.path.getsize(path),
            "stored_sha256": sha256_file(path),
            "encrypted": encrypted,
        }
        entry.update(plain.get(kind, {}))
        files.append(entry)
    now = utc_now()
    modules = [{"name": n, "version": v, "state": s} for n, v, s in read_tsv(args.modules_tsv)]
    counts = {}
    for table, count in read_tsv(args.counts_tsv):
        counts[table] = None if count == "" else int(count)
    manifest = {
        "schema": SCHEMA,
        "created_utc": now.strftime(TS_FORMAT),
        "created_utc_iso": now.isoformat(),
        "db_name": args.db,
        "odoo_release": args.odoo_release,
        "odoo_base_module_version": args.odoo_base_version,
        "postgres_server_version": args.pg_version,
        "installed_module_count": len(modules),
        "modules": modules,
        "row_counts": counts,
        "encryption": {"enabled": encrypted, "cipher": "aes-256-cbc", "kdf": "pbkdf2",
                       "iterations": ENC_ITERATIONS} if encrypted
                      else {"enabled": False},
        "filestore_entry_count": args.filestore_entries,
        "immutability": {"requested": args.immutable_requested == "1", "result": args.immutable_result},
        "files": files,
    }
    tmp = os.path.join(d, "manifest.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, os.path.join(d, "manifest.json"))
    lines = []
    for name in stored_names + ["manifest.json"]:
        lines.append("%s  %s" % (sha256_file(os.path.join(d, name)), name))
    with open(os.path.join(d, "SHA256SUMS"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(json.dumps({"ok": True, "dir": d, "files": stored_names}))
    return 0


def load_manifest(d):
    with open(os.path.join(d, "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


def cmd_verify_manifest(args):
    manifest = load_manifest(args.dir)
    problems = []
    for f in manifest["files"]:
        path = os.path.join(args.dir, f["name"])
        if not os.path.isfile(path):
            problems.append("missing: " + f["name"])
            continue
        if os.path.getsize(path) != f["stored_size"]:
            problems.append("size mismatch: " + f["name"])
        if sha256_file(path) != f["stored_sha256"]:
            problems.append("sha256 mismatch: " + f["name"])
    print(json.dumps({"ok": not problems, "problems": problems, "db_name": manifest["db_name"],
                      "created_utc": manifest["created_utc"]}, ensure_ascii=False))
    return 0 if not problems else 4


def cmd_get(args):
    value = load_manifest(args.dir)
    for part in args.path.split("."):
        if isinstance(value, list):
            value = value[int(part)]
        else:
            value = value.get(part) if isinstance(value, dict) else None
        if value is None:
            break
    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False))
    elif value is None:
        print("")
    else:
        print(value)
    return 0


def cmd_modules_tsv(args):
    for m in load_manifest(args.dir)["modules"]:
        print("%s\t%s\t%s" % (m["name"], m["version"], m["state"]))
    return 0


def cmd_counts_tsv(args):
    for table, count in sorted(load_manifest(args.dir)["row_counts"].items()):
        print("%s\t%s" % (table, "" if count is None else count))
    return 0


def cmd_compare_counts(args):
    manifest = load_manifest(args.dir)
    actual = {t: (None if c == "" else int(c)) for t, c in read_tsv(args.actual_tsv)}
    expected = manifest["row_counts"]
    mismatches = {}
    for table, exp in expected.items():
        exp_norm = "absent" if exp is None else exp
        got = actual.get(table, "absent")
        if got != exp_norm:
            mismatches[table] = {"expected": exp_norm, "actual": got}
    print(json.dumps({"ok": not mismatches, "tables": len(expected), "mismatches": mismatches}))
    return 0 if not mismatches else 5


def cmd_check_attach(args):
    """Runs inside the Odoo container. Input: env ISMS_ATTACH_LIST lines 'store_fname<TAB>sha1'."""
    raw = os.environ.get("ISMS_ATTACH_LIST", "")
    root = os.path.realpath(args.filestore)
    checked = missing = mismatch = bad_path = 0
    problems = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        store_fname, expected = line.split("\t")
        checked += 1
        path = os.path.realpath(os.path.join(root, store_fname))
        if not path.startswith(root + os.sep):
            bad_path += 1
            problems.append("unsafe store path")
            continue
        if not os.path.isfile(path):
            missing += 1
            problems.append("missing " + store_fname)
            continue
        digest = hashlib.sha1()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            mismatch += 1
            problems.append("sha1 mismatch " + store_fname)
    ok = missing == 0 and mismatch == 0 and bad_path == 0
    print(json.dumps({"ok": ok, "checked": checked, "missing": missing, "sha1_mismatch": mismatch,
                      "unsafe_paths": bad_path, "problems": problems[:20]}))
    return 0 if ok else 6


def backup_dirs(root, db):
    base = os.path.join(root, db)
    found = []
    if not os.path.isdir(base):
        return found
    for name in os.listdir(base):
        path = os.path.join(base, name)
        if name.endswith(".partial") or not os.path.isfile(os.path.join(path, "COMPLETE")):
            continue
        try:
            manifest = load_manifest(path)
            when = dt.datetime.strptime(manifest["created_utc"], TS_FORMAT).replace(tzinfo=dt.timezone.utc)
        except (OSError, ValueError, KeyError):
            continue
        found.append((when, path))
    return sorted(found, reverse=True)


def cmd_retention(args):
    backups = backup_dirs(args.root, args.db)
    keep = set()
    days, weeks = set(), set()
    for when, path in backups:
        day = when.date()
        week = day.isocalendar()[:2]
        if day not in days and len(days) < args.daily:
            days.add(day)
            keep.add(path)
        if week not in weeks and len(weeks) < args.weekly:
            weeks.add(week)
            keep.add(path)
    if args.keep:
        keep.add(os.path.join(args.root, args.db, args.keep))
    removed, failed = [], []
    for when, path in backups:
        if path in keep:
            continue
        if args.dry_run:
            removed.append(os.path.basename(path) + " (dry-run)")
            continue
        try:
            shutil.rmtree(path)
            removed.append(os.path.basename(path))
        except OSError as exc:
            failed.append("%s: %s" % (os.path.basename(path), exc.strerror))
    print(json.dumps({"ok": not failed, "root": args.root, "db": args.db, "kept": len(keep),
                      "pruned": removed, "failed": failed, "daily": args.daily, "weekly": args.weekly}))
    return 0 if not failed else 7


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write-manifest")
    w.add_argument("--dir", required=True)
    w.add_argument("--db", required=True)
    w.add_argument("--odoo-release", default="")
    w.add_argument("--odoo-base-version", default="")
    w.add_argument("--pg-version", default="")
    w.add_argument("--modules-tsv", required=True)
    w.add_argument("--counts-tsv", required=True)
    w.add_argument("--plain-tsv", required=True)
    w.add_argument("--encrypted", choices=["0", "1"], default="0")
    w.add_argument("--filestore-entries", type=int, default=0)
    w.add_argument("--immutable-requested", choices=["0", "1"], default="0")
    w.add_argument("--immutable-result", default="not requested")
    w.set_defaults(func=cmd_write_manifest)

    v = sub.add_parser("verify-manifest")
    v.add_argument("--dir", required=True)
    v.set_defaults(func=cmd_verify_manifest)

    g = sub.add_parser("get")
    g.add_argument("--dir", required=True)
    g.add_argument("--path", required=True)
    g.set_defaults(func=cmd_get)

    mt = sub.add_parser("modules-tsv")
    mt.add_argument("--dir", required=True)
    mt.set_defaults(func=cmd_modules_tsv)

    ct = sub.add_parser("counts-tsv")
    ct.add_argument("--dir", required=True)
    ct.set_defaults(func=cmd_counts_tsv)

    c = sub.add_parser("compare-counts")
    c.add_argument("--dir", required=True)
    c.add_argument("--actual-tsv", required=True)
    c.set_defaults(func=cmd_compare_counts)

    a = sub.add_parser("check-attach")
    a.add_argument("--filestore", required=True)
    a.set_defaults(func=cmd_check_attach)

    r = sub.add_parser("retention")
    r.add_argument("--root", required=True)
    r.add_argument("--db", required=True)
    r.add_argument("--daily", type=int, required=True)
    r.add_argument("--weekly", type=int, required=True)
    r.add_argument("--keep", default="", help="backup directory name that must never be pruned")
    r.add_argument("--dry-run", action="store_true")
    r.set_defaults(func=cmd_retention)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
