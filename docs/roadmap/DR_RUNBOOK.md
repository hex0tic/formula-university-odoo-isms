# Disaster recovery runbook and security test status (SEC-03, SEC-04)

Scope: Phase 5 tasks SEC-03 (offsite or immutable backups, DR) and SEC-04 (security regression tests).
Tools: `odoo/scripts/backup/` (see its README), test addon `odoo/addons/university_security_tests/`.
Environment for all measurements below: staging only (database `orgil_isms_stage`, containers `isms-db` and `isms-stage-odoo`, volume `isms-stage-data`). Production database `orgil_isms` and containers `isms-odoo` and `isms-https` were NOT touched. Backups were written only under `<session-tmp>/backup-test/` (session temp directory named in the brief). Secrets: the encryption key was generated into a 0600 file outside the repository and is not recorded here.

Labels: **VERIFIED** (run and measured here), **NOT VERIFIED** (not run or not possible in this environment).

## 1. Roles

| Role | Responsibility |
| --- | --- |
| Operator (system administrator with Docker access) | runs `backup.sh` on schedule, keeps the key file, checks exit codes |
| Restore verifier (CISO or delegated analyst) | runs `restore_verify.sh` monthly and after any backup-tool change, records the report |
| CISO | approves retention values, key custody, and any restore into a non-throwaway database |
| Offsite host owner | operates the rsync target and its disk or WORM media; NOT VERIFIED (no offsite host exists in this environment) |

A production restore into `orgil_isms` is not a verification step. It needs explicit CISO approval and a fresh backup taken first.

## 2. Backup procedure

1. Confirm the staging-or-production target: `ISMS_DB_NAME`, `ISMS_DB_CONTAINER`, `ISMS_ODOO_CONTAINER`.
2. Set `ISMS_BACKUP_ROOT` outside the repository, a second copy in `ISMS_BACKUP_COPY_DIRS` or `ISMS_BACKUP_RSYNC_TARGET`, and `ISMS_BACKUP_KEY_FILE` (mode 0400 or 0600).
3. Run `odoo/scripts/backup/backup.sh`. Exit 0 means the primary and all configured copies passed hash verification. Exit 13 means a copy failed but the primary is intact: raise an incident.
4. Schedule (cron example, NOT INSTALLED): `0 3 * * * ISMS_... /path/odoo/scripts/backup/backup.sh >> /var/log/isms-backup.log 2>&1`. Record the actual schedule here once installed. The RPO bound equals this interval.
5. Monitor: a missing `COMPLETE` file in the newest directory or a non-zero exit is an alert.

## 3. Restore verification procedure

1. `ISMS_BACKUP_KEY_FILE=... odoo/scripts/backup/restore_verify.sh --latest-from <ROOT> --db <db> --report <file>`.
2. The script checks stored hashes, decrypts, checks plaintext hashes, restores into `isms_restore_verify_*`, compares installed modules and row counts of 21 tables with the manifest, verifies every `ir_attachment` store file SHA-1 against `checksum`, then drops the throwaway database and filestore.
3. Record RPO_observed (backup age) and RTO_measured (restore start to verified), and attach the JSON report to the evidence folder.

## 4. Full restore into production (emergency, not rehearsed)

Procedure outline only, NOT VERIFIED on production: stop the Odoo container; take a fresh backup of the damaged state if it is still readable; restore the chosen dump into a new database name; restore the filestore into the matching path; point `dbfilter` at the restored name after the CISO approves; start Odoo; run the security tests against the restored system; document the data-loss window. Each of these steps requires the CISO's approval (master prompt section 8).

## 5. Measured results (staging, 2026-11-26)

Backups (both encrypted, AES-256-CBC PBKDF2 310000 iterations, run on the same host, two local target directories standing in for offsite):

| Run | Directory | Manifest created (UTC) | Dump bytes (plain / stored) | Filestore bytes (plain / stored) | Duration |
| --- | --- | --- | --- | --- | --- |
| 1 | `local/orgil_isms_stage/20261126T114823Z` | 20261126T114842Z | 4877733 / 4877760 | 12761664 / 12761696 (442 entries) | 19 s (includes copy and retention) |
| 2 | `local/orgil_isms_stage/20261126T115306Z` | 20261126T115322Z | 4877733 / 4877760 | 12761664 / 12761696 | 16 s |

Run 2 manifest hashes (`20261126T115306Z`; hashes are integrity values, not secrets):

| File | Stored SHA-256 | Plaintext SHA-256 |
| --- | --- | --- |
| `db.dump.enc` | f87faa7bc7b3d2ea898cbe9f4f17821a3a7eaa2bc7915ec2d827b17d01eb463c | 891a035169adcb73211bc6778629ded2b0403aada1eb5c9c3f09015be27be529 |
| `filestore.tar.gz.enc` | 4452f1e15fc7d3a94c25b194b894388f1319d33486033ec820ae855b7a2c8111 | 6ea1f5f9b946cc91836136170efe84d94676a61f90cc62d73be61c1bcfa9007f |
| `manifest.json` | be1808aa68c1bdca2e09f933dd34d60fbe036ec09ef0317060c54b2cd822c6f9 | n/a |

Manifest content at run 2: Odoo release `18.0-20261112`, base module `18.0.1.3`, PostgreSQL 16.15, 69 installed modules, 442 filestore entries, row counts (staging): isms_asset 16, isms_risk 15, isms_control 93, isms_incident 22, isms_policy 4, isms_audit_log 641, isms_threat 14, isms_vulnerability 14, isms_finding 2, isms_policy_ack 11, campus_student 3, campus_course 2, campus_offering 2, campus_enrollment 3, campus_grade_change 2, access_review 2, helpdesk_ticket 26, res_users 27, ir_attachment 207, isms_capa 0, isms_evidence 0.

Restores (`restore_verify.sh`, latest backup, throwaway DB `isms_restore_verify_final`):

| Metric | Run 1 (`isms_restore_verify_run1`) | Final run (`isms_restore_verify_final`) |
| --- | --- | --- |
| Stored + plaintext hashes | match | match |
| Modules match | yes (69) | yes |
| Row counts (21 tables) | match | match (0 mismatches) |
| Attachments checked (SHA-1 = checksum) | 206 ok, 0 missing, 0 mismatch | 206 ok, 0 missing, 0 mismatch; 1 row without store file (DB-only) |
| pg_restore time | not logged (run 1 before timing lines) | 75.3 s |
| Filestore extraction | not logged | 1.7 s |
| Restore total (`restore_seconds`) | 73.7 s | 78.5 s |
| Verification (`verify_seconds`) | 2.2 s | 3.1 s |
| **RTO measured** (start to verified) | **75.9 s** | **81.6 s** |
| **RPO observed** (age of backup at verification) | 155 s | 92 s |

Interpretation: RTO for the staging database of 51 MB (dump 4.9 MB) is about 1.5 minutes, dominated by `pg_restore` (single-job restore, 1 DB). The measured RPO is the age of the chosen backup, not the schedule. The schedule-based RPO bound is NOT VERIFIED because no cron job exists yet.

Negative and failure-path tests (all VERIFIED):

| Test | Result |
| --- | --- |
| Restore target `orgil_isms` | refused, exit 1, no Docker call |
| Restore target equal to source `orgil_isms_stage` | refused, exit 1 |
| Restore target with shell metacharacters | refused, exit 1 |
| Restore from missing backup directory | refused, exit 1 |
| Restore target already existing | refused, exit 1 (test DB created and dropped) |
| Corrupted stored file (one byte changed) | rejected at the hash step, exit 4; throwaway objects removed (none created) |
| Second backup while lock held by another process | exit 3 (lock file `.backup.lock`) |
| Retention, same-day: second backup prunes the older same-day backup in both targets | VERIFIED (`pruned` list in both targets) |
| Retention, multi-day synthetic set (30 daily + 1 extra, daily 7 / weekly 4) | 31 directories to 9 kept (7 days + 2 extra weeks), 22 pruned; dry-run matches apply |
| `chattr +i` requested (`--immutable`) | NOT applied: `Operation not permitted` (run as uid 1000, not root); recorded in manifest, backup still succeeded |
| Copy target unavailable (rsync or missing dir) | counted as copy failure, exit 13 path implemented; see section 6 for rsync |

## 6. NOT VERIFIED

- Real offsite host and rsync-over-ssh target: sshd is not running on this host (`ssh localhost` refused). The rsync branch of `backup.sh` and remote retention are implemented but NOT executed.
- WORM or object-lock storage and immutability: `chattr +i` needs root; not applied here.
- Scheduled backups (cron or systemd timer): none installed. RPO schedule bound NOT VERIFIED.
- Production backup and restore: not run, by rule (production DB not touched).
- Restore into an Odoo instance (web login, attachments visible in UI, cron): only database and filestore checks were run; the Odoo server was not started against the restored DB.
- Encryption key custody and rotation: a test key was generated for staging only.
- Backup taken while the system is in use: staging was idle; live consistency NOT VERIFIED.

## 7. SEC-04 security regression suite

Addon: `odoo/addons/university_security_tests/` (test-only, no models; depends on `university_isms`, `campus_university`, `university_access_review`). Tests call the ORM with `with_user` as real low-privilege users, without sudo. Each test documents the attack it simulates in its docstring.

Run (throwaway database created and dropped by the staging test script):

    MODULES=university_security_tests TAGS=/university_security_tests odoo/scripts/run-tests.sh (staging variant: scratchpad stage-test.sh)

Result of the final run (log `<session-tmp>/stage-test-logs/isms_ci_20261126200900_272097.log`): **22 tests, 22 passed, 0 failed, 0 errors** (3922 queries, 11.3 s).
Earlier runs: run 1 (`...200222...`) had 2 errors caused by test code (export refusal raised UserError, not handled) and an empty CSRF route inventory (routes are only generated for installed modules). Both were fixed; no assertion was weakened. Run 2 (`...200552...`) passed 22/22 before the last two test-code corrections (rule xmlid and a timestamp assertion); run 3 passed 22/22 after them.

| Test | Attack simulated | Result |
| --- | --- | --- |
| test_01 | plain user adds self to Administrator group | PASS |
| test_02 | student grants CISO group to another account | PASS |
| test_03 | plain user creates account with admin group | PASS |
| test_04 | plain user inserts ACL or edits record rule | PASS |
| test_05 | non-manager applies access review, opens review of another user | PASS |
| test_06 | student reads other student's enrollment score (IDOR) | PASS |
| test_07 | lecturer reads roster of another offering | PASS |
| test_08 | reporter reads another reporter's incident | PASS |
| test_09 | owner writes another owner's asset | PASS |
| test_10 | search_count, read_group, export_data, name_search side channels | PASS (export refused entirely for students) |
| test_11 | registrar approves own grade change | PASS |
| test_12 | lecturer approves own grade change | PASS |
| test_13 | stale revision approval after another change applied | PASS (ValidationError) |
| test_14 | direct score or revision write, forged context flag | PASS |
| test_15 | incident close by analyst or reporter | PASS |
| test_16 | policy approve by submitter or auditor | PASS |
| test_17 | risk accept by analyst or owner, forged accepted_by_id | PASS |
| test_18 | back-dating protected timestamps, forged internal token in context | PASS |
| test_19 | unlink of incident by reporter or analyst | PASS |
| test_20 | write or unlink of isms.audit.log by CISO, auditor, superuser | PASS (ORM level only) |
| test_21 | csrf=False on POST routes with auth user or public (source AST inventory) | PASS |
| test_22 | export of res.users password and TOTP seed by normal user | PASS (export refused entirely) |

CSRF route inventory (test_21, AST scan of custom addon sources, tests and static excluded): 5 `http.route` calls, all in the vendored OCA addon `helpdesk_mgmt` (`controllers/main.py:14`, `:54`, `:111`; `controllers/myaccount.py:33`, `:168`). All use the default `csrf=True`. None in the repository-authored addons. Two are `auth=user` and one is `auth=public` GET with access token.

### Real vulnerabilities found by SEC-04

None failed in the final run. This is a statement about the tests written here, not a proof of absence. Observations that are NOT covered or are weaker than they look:

- Audit log protection (test_20) is ORM-level only. The `odoo` role is a PostgreSQL superuser and can alter `isms_audit_log` without trace (BASELINE section 6.2). This is a known design gap for SEC-02, not a test failure.
- Test coverage gap: `helpdesk.ticket` confidentiality for incident-linked tickets, the `university_isms_helpdesk` bridge, and `campus_isms_bridge` were not tested (they are not in this addon's depends).
- The password and TOTP tests verify that export and read are refused for normal users. Export is refused as a whole, so the test cannot tell whether a partial column filter exists.
- Exports and read-group checks were run with one student and one reporter fixture. Larger data and other roles (auditor, analyst) were not exercised.
- Routes: only the source scan for `csrf=False` was asserted. Runtime routing for installed modules was not checked, because the routing generator yields nothing for modules that are not installed in the test database.

## 8. Limitations (summary)

- Offsite host, rsync-over-ssh and remote retention: implemented, not executed (no sshd).
- WORM, object lock and `chattr +i`: attempted, not applied (not root).
- Scheduled backups: not installed; RPO schedule bound NOT VERIFIED.
- Production (`orgil_isms`, `isms-odoo`, `isms-https`) was not backed up, restored or tested.
- Restore is database and filestore level; the Odoo web application was not started against the restored database.
