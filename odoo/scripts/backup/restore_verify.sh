#!/usr/bin/env bash
# Restore one ISMS backup into a NEW throwaway database and filestore, verify it, then drop it.
# The production database name (orgil_isms) and any existing database are refused.
#
# Usage:
#   restore_verify.sh --backup-dir DIR [--target-db NAME] [--keep] [--report FILE]
#   restore_verify.sh --latest-from ROOT [--db NAME] [...]
#
# Environment (same meaning as backup.sh):
#   ISMS_DB_CONTAINER (isms-db), ISMS_DB_USER (odoo), ISMS_ODOO_CONTAINER (isms-odoo),
#   ISMS_FILESTORE_ROOT (/var/lib/odoo/filestore), ISMS_BACKUP_KEY_FILE (needed for encrypted backups),
#   ISMS_RESTORE_WORK_DIR (plaintext work dir, default /var/tmp; removed on exit).
#
# Measures:
#   RPO_observed  age of the chosen backup at verification time (now - manifest created_utc).
#                 The real RPO bound is the backup interval, which must come from a schedule.
#   RTO_measured  seconds from restore start until the restored DB and filestore pass verification.
#
# Exit codes: 0 verified; 1 usage/refused target; 2 preflight; 4 manifest hash failure;
#   12 decryption/plaintext hash failure; 15 restore failed; 16 verification mismatch (counts,
#   modules, attachments); 17 cleanup failed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$SCRIPT_DIR/isms_backup_tool.py"
ENC_ITERATIONS=310000
PROD_DB_NAME="orgil_isms"

: "${ISMS_DB_CONTAINER:=isms-db}"
: "${ISMS_DB_USER:=odoo}"
: "${ISMS_ODOO_CONTAINER:=isms-odoo}"
: "${ISMS_FILESTORE_ROOT:=/var/lib/odoo/filestore}"
: "${ISMS_BACKUP_KEY_FILE:=}"
: "${ISMS_RESTORE_WORK_DIR:=/var/tmp}"
: "${ISMS_DB_NAME:=orgil_isms}"

BACKUP_DIR=""
LATEST_FROM=""
TARGET_DB=""
KEEP=0
REPORT=""

usage() { sed -n '2,20p' "$0"; }
while (( $# )); do
  case "$1" in
    --backup-dir) BACKUP_DIR="$2"; shift 2 ;;
    --latest-from) LATEST_FROM="$2"; shift 2 ;;
    --db) ISMS_DB_NAME="$2"; shift 2 ;;
    --target-db) TARGET_DB="$2"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    --report) REPORT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
die() { local code="$1"; shift; log "ERROR: $*"; exit "$code"; }

# ---------------------------------------------------------------- choose backup
if [[ -z "$BACKUP_DIR" && -n "$LATEST_FROM" ]]; then
  BACKUP_DIR="$(python3 -I - "$LATEST_FROM" "$ISMS_DB_NAME" <<'PY'
import os, sys
root, db = sys.argv[1], sys.argv[2]
base = os.path.join(root, db)
names = sorted(n for n in os.listdir(base)
               if not n.endswith(".partial") and os.path.isfile(os.path.join(base, n, "COMPLETE")))
print(os.path.join(base, names[-1]) if names else "")
PY
)"
fi
[[ -n "$BACKUP_DIR" ]] || die 1 "no backup selected (use --backup-dir or --latest-from)"
[[ -f "$BACKUP_DIR/COMPLETE" && -f "$BACKUP_DIR/manifest.json" ]] || die 1 "not a complete backup: $BACKUP_DIR"
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd)"

SOURCE_DB="$(python3 -I "$TOOL" get --dir "$BACKUP_DIR" --path db_name)"
ENCRYPTED="$(python3 -I "$TOOL" get --dir "$BACKUP_DIR" --path encryption.enabled)"
CREATED="$(python3 -I "$TOOL" get --dir "$BACKUP_DIR" --path created_utc)"

# ---------------------------------------------------------------- target name guard
if [[ -z "$TARGET_DB" ]]; then TARGET_DB="isms_restore_verify_$(date -u +%Y%m%d%H%M%S)_$$"; fi
[[ "$TARGET_DB" =~ ^isms_restore_verify_[a-z0-9_]{1,40}$ ]] \
  || die 1 "target must match isms_restore_verify_[a-z0-9_]+ (got '$TARGET_DB')"
for forbidden in "$PROD_DB_NAME" "$SOURCE_DB" "$ISMS_DB_NAME"; do
  [[ "$TARGET_DB" != "$forbidden" ]] || die 1 "refusing to restore onto '$forbidden'"
done

psql_admin() {
  docker exec "$ISMS_DB_CONTAINER" psql -X -v ON_ERROR_STOP=1 -U "$ISMS_DB_USER" -d postgres -At -c "$1"
}
psql_target_ro() {
  docker exec -e PGOPTIONS="-c default_transaction_read_only=on" "$ISMS_DB_CONTAINER" \
    psql -X -v ON_ERROR_STOP=1 -U "$ISMS_DB_USER" -d "$TARGET_DB" -At -F $'\t' -c "$1"
}

# ---------------------------------------------------------------- preflight
for bin in docker python3 sha256sum tar; do command -v "$bin" >/dev/null 2>&1 || die 2 "missing command: $bin"; done
running="$(docker inspect -f '{{.State.Running}}' "$ISMS_DB_CONTAINER" 2>/dev/null || echo false)"
[[ "$running" == true ]] || die 2 "container $ISMS_DB_CONTAINER is not running"
running="$(docker inspect -f '{{.State.Running}}' "$ISMS_ODOO_CONTAINER" 2>/dev/null || echo false)"
[[ "$running" == true ]] || die 2 "container $ISMS_ODOO_CONTAINER is not running"
exists="$(psql_admin "SELECT count(*) FROM pg_database WHERE datname = '$TARGET_DB'")"
[[ "$exists" == 0 ]] || die 1 "database $TARGET_DB already exists; choose another --target-db"
if [[ "$ENCRYPTED" == True || "$ENCRYPTED" == true ]]; then
  [[ -n "$ISMS_BACKUP_KEY_FILE" && -r "$ISMS_BACKUP_KEY_FILE" ]] || die 1 "encrypted backup: set ISMS_BACKUP_KEY_FILE"
  command -v openssl >/dev/null 2>&1 || die 2 "openssl required"
fi

WORK="$(mktemp -d "$ISMS_RESTORE_WORK_DIR/isms-restore.XXXXXX")"
chmod 700 "$WORK"
FS_DEST="$ISMS_FILESTORE_ROOT/$TARGET_DB"
DB_CREATED=0
FS_CREATED=0
cleanup() {
  local rc=$?
  if (( ! KEEP )); then
    if (( DB_CREATED )); then docker exec "$ISMS_DB_CONTAINER" dropdb -U "$ISMS_DB_USER" --if-exists "$TARGET_DB" >/dev/null 2>&1 || rc=17; fi
    if (( FS_CREATED )); then docker exec "$ISMS_ODOO_CONTAINER" rm -rf -- "$FS_DEST" >/dev/null 2>&1 || rc=17; fi
    if (( DB_CREATED || FS_CREATED )); then log "throwaway database and filestore dropped (exit=$rc)"; fi
  else
    log "--keep: left $TARGET_DB and $FS_DEST in place"
  fi
  rm -rf -- "$WORK"
  exit "$rc"
}
trap cleanup EXIT

T0="$(date +%s.%N)"
log "restore_verify start source_db=$SOURCE_DB backup=$(basename "$BACKUP_DIR") target=$TARGET_DB"

# ---------------------------------------------------------------- 1. stored hashes
python3 -I "$TOOL" verify-manifest --dir "$BACKUP_DIR" > "$WORK/manifest-check.json" \
  || die 4 "stored file hash check failed: $(cat "$WORK/manifest-check.json")"
log "stored file SHA-256 verified against manifest"

# ---------------------------------------------------------------- 2. decrypt and plaintext hashes
if [[ "$ENCRYPTED" == True || "$ENCRYPTED" == true ]]; then
  for kind in database_dump filestore_archive; do
    case "$kind" in database_dump) stored=db.dump.enc; plain=db.dump ;; *) stored=filestore.tar.gz.enc; plain=filestore.tar.gz ;; esac
    openssl enc -d -aes-256-cbc -pbkdf2 -iter "$ENC_ITERATIONS" -in "$BACKUP_DIR/$stored" -out "$WORK/$plain" \
      -pass "file:$ISMS_BACKUP_KEY_FILE" || die 12 "decryption failed for $stored"
  done
else
  cp -- "$BACKUP_DIR/db.dump" "$WORK/db.dump"
  cp -- "$BACKUP_DIR/filestore.tar.gz" "$WORK/filestore.tar.gz"
fi
for pair in "database_dump:db.dump" "filestore_archive:filestore.tar.gz"; do
  kind="${pair%%:*}"; plain="${pair#*:}"
  expected="$(python3 -I "$TOOL" get --dir "$BACKUP_DIR" --path "files" | python3 -I -c '
import json, sys
kind = sys.argv[1]
for f in json.load(sys.stdin):
    if f["kind"] == kind:
        print(f["plain_sha256"])
' "$kind")"
  actual="$(sha256sum "$WORK/$plain" | cut -d' ' -f1)"
  [[ "$actual" == "$expected" ]] || die 12 "plaintext SHA-256 mismatch for $kind"
done
log "decrypted plaintext SHA-256 matches manifest"

# ---------------------------------------------------------------- 3. restore into throwaway DB
T_STEP="$(date +%s.%N)"
docker exec "$ISMS_DB_CONTAINER" createdb -U "$ISMS_DB_USER" -T template0 "$TARGET_DB"
DB_CREATED=1
if ! docker exec -i "$ISMS_DB_CONTAINER" pg_restore -U "$ISMS_DB_USER" --no-owner --no-acl -d "$TARGET_DB" \
     < "$WORK/db.dump" 2> "$WORK/pg_restore.err"; then
  log "pg_restore stderr (first lines):"; head -5 "$WORK/pg_restore.err" >&2 || true
  die 15 "pg_restore failed"
fi
log "pg_restore done in $(python3 -c 'import sys; print(round(float(sys.argv[1])-float(sys.argv[2]),1))' "$(date +%s.%N)" "$T_STEP") s"
T_STEP="$(date +%s.%N)"
docker exec -i "$ISMS_ODOO_CONTAINER" sh -c 'mkdir -p -- "$1" && tar -xzf - -C "$1"' sh "$FS_DEST" < "$WORK/filestore.tar.gz" \
  || die 15 "filestore extraction failed"
FS_CREATED=1
T_RESTORED="$(date +%s.%N)"
log "filestore extracted in $(python3 -c 'import sys; print(round(float(sys.argv[1])-float(sys.argv[2]),1))' "$T_RESTORED" "$T_STEP") s"

# ---------------------------------------------------------------- 4. verification
FAIL=0
python3 -I "$TOOL" modules-tsv --dir "$BACKUP_DIR" > "$WORK/modules.expected"
psql_target_ro "SELECT name, latest_version, state FROM ir_module_module WHERE state = 'installed' ORDER BY name" \
  > "$WORK/modules.actual"
if diff -q "$WORK/modules.expected" "$WORK/modules.actual" >/dev/null; then MODULES_OK=true; else MODULES_OK=false; FAIL=16; fi

python3 -I "$TOOL" counts-tsv --dir "$BACKUP_DIR" > "$WORK/counts.expected"
existing="$(psql_target_ro "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relkind = 'r'")"
union=""
while IFS=$'\t' read -r table _; do
  [[ -n "$table" ]] || continue
  if grep -qx -- "$table" <<<"$existing"; then
    union+="SELECT '$table', (SELECT count(*) FROM \"$table\")::text UNION ALL "
  fi
done < "$WORK/counts.expected"
: > "$WORK/counts.actual"
if [[ -n "$union" ]]; then psql_target_ro "${union% UNION ALL }" > "$WORK/counts.actual"; fi
COUNTS_JSON="$(python3 -I "$TOOL" compare-counts --dir "$BACKUP_DIR" --actual-tsv "$WORK/counts.actual")" || FAIL=16
COUNTS_OK=$([[ "$COUNTS_JSON" == *'"ok": true'* ]] && echo true || echo false)

# attachments: every store file must exist and its SHA-1 must equal ir_attachment.checksum (run in the Odoo container)
psql_target_ro "SELECT store_fname, checksum FROM ir_attachment WHERE store_fname IS NOT NULL AND checksum IS NOT NULL ORDER BY id" \
  > "$WORK/attach.tsv"
NO_STORE="$(psql_target_ro "SELECT count(*) FROM ir_attachment WHERE store_fname IS NULL")"
ATTACH_JSON="$(docker exec -i -e ISMS_ATTACH_LIST="$(cat "$WORK/attach.tsv")" "$ISMS_ODOO_CONTAINER" \
  python3 -I - check-attach --filestore "$FS_DEST" < "$TOOL")" || true
[[ -n "$ATTACH_JSON" ]] || ATTACH_JSON='{"ok": false, "problems": ["attachment check did not run"]}'
ATTACH_OK=$([[ "$ATTACH_JSON" == *'"ok": true'* ]] && echo true || echo false)
[[ "$ATTACH_OK" == true ]] || FAIL=16
T_VERIFIED="$(date +%s.%N)"

elapsed() { python3 -c 'import sys; print(round(float(sys.argv[2]) - float(sys.argv[1]), 2))' "$1" "$2"; }
RESTORE_S="$(elapsed "$T0" "$T_RESTORED")"
VERIFY_S="$(elapsed "$T_RESTORED" "$T_VERIFIED")"
RTO_S="$(elapsed "$T0" "$T_VERIFIED")"
AGE_S="$(python3 -c 'import sys,datetime as d; c=d.datetime.strptime(sys.argv[1],"%Y%m%dT%H%M%SZ").replace(tzinfo=d.timezone.utc); print(int((d.datetime.now(d.timezone.utc)-c).total_seconds()))' "$CREATED")"

export R_SOURCE_DB="$SOURCE_DB" R_TARGET_DB="$TARGET_DB" R_BACKUP="$(basename "$BACKUP_DIR")" R_CREATED="$CREATED"
export R_MODULES_OK="$MODULES_OK" R_COUNTS_OK="$COUNTS_OK" R_ATTACH_OK="$ATTACH_OK" R_NO_STORE="$NO_STORE"
export R_RESTORE_S="$RESTORE_S" R_VERIFY_S="$VERIFY_S" R_RTO_S="$RTO_S" R_AGE_S="$AGE_S" R_KEEP="$KEEP"
export R_COUNTS_JSON="$COUNTS_JSON" R_ATTACH_JSON="$ATTACH_JSON" R_FAIL="$FAIL"
REPORT_JSON="$(python3 -I -c '
import json, os
e = os.environ
def b(k): return e[k] == "true"
report = {
    "source_db": e["R_SOURCE_DB"], "target_db": e["R_TARGET_DB"], "backup_dir": e["R_BACKUP"],
    "backup_created_utc": e["R_CREATED"],
    "stored_and_plaintext_hashes_ok": True,
    "modules_match": b("R_MODULES_OK"), "counts_match": b("R_COUNTS_OK"), "attachments_ok": b("R_ATTACH_OK"),
    "attachments_without_store_fname": int(e["R_NO_STORE"]),
    "restore_seconds": float(e["R_RESTORE_S"]), "verify_seconds": float(e["R_VERIFY_S"]),
    "rto_measured_seconds": float(e["R_RTO_S"]), "rpo_observed_backup_age_seconds": int(e["R_AGE_S"]),
    "throwaway_kept": e["R_KEEP"] == "1", "exit_code": int(e["R_FAIL"]),
    "counts_detail": json.loads(e["R_COUNTS_JSON"]), "attachment_detail": json.loads(e["R_ATTACH_JSON"]),
}
print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
')"
echo "$REPORT_JSON"
[[ -z "$REPORT" ]] || printf '%s\n' "$REPORT_JSON" > "$REPORT"

if (( FAIL )); then die "$FAIL" "verification mismatch (modules=$MODULES_OK counts=$COUNTS_OK attachments=$ATTACH_OK)"; fi
log "VERIFIED: restore + checks passed"
exit 0
