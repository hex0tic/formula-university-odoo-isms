#!/usr/bin/env bash
# ISMS backup: PostgreSQL custom-format dump + Odoo filestore archive, SHA-256 manifest,
# optional AES-256 encryption, copy to secondary/rsync targets with hash verification,
# retention, lock file and optional chattr +i (best effort).
#
# Usage:
#   odoo/scripts/backup/backup.sh [--immutable] [-h|--help]
#
# All settings are environment variables (defaults match odoo/docker-compose.yml):
#   ISMS_DB_NAME            database to back up                  (default orgil_isms)
#   ISMS_DB_CONTAINER       PostgreSQL container                  (default isms-db)
#   ISMS_DB_USER            PostgreSQL role                       (default odoo)
#   ISMS_ODOO_CONTAINER     Odoo container (mounts /var/lib/odoo) (default isms-odoo)
#   ISMS_FILESTORE_PATH     filestore dir inside Odoo container   (default /var/lib/odoo/filestore/<db>)
#   ISMS_BACKUP_ROOT        primary backup root (must be outside the repository)
#                                                                  (default /var/backups/isms)
#   ISMS_BACKUP_COPY_DIRS   colon-separated mountpoints for separate backup disks or NAS shares
#   ISMS_BACKUP_RSYNC_TARGET optional user@host:/absolute/path, copied over rsync+ssh (BatchMode)
#   ISMS_BACKUP_KEY_FILE    optional path to an encryption key FILE (mode 0400/0600). The key
#                           is never printed and never stored in the repository.
#   ISMS_BACKUP_KEEP_DAILY  newest backup per day kept for N days      (default 7)
#   ISMS_BACKUP_KEEP_WEEKLY newest backup per ISO week kept for N weeks (default 4)
#   ISMS_BACKUP_IMMUTABLE   1 = also try `chattr +i` on stored files (needs root; failure is reported)
#
# Exit codes:
#   0  success          1  configuration / usage error     2  preflight failed
#   3  another backup holds the lock                       10 database dump or filestore export failed
#   11 manifest or hash failure    12 encryption failure    13 copy or post-copy verification failed
#   14 retention failed (backup itself succeeded)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$SCRIPT_DIR/isms_backup_tool.py"
ENC_ITERATIONS=310000

: "${ISMS_DB_NAME:=orgil_isms}"
: "${ISMS_DB_CONTAINER:=isms-db}"
: "${ISMS_DB_USER:=odoo}"
: "${ISMS_ODOO_CONTAINER:=isms-odoo}"
: "${ISMS_FILESTORE_PATH:=/var/lib/odoo/filestore/$ISMS_DB_NAME}"
: "${ISMS_BACKUP_ROOT:=/var/backups/isms}"
: "${ISMS_BACKUP_COPY_DIRS:=}"
: "${ISMS_BACKUP_RSYNC_TARGET:=}"
: "${ISMS_BACKUP_KEY_FILE:=}"
: "${ISMS_BACKUP_KEEP_DAILY:=7}"
: "${ISMS_BACKUP_KEEP_WEEKLY:=4}"
: "${ISMS_BACKUP_IMMUTABLE:=0}"

for arg in "$@"; do
  case "$arg" in
    --immutable) ISMS_BACKUP_IMMUTABLE=1 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 1 ;;
  esac
done

umask 077
TS="$(date -u +%Y%m%dT%H%M%SZ)"
START_EPOCH="$(date +%s)"
COPY_FAILURES=0
PARTIAL=""
FINAL=""

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { local code="$1"; shift; log "ERROR: $*"; exit "$code"; }

cleanup() {
  local rc=$?
  if [[ -n "$PARTIAL" && -d "$PARTIAL" ]]; then
    rm -rf -- "$PARTIAL"   # may contain plaintext before encryption; always remove on failure
    log "removed incomplete work dir"
  fi
  exit "$rc"
}
trap cleanup EXIT

# ---------------------------------------------------------------- preflight
for bin in docker python3 sha256sum flock tar gzip; do
  command -v "$bin" >/dev/null 2>&1 || die 2 "missing command: $bin"
done
[[ "$ISMS_DB_NAME" =~ ^[A-Za-z0-9_]+$ ]] || die 1 "ISMS_DB_NAME must match [A-Za-z0-9_]+"
[[ "$ISMS_BACKUP_ROOT" == /* ]] || die 1 "ISMS_BACKUP_ROOT must be an absolute path"
case "$ISMS_BACKUP_ROOT" in
  "$SCRIPT_DIR"*|*/formula-university-odoo-isms/*) die 1 "backup root must be outside the repository" ;;
esac
[[ "$ISMS_BACKUP_KEEP_DAILY" =~ ^[0-9]+$ && "$ISMS_BACKUP_KEEP_WEEKLY" =~ ^[0-9]+$ ]] \
  || die 1 "retention values must be non-negative integers"
[[ "$ISMS_BACKUP_IMMUTABLE" == 0 || "$ISMS_BACKUP_IMMUTABLE" == 1 ]] || die 1 "ISMS_BACKUP_IMMUTABLE must be 0 or 1"

if [[ -n "$ISMS_BACKUP_RSYNC_TARGET" && ! "$ISMS_BACKUP_RSYNC_TARGET" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.@-]*:/[a-zA-Z0-9_./-]+$ ]]; then
  die 1 "rsync target must be user@host:/absolute/path with plain path components"
fi

ENCRYPT=0
if [[ -n "$ISMS_BACKUP_KEY_FILE" ]]; then
  command -v openssl >/dev/null 2>&1 || die 2 "openssl required for encryption"
  [[ -f "$ISMS_BACKUP_KEY_FILE" && -r "$ISMS_BACKUP_KEY_FILE" ]] || die 2 "key file not readable"
  mode="$(stat -c %a "$ISMS_BACKUP_KEY_FILE")"
  if (( 8#$mode & 8#077 )); then die 2 "key file mode must be 0400 or 0600 (found $mode)"; fi
  [[ -s "$ISMS_BACKUP_KEY_FILE" ]] || die 2 "key file is empty"
  ENCRYPT=1
fi
if [[ -n "$ISMS_BACKUP_COPY_DIRS$ISMS_BACKUP_RSYNC_TARGET" ]] && (( ! ENCRYPT )); then
  die 1 "secondary backup requires ISMS_BACKUP_KEY_FILE"
fi

for c in "$ISMS_DB_CONTAINER" "$ISMS_ODOO_CONTAINER"; do
  running="$(docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null || echo false)"
  [[ "$running" == true ]] || die 2 "container $c is not running"
done

mkdir -p -- "$ISMS_BACKUP_ROOT"
exec 9>"$ISMS_BACKUP_ROOT/.backup.lock"
if ! flock -n 9; then die 3 "another backup run holds $ISMS_BACKUP_ROOT/.backup.lock"; fi

# read-only SQL helper: PGOPTIONS makes every statement in the session read-only
psql_ro() {
  docker exec -e PGOPTIONS="-c default_transaction_read_only=on" "$ISMS_DB_CONTAINER" \
    psql -X -v ON_ERROR_STOP=1 -U "$ISMS_DB_USER" -d "$ISMS_DB_NAME" -At -F $'\t' -c "$1"
}

db_exists="$(psql_ro "SELECT 1 FROM pg_database WHERE datname = '$ISMS_DB_NAME'" || true)"
[[ "$db_exists" == 1 ]] || die 2 "database $ISMS_DB_NAME does not exist on $ISMS_DB_CONTAINER"
docker exec "$ISMS_ODOO_CONTAINER" test -d "$ISMS_FILESTORE_PATH" || die 2 "filestore path missing: $ISMS_FILESTORE_PATH"

DEST_DIR="$ISMS_BACKUP_ROOT/$ISMS_DB_NAME"
PARTIAL="$DEST_DIR/.$TS.partial"
FINAL="$DEST_DIR/$TS"
mkdir -p -- "$DEST_DIR"
mkdir -- "$PARTIAL"
log "backup start db=$ISMS_DB_NAME ts=$TS encrypt=$ENCRYPT immutable=$ISMS_BACKUP_IMMUTABLE"

# ---------------------------------------------------------------- metadata (read-only)
ODOO_RELEASE="$(docker exec "$ISMS_ODOO_CONTAINER" python3 -c 'import odoo.release as r; print(r.version)' | tr -d '\r')"
BASE_VERSION="$(psql_ro "SELECT latest_version FROM ir_module_module WHERE name = 'base'" || true)"
PG_VERSION="$(psql_ro "SHOW server_version" || true)"
psql_ro "SELECT name, latest_version, state FROM ir_module_module WHERE state = 'installed' ORDER BY name" \
  > "$PARTIAL/modules.tsv"

KEY_TABLES=(isms_asset isms_threat isms_vulnerability isms_risk isms_control isms_incident isms_policy
  isms_policy_ack isms_audit_log isms_finding isms_capa isms_evidence campus_student campus_course
  campus_offering campus_enrollment campus_grade_change res_users ir_attachment helpdesk_ticket access_review)
existing="$(psql_ro "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname = ANY(ARRAY['$(IFS=,; printf '%s' "${KEY_TABLES[*]}" | sed "s/,/','/g")'])" || true)"
: > "$PARTIAL/counts.tsv"
union=""
for t in "${KEY_TABLES[@]}"; do
  if grep -qx -- "$t" <<<"$existing"; then
    union+="SELECT '$t', (SELECT count(*) FROM \"$t\")::text UNION ALL "
  else
    printf '%s\t\n' "$t" >> "$PARTIAL/counts.tsv"
  fi
done
if [[ -n "$union" ]]; then
  psql_ro "${union% UNION ALL }" >> "$PARTIAL/counts.tsv"
fi
log "metadata: odoo_release=$ODOO_RELEASE base=$BASE_VERSION pg=$PG_VERSION modules=$(wc -l < "$PARTIAL/modules.tsv") tables_counted=$(grep -vc $'\t$' "$PARTIAL/counts.tsv" || true)"

# ---------------------------------------------------------------- dump and filestore
DUMP="$PARTIAL/db.dump"
FS_ARCHIVE="$PARTIAL/filestore.tar.gz"
if ! docker exec "$ISMS_DB_CONTAINER" pg_dump -U "$ISMS_DB_USER" -Fc --no-owner --no-acl -d "$ISMS_DB_NAME" > "$DUMP"; then
  die 10 "pg_dump failed"
fi
[[ -s "$DUMP" ]] || die 10 "pg_dump produced an empty file"
if ! docker exec "$ISMS_ODOO_CONTAINER" tar -C "$ISMS_FILESTORE_PATH" -czf - . > "$FS_ARCHIVE"; then
  die 10 "filestore export failed"
fi
FS_ENTRIES="$(tar -tzf "$FS_ARCHIVE" | wc -l)"
log "dump bytes=$(stat -c %s "$DUMP") filestore bytes=$(stat -c %s "$FS_ARCHIVE") filestore entries=$FS_ENTRIES"

# plaintext digests are recorded before encryption so a restore can verify the decrypted data
{
  printf 'database_dump\t%s\t%s\n' "$(sha256sum "$DUMP" | cut -d' ' -f1)" "$(stat -c %s "$DUMP")"
  printf 'filestore_archive\t%s\t%s\n' "$(sha256sum "$FS_ARCHIVE" | cut -d' ' -f1)" "$(stat -c %s "$FS_ARCHIVE")"
} > "$PARTIAL/plain.tsv"

if (( ENCRYPT )); then
  for f in "$DUMP" "$FS_ARCHIVE"; do
    openssl enc -aes-256-cbc -pbkdf2 -iter "$ENC_ITERATIONS" -salt -in "$f" -out "$f.enc" \
      -pass "file:$ISMS_BACKUP_KEY_FILE" || die 12 "openssl encryption failed"
    rm -f -- "$f"   # no plaintext copy is kept at rest
  done
  log "encrypted stored files with aes-256-cbc pbkdf2 iter=$ENC_ITERATIONS"
fi

# ---------------------------------------------------------------- immutability (best effort)
IMMUTABLE_RESULT="not requested"
if (( ISMS_BACKUP_IMMUTABLE )); then
  if chattr_out="$(chattr +i "$PARTIAL"/db.dump* "$PARTIAL"/filestore.tar.gz* 2>&1)"; then
    IMMUTABLE_RESULT="applied chattr +i to stored files"
  else
    IMMUTABLE_RESULT="NOT applied (needs root or a supporting filesystem): $(head -1 <<<"$chattr_out" | cut -c1-160)"
  fi
  log "immutability: $IMMUTABLE_RESULT"
fi

# ---------------------------------------------------------------- manifest
ENC_FLAG=$(( ENCRYPT ))
python3 -I "$TOOL" write-manifest --dir "$PARTIAL" --db "$ISMS_DB_NAME" \
  --odoo-release "$ODOO_RELEASE" --odoo-base-version "$BASE_VERSION" --pg-version "$PG_VERSION" \
  --modules-tsv "$PARTIAL/modules.tsv" --counts-tsv "$PARTIAL/counts.tsv" --plain-tsv "$PARTIAL/plain.tsv" \
  --encrypted "$ENC_FLAG" --filestore-entries "$FS_ENTRIES" \
  --immutable-requested "$ISMS_BACKUP_IMMUTABLE" --immutable-result "$IMMUTABLE_RESULT" >/dev/null \
  || die 11 "manifest generation failed"
rm -f -- "$PARTIAL/modules.tsv" "$PARTIAL/counts.tsv" "$PARTIAL/plain.tsv"
(cd "$PARTIAL" && sha256sum -c --quiet SHA256SUMS) || die 11 "SHA256SUMS self-check failed"

# ---------------------------------------------------------------- primary: publish and verify
mv -- "$PARTIAL" "$FINAL"
PARTIAL=""
(cd "$FINAL" && sha256sum -c --quiet SHA256SUMS) || die 11 "primary post-write verification failed"
touch "$FINAL/COMPLETE"
log "primary ok: $FINAL"
log "sha256 of SHA256SUMS: $(sha256sum "$FINAL/SHA256SUMS" | cut -c1-64)"

# ---------------------------------------------------------------- secondary local copies
IFS=':' read -r -a COPY_LIST <<< "$ISMS_BACKUP_COPY_DIRS"
for dir in "${COPY_LIST[@]}"; do
  [[ -n "$dir" ]] || continue
  [[ "$dir" == /* ]] || { log "copy target must be absolute: $dir"; COPY_FAILURES=$((COPY_FAILURES+1)); continue; }
  if ! mountpoint -q -- "$dir" || [[ "$(stat -Lc %d -- "$dir")" == "$(stat -Lc %d -- "$ISMS_BACKUP_ROOT")" ]]; then
    log "copy target is not a mounted, separate filesystem: $dir"
    COPY_FAILURES=$((COPY_FAILURES+1))
    continue
  fi
  target="$dir/$ISMS_DB_NAME/$TS"
  if ! { mkdir -p -- "$dir/$ISMS_DB_NAME" && mkdir -- "$target.partial"; } 2>/dev/null; then
    log "copy target unavailable: $dir"; COPY_FAILURES=$((COPY_FAILURES+1)); continue
  fi
  if cp -p -- "$FINAL"/* "$target.partial/" \
     && (cd "$target.partial" && sha256sum -c --quiet SHA256SUMS) \
     && mv -- "$target.partial" "$target" && touch "$target/COMPLETE"; then
    log "copy ok: $target"
  else
    rm -rf -- "$target.partial"
    log "copy FAILED or not verified: $target"
    COPY_FAILURES=$((COPY_FAILURES+1))
  fi
done

# ---------------------------------------------------------------- rsync-over-ssh target
if [[ -n "$ISMS_BACKUP_RSYNC_TARGET" ]]; then
  if [[ "$ISMS_BACKUP_RSYNC_TARGET" =~ ^([^:/]+):(/[^[:space:]]+)$ ]]; then
    rhost="${BASH_REMATCH[1]}"; rpath="${BASH_REMATCH[2]%/}"
    rdir="$rpath/$ISMS_DB_NAME"
    rfinal="$rdir/$TS"
    SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=yes)
    if "${SSH[@]}" "$rhost" "mkdir -p '$rdir' && rm -rf '$rfinal.partial' && mkdir '$rfinal.partial'" \
       && rsync -a --partial -e "ssh -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=yes" "$FINAL/" "$rhost:$rfinal.partial/" \
       && "${SSH[@]}" "$rhost" "cd '$rfinal.partial' && sha256sum -c --quiet SHA256SUMS && mv '$rfinal.partial' '$rfinal' && touch '$rfinal/COMPLETE'"; then
      log "rsync ok: $rhost:$rfinal"
    else
      "${SSH[@]}" "$rhost" "rm -rf '$rfinal.partial'" || true
      log "rsync FAILED or not verified: $rhost:$rfinal"
      COPY_FAILURES=$((COPY_FAILURES+1))
    fi
  else
    log "ISMS_BACKUP_RSYNC_TARGET must look like user@host:/absolute/path without quotes"
    COPY_FAILURES=$((COPY_FAILURES+1))
  fi
fi

# ---------------------------------------------------------------- retention
RET_FAIL=0
python3 -I "$TOOL" retention --root "$ISMS_BACKUP_ROOT" --db "$ISMS_DB_NAME" \
  --daily "$ISMS_BACKUP_KEEP_DAILY" --weekly "$ISMS_BACKUP_KEEP_WEEKLY" --keep "$TS" || RET_FAIL=1
for dir in "${COPY_LIST[@]}"; do
  [[ -n "$dir" && -d "$dir/$ISMS_DB_NAME" ]] || continue
  python3 -I "$TOOL" retention --root "$dir" --db "$ISMS_DB_NAME" \
    --daily "$ISMS_BACKUP_KEEP_DAILY" --weekly "$ISMS_BACKUP_KEEP_WEEKLY" --keep "$TS" || RET_FAIL=1
done
if [[ -n "$ISMS_BACKUP_RSYNC_TARGET" && "$ISMS_BACKUP_RSYNC_TARGET" =~ ^([^:/]+):(/[^[:space:]]+)$ ]]; then
  rhost="${BASH_REMATCH[1]}"; rpath="${BASH_REMATCH[2]%/}"
  ssh -o BatchMode=yes -o ConnectTimeout=20 "$rhost" \
    "python3 -I - --root '$rpath' --db '$ISMS_DB_NAME' --daily $ISMS_BACKUP_KEEP_DAILY --weekly $ISMS_BACKUP_KEEP_WEEKLY --keep '$TS'" \
    < "$TOOL" || RET_FAIL=1
fi

# ---------------------------------------------------------------- summary
DUR=$(( $(date +%s) - START_EPOCH ))
log "summary: ts=$TS duration_s=$DUR files=$(ls "$FINAL" | tr '\n' ' ')"
log "summary: sha256 manifest=$(sha256sum "$FINAL/manifest.json" | cut -c1-64)"
if (( COPY_FAILURES > 0 )); then
  log "FINISHED WITH COPY FAILURES: $COPY_FAILURES (primary backup is intact)"; exit 13
fi
if (( RET_FAIL )); then
  log "FINISHED: backup ok, retention reported failures (see lines above)"; exit 14
fi
log "FINISHED OK"
exit 0
