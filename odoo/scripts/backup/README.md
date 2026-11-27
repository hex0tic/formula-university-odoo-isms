# ISMS backup and restore verification (SEC-03)

Tools: `backup.sh`, `restore_verify.sh`, `isms_backup_tool.py` (Python 3 standard library only, no new dependencies).
Procedure, roles, measured results and what is NOT VERIFIED: `docs/roadmap/DR_RUNBOOK.md`.

## What a backup contains

Directory `<ROOT>/<db>/<UTC timestamp>/`:

| File | Content |
| --- | --- |
| `db.dump` or `db.dump.enc` | `pg_dump -Fc --no-owner --no-acl` of the database |
| `filestore.tar.gz` or `.enc` | Odoo filestore (attachments), read from the Odoo container |
| `manifest.json` | db name, Odoo release and base module version, PostgreSQL version, installed module list with versions (`ir_module_module`), row counts of key ISMS/campus tables, stored and plaintext SHA-256 and sizes, encryption parameters, immutability result, UTC timestamp |
| `SHA256SUMS` | SHA-256 of the stored files and of `manifest.json` (`sha256sum -c` format) |
| `COMPLETE` | written last; retention and restore only consider directories that have it |

Encryption: `openssl enc -aes-256-cbc -pbkdf2 -iter 310000 -salt` with `-pass file:<key file>`.
The key is read from the file, never printed, never stored in the repository. The key file must be mode 0400 or 0600.
Plaintext dump files are deleted after encryption. The plaintext digests stay in the manifest so a restore can verify decrypted data.

## Usage

```
# backup (defaults match odoo/docker-compose.yml: containers isms-db and isms-odoo, DB orgil_isms)
ISMS_BACKUP_ROOT=/srv/backups/isms \
ISMS_BACKUP_COPY_DIRS=/mnt/offsite-disk/isms \
ISMS_BACKUP_RSYNC_TARGET=backup@offsite.example:/srv/isms-backups \
ISMS_BACKUP_KEY_FILE=/root/.config/isms/backup.key \
odoo/scripts/backup/backup.sh [--immutable]

# restore into a NEW throwaway database, verify, drop it
ISMS_BACKUP_KEY_FILE=/root/.config/isms/backup.key \
odoo/scripts/backup/restore_verify.sh --latest-from /srv/backups/isms --db orgil_isms [--target-db isms_restore_verify_x] [--keep] [--report FILE]
```

Environment variables (all optional except where noted):

| Variable | Default | Meaning |
| --- | --- | --- |
| `ISMS_DB_NAME` | `orgil_isms` | database to back up |
| `ISMS_DB_CONTAINER` | `isms-db` | PostgreSQL container (`pg_dump`, `psql`, `pg_restore` run inside it) |
| `ISMS_DB_USER` | `odoo` | PostgreSQL role |
| `ISMS_ODOO_CONTAINER` | `isms-odoo` | Odoo container, mounts the data volume at `/var/lib/odoo` |
| `ISMS_FILESTORE_PATH` | `/var/lib/odoo/filestore/<db>` | filestore path inside the Odoo container (backup) |
| `ISMS_FILESTORE_ROOT` | `/var/lib/odoo/filestore` | filestore root inside the Odoo container (restore) |
| `ISMS_BACKUP_ROOT` | `/var/backups/isms` | primary root; must be outside the repository (enforced) |
| `ISMS_BACKUP_COPY_DIRS` | empty | colon-separated mountpoints on separate filesystems (mounted backup disk or NAS). Do not list an ordinary directory or a path below the mountpoint. |
| `ISMS_BACKUP_RSYNC_TARGET` | empty | `user@host:/absolute/path`, copied with rsync over SSH (BatchMode, pinned host key). Both endpoints need rsync. |
| `ISMS_BACKUP_KEY_FILE` | empty | encryption key file; if empty, backups are NOT encrypted |
| `ISMS_BACKUP_KEEP_DAILY` | `7` | newest backup of each of the last N days is kept |
| `ISMS_BACKUP_KEEP_WEEKLY` | `4` | newest backup of each of the last N ISO weeks is kept |
| `ISMS_BACKUP_IMMUTABLE` | `0` | `1` (or `--immutable`) tries `chattr +i` on stored files; failure is reported, not fatal |
| `ISMS_RESTORE_WORK_DIR` | `/var/tmp` | plaintext work dir for restore, removed on exit |

## Safety properties

- Lock file `<ROOT>/.backup.lock` (`flock -n`): a second concurrent run exits 3.
- Every copy is written to `<name>.partial`, verified with `sha256sum -c` (remote: over ssh), then renamed. A failed copy never leaves a `COMPLETE` directory.
- Work directories are removed on failure, including any plaintext dump.
- Reads are read-only: psql sessions set `default_transaction_read_only=on` through `PGOPTIONS`.
- `restore_verify.sh` only creates databases named `isms_restore_verify_*`. It refuses `orgil_isms`, the source database name, and any existing database name, before touching Docker.
- Restore never writes to the source database. The throwaway database and its filestore directory are dropped at exit unless `--keep` is given.

## Exit codes

`backup.sh`: 0 ok; 1 configuration error; 2 preflight failed; 3 lock held; 10 dump or filestore export failed; 11 manifest or hash failure; 12 encryption failure; 13 copy or post-copy verification failed (the primary backup is still intact); 14 retention failed.

`restore_verify.sh`: 0 verified; 1 usage or refused target; 2 preflight failed; 4 stored-file hash mismatch; 12 decryption or plaintext hash mismatch; 15 restore failed; 16 verification mismatch (modules, row counts, attachments); 17 cleanup failed.

## Retention rule

Per database and per root: the newest backup of each of the last `KEEP_DAILY` UTC days and of each of the last `KEEP_WEEKLY` ISO weeks is kept (union of both sets). The backup just created is always kept. Everything else is removed. Removal of an immutable file fails, which is reported (exit 14 / `failed` list).

## Known limits

- The row counts and the dump are taken at different moments. Run backups while the system is idle, or accept a small inconsistency; the restore verification compares the restored counts with the manifest counts and will show a difference if data changed.
- Filestore and dump are not taken in one transaction. A file added between the two steps can appear as an orphan (harmless); a file referenced by the dump but missing from the archive is detected by the attachment check.
- `chattr +i` needs root (CAP_LINUX_IMMUTABLE) and a filesystem that supports it. Real WORM protection needs WORM media or object-lock storage: NOT VERIFIED here.
- Remote retention runs `isms_backup_tool.py` over ssh on the offsite host (requires `python3` there).

Secondary targets require encryption. A missing mount or one on the primary filesystem is reported as a copy failure; the primary archive is still published and verified. Separate filesystems may still share a device or location; verify separation with the storage owner before recording an offsite backup.
