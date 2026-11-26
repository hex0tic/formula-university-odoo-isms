# Phase 0 Baseline

Scope: BASE-01, BASE-02, BASE-07, BASE-08. Documentation only. No addon, database, container, git configuration or history was changed. Paths are relative to the repository root unless stated otherwise.

Verification labels: **VERIFIED** (checked by code reading or a read-only query in this pass), **NOT VERIFIED** (not checked or not runnable here).

## 1. Repository identity (BASE-01)

| Item | Value |
| --- | --- |
| Branch | `formula-erp` |
| HEAD commit | `2f68f1246fc7f7423e07fb683197ca83dac326a8` (short `2f68f12`, "Add user access review module, LAN HTTPS setup and final report") |
| Working tree at start | clean (`git status --short` empty) |
| Odoo | 18.0 Community (`odoo:18.0` image, `version_info = (18, 0, 0, FINAL)` in the staging container); not digest-pinned |
| PostgreSQL | `postgres:16-alpine` in compose; staging server reports 16.15 |
| Compose services | `db` (isms-db), `odoo` (isms-odoo, 127.0.0.1:8069 by default), `https` (nginx 1.30.5, LAN:8443), `turn` (coturn 4.19.1, `network_mode: host`) |
| Staging runtime | container `isms-stage-odoo`, database `orgil_isms_stage`, `dbfilter=^orgil_isms_stage$`, `list_db=False`, `proxy_mode=False`, `workers=0`, `max_cron_threads=0`, `without_demo=all` (non-secret keys read from `/etc/odoo/odoo.conf`) |
| Production | database `orgil_isms` / container `isms-odoo` was NOT queried or touched |

Whether the staging container runs exactly the HEAD code is NOT VERIFIED.

### 1.1 Addons

| Addon | Version | Depends | Application | Purpose | Models (`_name`) and inherited models |
| --- | --- | --- | --- | --- | --- |
| `university_isms` | 18.0.1.1.0 | base, mail, hr, project | yes | ISO/IEC 27001 ISMS: assets, threats, vulnerabilities, risks, Annex A controls and SoA, incidents, policies, audit log, monitoring, management-review PDF | `isms.asset`, `isms.threat`, `isms.vulnerability`, `isms.risk`, `isms.control`, `isms.incident`, `isms.policy`, `isms.policy.ack`, `isms.audit.log`, `isms.audit.mixin`, `isms.monitoring`, report `university_isms.report_management_review`. Inherits `res.users`, `project.task`, `res.groups`. |
| `campus_university` | 18.0.1.0.0 | base, mail | yes | Academic records, grade-change request and independent approval | `campus.program`, `campus.student`, `campus.course`, `campus.offering`, `campus.enrollment`, `campus.grade.change` |
| `campus_isms_bridge` | 18.0.1.1.0 | campus_university, university_isms | no | Audit mixin on campus models; grade-change links to ISMS asset/incident; makes all campus users ISMS Reporters | inherits `campus.student`, `campus.enrollment`, `campus.grade.change` |
| `university_isms_helpdesk` | 18.0.1.0.0 | university_isms, helpdesk_mgmt | no | Two-way sync of ISMS incidents and OCA helpdesk tickets | inherits `isms.incident`, `helpdesk.ticket` |
| `university_isms_stock` | 18.0.1.1.0 | university_isms, stock | no | Links ISMS assets to Inventory product, lot/serial and location | inherits `isms.asset`, `stock.lot` |
| `university_isms_inventory_catalog` | 18.0.1.1.0 | university_isms_stock | no | Read-only ISMS catalog in Inventory product views | inherits `product.product` |
| `university_access_review` | 18.0.1.0.0 | base, mail, hr, project, university_isms | no (False) | Per-user access review: model, project, channel and business-action visibility; group apply | `access.review` and 5 line models; inherits `res.users` |
| `campus_rtc_fix` | 18.0.1.0.0 | mail | no | Frontend-only patch to create media transceivers before first WebRTC negotiation (`static/src/rtc_initialization.js`) | none |
| `helpdesk_mgmt` | 18.0.1.19.5 | mail, portal | yes | Vendored OCA helpdesk (OCA/helpdesk 18.0, commit `9fbf485f7ab7961fd06250965990523e05e00ecd`, AGPL-3; see `THIRD_PARTY.md`). 94 files, its own tests not part of the default run. | helpdesk ticket, team, stage, category, channel, tag |

Custom model code size (lines): `university_isms/models/*.py` 1,568 total (incident 300, risk 379, monitoring 180, policy 170, res_users 129, audit 176); `campus_university/models/academic.py` 294; `university_access_review/models/access_review.py` 375; `university_isms_helpdesk/models/incident_helpdesk.py` 133.

Tests in the default regression run (`odoo/scripts/run-tests.sh`, `MODULES` default): campus_university 11, campus_isms_bridge 4, university_isms 25, university_isms_stock 1, university_isms_helpdesk 6 = 47. Not in the default run: `university_access_review` (5 `def test_` methods), `campus_rtc_fix` (0 tests), `helpdesk_mgmt` own tests, `university_isms_inventory_catalog` (0 tests).

## 2. RBAC map (BASE-02)

### 2.1 Custom res.groups (11 total)

| XML id | Name | Category | Implies (effective) |
| --- | --- | --- | --- |
| `university_isms.group_isms_reporter` | 1. Мэдээлэгч (Reporter) | ISMS | `base.group_user` |
| `university_isms.group_isms_asset_owner` | 2. Asset Owner | ISMS | Reporter |
| `university_isms.group_isms_analyst` | 4. Security Analyst | ISMS | Asset Owner, `project.group_project_user`, (via helpdesk bridge) `helpdesk_mgmt.group_helpdesk_user` |
| `university_isms.group_isms_auditor` | 3. Internal Auditor (read-only) | ISMS Audit (separate category) | Reporter |
| `university_isms.group_isms_manager` | 5. CISO | ISMS | Analyst, Auditor |
| `campus_university.group_campus_user` | Campus Catalog Reader | none | `base.group_user`; (via bridge) `university_isms.group_isms_reporter` |
| `campus_university.group_campus_student` | Campus Student | Campus | Catalog Reader |
| `campus_university.group_campus_lecturer` | Campus Lecturer | Campus | Catalog Reader |
| `campus_university.group_campus_registrar` | Campus Registrar | Campus | Catalog Reader |
| `campus_university.group_campus_auditor` | Campus Academic Auditor | Campus | Catalog Reader |
| `campus_isms_bridge.group_campus_isms_auditor` | Campus and ISMS Auditor | none | Campus Auditor, ISMS Auditor (0 users) |

Core behaviour: `base.group_user` implies `base.group_no_one` (Technical Features) in core `base/security/base_groups.xml:51`. Therefore all internal users, including campus users, hold Technical Features. Its effect on debug-mode access is NOT VERIFIED.

Users configured in XML: `university_isms` assigns `group_isms_reporter` to `base.user_admin` and `group_isms_manager` to `base.user_root` (`isms_security.xml`). Migration 18.0.1.1.0 later removed the CISO group from `admin` (audit doc section 3.3); current DB confirms.

### 2.2 Record rules (25 custom, plus 2 helpdesk)

| Model | Rule (group, domain) | Effect |
| --- | --- | --- |
| `isms.asset` | Owner (Asset Owner): `owner_id` or `custodian_id` = user, write only | Owner write restricted; read unrestricted for all Asset Owners |
| `isms.asset` | Analyst: `(1=1)` | Analyst write/create/unlink unrestricted |
| `isms.risk` | Asset Owner: `owner_id` or `asset_ids.owner_id` = user | read limited |
| `isms.risk` | Analyst, Auditor: `(1=1)` | |
| `isms.incident` | Reporter: `reporter_id` = user | Reporter sees own incidents only |
| `isms.incident` | Asset Owner: `asset_ids.owner_id` = user, read-only | |
| `isms.incident` | Analyst, Auditor: `(1=1)` | |
| `isms.policy` | Reporter: `state = approved` | Reporter sees approved policies only |
| `isms.policy` | Analyst, Auditor: `(1=1)` | |
| `isms.policy.ack` | Reporter: `user_id` = user | |
| `isms.policy.ack` | Analyst, Auditor: `(1=1)` | |
| `campus.student` | Student: `user_id` = user; Lecturer: `enrollment_ids.offering_id.lecturer_id` = user; Registrar and Campus Auditor: all | |
| `campus.enrollment` | Student: `student_id.user_id` = user; Lecturer: `offering_id.lecturer_id` = user; Registrar and Auditor: all | |
| `campus.grade.change` | Student: own student; Lecturer: `requester_id` = user; Registrar and Auditor: all | |
| `campus.offering` | Student: enrolled; Lecturer: `lecturer_id` = user; Registrar and Auditor: all | |
| `helpdesk.ticket` (helpdesk_security.xml) | ISMS Analyst or Auditor: all; others: no ISMS link or own reporter | incident confidentiality |
| `helpdesk.ticket` | Auditor: `isms_incident_id != False`, read-only | |

No record rules in `campus_isms_bridge` or `university_access_review`. Those models rely on ACL and Python guards.

### 2.3 ACL summary (`ir.model.access.csv`; R=Reporter, O=Asset Owner, A=Analyst, Au=ISMS Auditor, M=CISO; `r w c d` = granted)

ACLs are unioned along implications, so an Analyst also has Owner and Reporter ACLs, and a CISO also has Analyst and Auditor ACLs.

| Model | R | O | A | Au | M | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `isms.asset` | - | r w | r w c | r | r w c d | |
| `isms.threat` | - | r | r w c | r | r w c d | |
| `isms.vulnerability` | - | r | r w c | r | r w c d | |
| `isms.risk` | - | r | r w c | r | r w c d | owner read rule applies |
| `isms.control` | r | - | r w | r (via Reporter) | r w c | Analyst: no create |
| `isms.incident` | r w c | r | r w c | r | r w c d | ISMS write guards in `incident.py` |
| `isms.policy` | r | - | r w c | r | r w c d | |
| `isms.policy.ack` | r c | - | - | r | - | CISO ACL absent; rules cover analyst and auditor |
| `isms.audit.log` | - | - | - | r | - | `base.group_system` read only; write and unlink raise `UserError` in ORM |
| `campus.program` | r (Catalog) | | | | | Registrar rwc |
| `campus.course` | r (Catalog) | | | | | Registrar rwc |
| `campus.student` | r (Student, Lecturer, Auditor) | | | | | Registrar rwc |
| `campus.offering` | r (Student, Lecturer, Auditor) | | | | | Registrar rwc |
| `campus.enrollment` | r (Student, Lecturer, Auditor) | | | | | Registrar rwc, ORM guards on score |
| `campus.grade.change` | r (Student), rwcd (Lecturer) | | | r (Auditor) | | Registrar rwcd |
| `access.review*` (6 models) | | | | | | `base.group_erp_manager` rwcd only |
| `helpdesk.ticket` | | | | Auditor r | | helpdesk_mgmt own ACLs not analyzed |
| `product.product` / `product.template` | | | Analyst r | Auditor r | | read only |

### 2.4 Server-side `has_group` and authority checks (file:line)

| Check | Location |
| --- | --- |
| Registrar-only grade operations: `_require_registrar` | `campus_university/models/academic.py:12-14` (definition); used at 121 (enrollment create), 144 (approval path), 274 (approve), 285 (reject) |
| Grade write blocked unless internal authority token | `academic.py:127-131` (`_GRADE_AUTHORITY` object, not a context string) |
| Grade-change create: lecturer or registrar only | `academic.py:208-213` |
| Lecturer may request only for own offering | `academic.py:226-228` |
| Self-approval blocked | `academic.py:147-148`; SQL constraint `independent_approval` at `academic.py:188-191` |
| Analyst-only investigate, resolve | `incident.py:267-270`, `277-279` via `_require_group` (`incident.py:257-259`) |
| CISO-only close, reopen | `incident.py:288-290`, `296-298` |
| Reporter-only field restriction | `incident.py:237-242` (`_REPORTER_FIELDS`, `_is_isms_team` at 202-203) |
| Link fields (asset, risk, control) restricted to ISMS team | `incident.py:211-215` |
| Analyst required for next risk stage | `risk.py:227-229`, `231-245` |
| CISO required for accept-risk | `risk.py:336-338` |
| Residual acceptance: owner or CISO | `risk.py:257-266` |
| Policy submit: Analyst | `policy.py:109-111` |
| Policy approve, retire: CISO | `policy.py:105-107`, `114-116` |
| Policy read-side report gating: Analyst or Auditor | `monitoring.py:170-172` |
| Access review: `erp_manager` required | `access_review.py:83-85`, `267-270`, `369-370`; no-self and root/admin protection at `access_review.py:267-285` |
| Access review: business-action matrix (display only) | `access_review.py:37-56`, evaluated at `access_review.py:212-236` |
| Internal workflow bypass uses Python token (not a context string) | `audit.py:91-96` (`ISMS_TRANSITION_TOKEN`) |
| Helpdesk sync authority token | `university_isms_helpdesk/models/incident_helpdesk.py:7`, guards at 88-101 |
| Asset-link groups on stock lot and campus grade change | `university_isms_stock/models/isms_asset.py` (`groups=` on `isms_asset_ids`), `campus_isms_bridge/models/academic_audit.py` (`groups=` on `isms_asset_id`, `isms_incident_id`) |

`sudo()` / `su=True` occurrences in custom model code: `university_isms` 27, `university_access_review` 10, `campus_university` 1 (grade write, authority-guarded), `university_isms_helpdesk` 2, `university_isms_stock` 1, `campus_isms_bridge` 0. Total 41 (grep count, `models/` only). The monitoring KPI path uses `self.env(su=True)` at `monitoring.py:86`. Review of each sudo call is NOT VERIFIED.

## 3. Workflows and state machines (BASE-02)

### 3.1 Grade change (campus_university)

States: `draft` → `submitted` → `approved` | `rejected`.

- Create: `academic.py:208-240`. Requester forced to current user; state must be draft; score, revision, approver fields rejected; offering must not be in draft state (`:229-230`).
- Direct grade edits: `CampusEnrollment.write` (`academic.py:127-131`) raises unless the call carries the process-local `_GRADE_AUTHORITY` object. RPC context values cannot forge it.
- Submit: `academic.py:262-272`; requires new score different from old.
- Approve: `academic.py:273-283` → `_apply_approved_change` (`academic.py:141-159`): registrar only; not requester; row lock `SELECT ... FOR UPDATE` on the enrollment; stale check on `grade_revision` and `score` (`:152-154`); write via authority token and `grade_revision + 1` (`:155-158`).
- Reject: `academic.py:284-295`; requester cannot reject own request.
- Invariants: `score_range` 0–100, `independent_approval` SQL check (`academic.py:188-192`).
- Reason minimum 10 characters (`:202-206`).

### 3.2 Incident (university_isms, 5 stages)

States (`incident.py:11-17`): `incident` → `report` → `investigate` → `resolve` → `close`. Reverse transitions only `resolve`→`investigate` and `close`→`investigate` (reopen, CISO). Transition table `incident.py:193-200`.

- Write path: `incident.py:231-255`. Non-team users cannot change `state` directly except via reporter path; transitions call the action methods.
- `report` (`:262-265`): no explicit group; any user who can write may move `incident` to `report` (reporter path).
- `investigate` (`:267-275`): analyst. Requires nothing beyond state.
- `resolve` (`:277-286`): analyst; requires root cause and resolution (`:280-281`); personal-data breach requires notification note (`:282-284`).
- `close` (`:288-294`): CISO; requires lessons learned (`:291-292`).
- Closed records are locked for business fields (`:244-246`); timestamps protected (`:221`, `:234`).
- SLA: `SLA_HOURS` low 120, medium 72, high 24, critical 4 (`incident.py:25`); computed at `:115-130`.
- Helpdesk coupling: incident write triggers sync (`incident_helpdesk.py:22-26`), `_sync_helpdesk_tickets` at `:28-56`, helpdesk ticket write guard `:94-120`, stage mapping `:104-114`, delete blocked for linked tickets `:123-125`.
- Brute-force detection: `incident.py:149-165` (5 failed logins in 15 minutes); evidence incident INC-2026-0070 is in state `report`.

### 3.3 Risk lifecycle (university_isms)

States (`risk.py:48-55`): `identify` → `analyze` → `evaluate` → `respond` → `implement` → `residual`. Skipping is refused (`risk.py:158-167`).

- Gates (`risk.py:209-225`): analyze needs assets and threat or vulnerability; evaluate needs likelihood and impact; respond needs treatment; accept needs CISO; implement needs treatment-plan text or Annex A link; residual needs residual values.
- Next-stage actions require analyst (`:227-245`).
- Accept (CISO): `:336-349`. Residual accept: owner or CISO (`:257-283`), blocked while treatment tasks are open (`:269`).
- Changing assessment fields clears prior acceptance (`risk.py:134-151`; `_ASSESSMENT_FIELDS`, `_PROTECTED` at 119-121).
- Level from 5×5 matrix: `matrix_level` at `risk.py:42-46`.
- Overdue: `risk.py:195-207`.

### 3.4 Policy approval (university_isms)

States (`policy.py:30-35`): `draft` → `review` → `approved` → `retired`; reset to draft from review, approved or retired.

- Approver and approval date are protected fields (`policy.py:78`).
- Approved or retired content frozen (`policy.py:79-80`).
- Transitions table `policy.py:53-61`; submit by analyst (`:109-111`); approve by CISO (`:105-107`, `:114-122`).
- Acknowledgement: only own record (`policy.py:158-159`), only for approved policy (`:160-161`), immutable after creation (`:167-169`).

### 3.5 Audit log guarantees (see section 6)

## 4. Integrations (BASE-02)

| Integration | Mechanism | Verification status |
| --- | --- | --- |
| Helpdesk bridge | `university_isms_helpdesk`, OCA `helpdesk_mgmt` (vendored) | Test file 6 tests PASS (regression-20261118.json). Live exercise evidence `evidence/tests/live-exercise.json` PASS 2026-11-16 (INC-2026-0021, ticket 17, state closed). Staging: 26 tickets, 22 linked. |
| Stock / Inventory | `university_isms_stock`: `product_id`, `lot_id`, `stock_location_id` on `isms.asset` | 1 test PASS. Staging: 16 assets all with product, 5 with lot. |
| Inventory catalog | `university_isms_inventory_catalog`: product read for Analyst and Auditor | `evidence/tests/inventory-catalog.json` PASS, 16 records. No tests. |
| Campus bridge | `campus_isms_bridge`: audit mixin on campus models, ISMS links on grade change, Reporter implication for all campus users | 4 tests PASS. Staging: 6 `campus.grade.change` audit rows. |
| RTC fix | `campus_rtc_fix` static JS patch on `web.assets_web` | Node-level regression cases recorded (`evidence/tests/rtc-initialization-20261118.json`); real two-device call result: **FAIL** (only local preview confirmed; peer state/ICE new). No automated tests. |
| LAN HTTPS | nginx on LAN IP:8443, TLS 1.2/1.3, serves only public CA cert, passes `X-Forwarded-Host/Proto/For` to Odoo | `nginx -t` PASS; CA trust: CA installed, HTTPS login 200; browser restart check pending user verification (`lan-ca-trust-20261118.json`). `web.base.url` = `https://172.16.151.135:8443` (staging). |
| TURN | coturn with `network_mode: host`, port 3478, relay 49160-49200, realm `formula-university.lan`, no-tls, no-cli; generated by `scripts/configure-lan-turn.py` (credential not recorded here) | NOT VERIFIED: relay path in a two-device call. Config file lives in `evidence/private/` (not read). |
| Outgoing mail | none configured (`ir_mail_server` active count 0 in staging) | VERIFIED absent in staging |
| SSO, LMS, SIEM, notification adapters | none in repository | not present |

## 5. Current data, staging copy (BASE-02)

Label: staging copy of production taken 2026-11-26 (per orchestrator). Read-only queries only, via `docker exec isms-db psql -U odoo -d orgil_isms_stage` with `SET default_transaction_read_only=on`. Production DB was not queried.

| Metric | Value |
| --- | --- |
| Assets (`isms_asset`) | 16 total, 16 active; 16 with `product_id`, 5 with `lot_id` |
| Risks (`isms_risk`) | 15; by state: identify 1, evaluate 3, respond 4, implement 5, residual 2 (analyze 0); by level: high 5, medium 8, low 2; accepted_by set 1; residual accepted 2 |
| Annex A catalogue (`isms_control`) | 93 total; `selected` 25; selected by implementation: yes 15, partial 10; catalogue-wide implementation: yes 42, partial 50, no 1 (implementation is filled for non-selected rows too); applicable not selected 67 |
| Policies (`isms_policy`) | 4, all `approved` |
| Incidents (`isms_incident`) | 22; by state: incident 15, report 1, investigate 2, resolve 0, close 4 |
| Helpdesk tickets (`helpdesk_ticket`) | 26; linked to ISMS 22; by stage: Incident 15, Close 4, New 4, Investigate 2, Report 1 (stage names as stored) |
| Audit log (`isms_audit_log`) | 595 rows; actions: write 245, create 191, state 66, login 64, access_change 20, login_failed 9; models include isms.control 272, res.users 85, isms.policy 51, isms.asset 39, isms.incident 36, isms.risk 32, campus.grade.change 6; timestamps 2026-11-16 03:00 to 2026-11-20 10:04 (database time). 510 rows have `ip_address` NULL (non-HTTP writes). |
| Users (`res_users`) | 23 total; 19 active internal; 2 share (portal/public, both inactive or system) |
| Groups with members | ISMS Reporter 20 (19 active); Asset Owner 7 (6); Analyst 4 (3); Auditor 4 (3); CISO 3 (2); Campus Student 2; Campus Lecturer 2; Campus Registrar 2; Campus Academic Auditor 1; Campus Catalog Reader 7; Campus and ISMS Auditor 0 |
| Campus | 3 students (2 linked to users), 2 offerings, 3 enrollments, 2 grade-change requests (1 approved, 1 submitted) |
| Attachments (`ir_attachment`) | 193 |
| Discuss `general` channel (id 1) | 19 members = all 19 active internal users |

SQL used (examples; all read-only):

```sql
SELECT state, count(*) FROM isms_incident GROUP BY 1;
SELECT count(*) FILTER (WHERE selected), implementation FROM isms_control GROUP BY implementation;
SELECT action, count(*) FROM isms_audit_log GROUP BY 1;
SELECT count(*), count(*) FILTER (WHERE active), count(*) FILTER (WHERE totp_secret IS NOT NULL) FROM res_users;  -- count only
```

## 6. Security posture (BASE-08)

Facts only. No secret value, TOTP seed or password was read or printed. Counts only where secrets are involved.

### 6.1 MFA

- `auth_totp` installed; `auth_totp_mail` installed; `auth_totp_mail_enforce` **uninstalled**; `auth_totp_portal` installed; `auth_passkey` uninstalled. Query: `SELECT name, state FROM ir_module_module WHERE name LIKE 'auth_%'`.
- `auth_totp_device` rows: **0**. Users with `res_users.totp_secret` set: **0** (count only).
- No enforcement of MFA for any group in repository code. Privileged accounts (uid 2 `admin`, uid 54, CISO uid 53 and 58, Access Rights holders) therefore have no second factor. `auth_totp_mail` needs outgoing mail, which is not configured (section 4).
- Conclusion: MFA is available in the install, not enrolled, not enforced. Status: **not implemented in practice** (matches `management/odoo-guide.md:122`).

### 6.2 Audit-log protections

- ORM level: `IsmsAuditLog.write` and `unlink` raise `UserError` (`university_isms/models/audit.py:77-81`). Mixin logs write and unlink with old and new values (`audit.py:146-175`). Internal bypass token is a Python object (`audit.py:91-96`).
- Database level: no triggers, no rules on `isms_audit_log` (`pg_trigger`, `pg_rules` count 0). Table owner is `odoo`, and role `odoo` is **superuser** with CREATEDB, and holds INSERT, SELECT, UPDATE, DELETE, TRUNCATE, TRIGGER on the table. Any DB administrator or application-DB credential can alter or delete audit rows without trace.
- No hash chain, no external sink, no WORM copy. Repository docs say the same (`management/odoo-guide.md:120`).
- `auth` and `access_change` events are logged in `res_users.py` (`_login` at 20-30, `create` at 79-88, `write` at 90-106, `ResGroups.write` at 112-129). `login_failed` is recorded.

### 6.3 Backup strategy

- Tool: `evidence/tools/backup_restore_verify.py`. Latest recorded run: `evidence/tests/backup-restore-20261116_032259.json`, result PASS, restore to a temporary database, 10 table counts compared, 190 attachments verified, 48.4 s restore.
- Backup files are in `evidence/private/backups/` (not read here).
- Offsite, immutable (WORM) or NAS copy: **none** (`management/operations.md:45`).
- Restore verification at HEAD: NOT VERIFIED.
- No scheduled backup job found in repository (`ir_cron` contains only the ISMS monitoring job in staging).

### 6.4 Database manager and proxy

- `list_db = False` in `config/odoo.conf.template:13`; staging `list_db = False` (VERIFIED). `dbfilter = ^orgil_isms$` (template) and `^orgil_isms_stage$` (staging).
- `admin_passwd` placeholder in template; actual value not read.
- `proxy_mode = False` in template and staging, but nginx sends `X-Forwarded-For` and `X-Forwarded-Proto https` (`config/lan-nginx.conf:27-29`). Odoo therefore does not use forwarded headers. `client_ip()` (`audit.py:29-36`) returns `REMOTE_ADDR`. Staging audit rows show Docker bridge and LAN addresses (`172.27.0.x`, `172.16.x.x`), consistent with the proxy hop being recorded instead of the client. Impact on IP accuracy: NOT VERIFIED beyond this observation.
- Odoo listens on `127.0.0.1:8069` by default (`docker-compose.yml:38`). `start-lan.sh` can bind to LAN IP.
- `workers = 0` in template and staging. `max_cron_threads = 1` in template, **0** in staging (cron does not run in staging).

### 6.5 Privileged users (counts, uid only)

| Group | Users (active) | Notes |
| --- | --- | --- |
| `base.group_system` (Settings) | 3 (2): uid 1 (`__system__`, inactive), uid 2 `admin`, uid 54 | uid 54 is non-default and holds Settings and Access Rights |
| `base.group_erp_manager` (Access Rights) | 3 (2): uid 1 (inactive), uid 2 `admin`, uid 54 | can run access review |
| `university_isms.group_isms_manager` (CISO) | 3 (2): uid 1 (inactive), uid 53, uid 58 | business approval rights |
| `stock.group_stock_manager` (Inventory Administrator) | 10 (8): uid 1, 2, 3 (inactive `default`), 13-19 (7 non-default accounts, all e-mail-form logins) | Inventory admin for 7 non-default accounts: need NOT VERIFIED |
| `base.group_no_one` (Technical Features) | 21 (19 active) | inherited from `base.group_user` in core |

`admin` (uid 2) holds no ISMS business group (only Reporter via XML and migration), consistent with `management/audit-20261118.md` section 3.3.

### 6.6 Discuss

- Discuss `general` (id 1) contains all 19 active internal users, including the 2 linked campus student accounts. Auto-join mechanism in core: NOT VERIFIED (no custom code creates this membership; no repository reference found).
- `university_access_review` reads discuss channels only for visibility (`access_review.py:190-194`).

### 6.7 Other posture facts

- Password policy: `auth_password_policy` installed, `auth_password_policy.minlength = 10` (staging `ir_config_parameter`).
- Self-service reset: `auth_signup.reset_password = True` in staging, but no outgoing mail, so the flow cannot send codes (VERIFIED configuration, delivery NOT VERIFIED).
- Access review can assign any non-hidden group to another user: `_group_lines` (`access_review.py:243-258`) excludes only `base.module_category_user_type` and `base.module_category_hidden`. `base.group_system` and `base.group_erp_manager` are both in `base.module_category_administration` (core `base/data/ir_module_category_data.xml:145-150`), which is not excluded, so both are offered. `action_apply_groups` (`access_review.py:267-285`) blocks self-change and root/admin only. A manager can grant Settings or Access Rights to another user through this path. Code reading; not exercised live.
- Campus student accounts inherit ISMS Reporter (`campus_isms_bridge/security/bridge_groups.xml`). Effects: reads approved policies; ACL on `isms.control` read (`access_control_reporter`), with sensitive fields limited by `groups=` (per `audit-20261118.md` section 3.1).
- Odoo image and PostgreSQL image are tag-pinned only (not digest-pinned).
- Evidence path for private material: `evidence/private/` (excluded; not read).

## 7. Course requirements status (BASE-07, summary)

Full table in `docs/roadmap/GAP_ANALYSIS.md` section B.

## 8. Known unverified items

- Current HEAD test run (BASE-05): NOT VERIFIED in this pass. Last recorded run: 47 PASS (`evidence/tests/regression-20261118.json`), with the exclusions in section 1.1.
- Browser screenshots by role and viewport (BASE-06): 16 PNG captures in `evidence/screenshots/` plus `debug-campus-ui.png`. Roles and viewports not recorded; treated as desktop only.
- Real two-device RTC call: FAIL (`evidence/tests/rtc-initialization-20261118.json`).
- Production database and container: not queried, not inspected.
