# Gap Analysis (Phase 0)

Base: HEAD `2f68f12` on branch `formula-erp`. Staging figures from `docs/roadmap/BASELINE.md` section 5 (staging copy of production taken 2026-11-26). Paths relative to repository root. Priority: **P0** security or data-integrity risk, or blocks later phases; **P1** needed in the phase that owns the task; **P2** later or nice-to-have.

Coverage labels: "none" means no file, model or view in the repository implements the item.

## A. Master-prompt task IDs

### A.1 Phase 0 (BASE)

| ID | Current coverage | Gap | Priority |
| --- | --- | --- | --- |
| BASE-01 | `docs/roadmap/BASELINE.md` (this pass); HEAD and addon manifests verified | Re-run at each HEAD change | P1 |
| BASE-02 | `docs/roadmap/BASELINE.md` sections 2-4; models, ACLs, rules, workflows mapped | Sudo review (41 call sites) not done; access-review group-grant path is a finding (GOV-05) | P0 |
| BASE-03 | `odoo/scripts/setup.sh`, `init-db.sh`, `odoo-cli.sh`, `odoo-shell.sh`, `docker-compose.yml`, `docker-compose.https.yml` | Staging container `isms-stage-odoo` and `orgil_isms_stage` are not defined in repo compose; reproducible staging procedure not documented in repo | P1 |
| BASE-04 | `evidence/tools/backup_restore_verify.py`; `evidence/tests/backup-restore-20261116_032259.json` PASS (local, 2026-11-16) | Not re-run at HEAD; no offsite copy | P0 |
| BASE-05 | `odoo/scripts/run-tests.sh` (47 tests PASS in `evidence/tests/regression-20261118.json`) | Not re-run at HEAD in this pass (NOT VERIFIED). Default run excludes `university_access_review` (5 tests), `campus_rtc_fix` (0 tests), `helpdesk_mgmt` own tests | P1 |
| BASE-06 | `evidence/screenshots/` 16 PNG + `debug-campus-ui.png` | Not per role or viewport; no mobile, tablet or dark captures; a debug image is committed | P1 |
| BASE-07 | `management/requirements.md` (R01-R21, U01-U08); section B below | Several evidence items are partial (report, slides, demo, contribution) | P1 |
| BASE-08 | `docs/roadmap/BASELINE.md` section 6 | Findings in section C (MFA, audit integrity, backup, access-review grant path, superuser DB role) | P0 |
| BASE-09 | `docs/roadmap/` (BASELINE, GAP_ANALYSIS). `management/` holds decisions, worklog, implementation plan | No backlog, test matrix or architecture-scope file yet; decision log exists only in `management/decisions.md` | P1 |

### A.2 Phase 1 (UI design system)

| ID | Current coverage | Gap | Priority |
| --- | --- | --- | --- |
| UI-01 | none (no design-system addon; no SCSS tokens; only `campus_rtc_fix` JS) | Create `formula_design_system` with tokens and typography | P1 |
| UI-02 | `university_isms/views/menus.xml` (stock Odoo menu tree) | Role-aware sidebar, breadcrumbs, active states | P1 |
| UI-03 | none (stock Odoo buttons) | Button variants and state set | P2 |
| UI-04 | partial: stock Odoo cards and dialogs; `confirm=` dialogs in access review and grade actions | Badges, toasts, tooltip rules, consistent confirmations | P2 |
| UI-05 | none | Transitions, skeleton loading, reduced-motion support | P2 |
| UI-06 | none in repository | Light and dark theme with persisted preference; core support NOT VERIFIED | P2 |
| UI-07 | none (responsive, keyboard and Cyrillic rendering NOT VERIFIED) | Test at 360, 768, 1440 px | P1 |
| UI-08 | none (only `helpdesk_mgmt/tests/test_js.py`, third-party) | Component tests and visual captures | P2 |

### A.3 Phase 2 (command center, analytics, heatmap)

| ID | Current coverage | Gap | Priority |
| --- | --- | --- | --- |
| DASH-01 | `university_isms/models/monitoring.py:85-160` `_isms_kpis`, run with `self.env(su=True)` (`monitoring.py:86`); report gated at `monitoring.py:170-172` | KPI query is superuser and not per-user; must become permission-aware | P0 |
| DASH-02 | none (no Owl component or client action) | Command Center | P1 |
| DASH-03 | partial: `risk.py:42-46` `matrix_level`; pivot in `university_isms/views/risk_views.xml` | Interactive 5x5 heatmap with drill-down | P1 |
| DASH-04 | partial: `residual_*` fields and `current_level` computed (`risk.py:178-189`) | Inherent vs residual visualization, trends | P2 |
| DASH-05 | partial: management-review PDF (`report/management_review.xml`) | Live panels for coverage, SLA, audit readiness, activity | P2 |
| DASH-06 | none | Role-specific dashboard content | P2 |
| DASH-07 | partial: PDF exports only (SoA, asset register, management review) | Time range, saved filters, safe CSV or XLSX export | P2 |
| DASH-08 | partial: manual role matrix in `evidence/tests/live-audit-20261118.json` | No automated ORM-vs-KPI test per role | P1 |

### A.4 Phase 3 (workflow UX)

| ID | Current coverage | Gap | Priority |
| --- | --- | --- | --- |
| WF-01 | partial: incident model with `sla_deadline`, `sla_status`, severity (`incident.py:115-130`); list and kanban views | SOC console with SLA countdown, analyst, affected assets, evidence summary | P1 |
| WF-02 | partial: chatter, helpdesk link `action_open_helpdesk` (`incident_helpdesk.py:58`) | Detail drawer, timeline, investigation notes | P1 |
| WF-03 | partial: `campus.grade.change` model and form/list views (`campus_university/views/campus_views.xml`); server-side rules (`academic.py:141-295`) | Before/after studio, review history, evidence panel | P1 |
| WF-04 | partial: server validation is complete for the modelled actions (section B of BASELINE); view `invisible=` rules not audited | Audit each button visibility against server rules | P1 |
| WF-05 | partial: `isms.control` model and views (`control_views.xml`, `catalog_views.xml`), 93-row catalogue `data/isms.control.csv` | Explorer with linked assets, risks, policies, evidence, next review, findings | P1 |
| WF-06 | partial: `university_access_review` shows group lines with inheritance (`access_review.py:243-258`) | Permission matrix and effective-access explanation; restrict grantable groups (GOV-05) | P1 |
| WF-07 | partial: Mongolian error messages in guards; stock list and form states | Loading, empty, error, keyboard coverage | P2 |
| WF-08 | partial: 11 campus tests incl. self-approval, stale approval, forged context and direct state write, out-of-range score (`campus_university/tests/test_academic.py:59-168`); 25 isms tests, 6 helpdesk tests | Double-click and concurrent-click tests, unauthorized-action matrix for incidents and policies not verified | P1 |

### A.5 Phase 4 (ISMS / GRC assurance)

| ID | Current coverage | Gap | Priority |
| --- | --- | --- | --- |
| ISMS-01 | partial: `evidence` text field on `isms.control` (`control.py:37`); no attachments, not versioned | Evidence vault: attachments, owner, version, SHA-256 digest, reviewer, review status | P1 |
| ISMS-02 | none | Control test plans and executions | P1 |
| ISMS-03 | partial: daily cron `ir_cron_data.xml` (`monitoring.py:51`) covers policy review, overdue risk and SLA; no control test. Staging `max_cron_threads=0` | Scheduled control checks with source, time, outcome, error | P1 |
| ISMS-04 | partial: `monitoring.py:25-40` `_schedule_once` creates mail activities, deduplicated by existing activity | Finding records, alerts, no duplicate incidents | P1 |
| ISMS-05 | partial: treatment tasks via project (`risk.py:314-336`, `project_task.py`) | CAPA: finding, action, owner, deadline, verification, closure | P1 |
| ISMS-06 | partial: `isms.policy.ack` with version (`policy.py:138-170`), `next_review_date` | Scope, expiry, attestation workflow, audit history | P1 |
| ISMS-07 | partial: acceptance reset on reassessment (`risk.py:134-151`); `lifecycle_stage` on assets | Re-evaluation triggers, waivers with owner and expiry, asset reminders | P2 |
| ISMS-08 | partial: SoA, asset register and management-review PDFs (`report/isms_reports.xml`) | Completeness and missing-evidence indicators | P1 |
| ISMS-09 | none | NIST/CIS mapping with verifiable sources | P2 |
| ISMS-10 | none | Tests for retries, permissions, evidence versions, reviewer separation, export completeness | P1 |

### A.6 Phase 5 (governance and security)

| ID | Current coverage | Gap | Priority |
| --- | --- | --- | --- |
| GOV-01 | none (access review is ad hoc per user) | Recertification campaigns, 30/90-day cadence, escalation | P1 |
| GOV-02 | partial: `REVIEW_ACTIONS` display matrix (`access_review.py:37-56`); admin SoD in migration 18.0.1.1.0 | Policy-backed SoD rules and reviewer workflow | P1 |
| GOV-03 | none | Temporary and privileged access requests with expiry | P1 |
| GOV-04 | partial: effective group lines with `implied_by` (`access_review.py:243-258`) | Privileged-access report respecting sensitive boundaries | P1 |
| GOV-05 | partial: self-change and root/admin blocked (`access_review.py:267-285`); audit of group changes (`res_users.py:90-128`) | **Access review can grant `base.group_system` and `base.group_erp_manager` to another user** (section C) | P0 |
| SEC-01 | partial: `auth_totp`, `auth_totp_mail` installed; 0 TOTP devices; `auth_totp_mail_enforce` not installed; no enforcement code | Enrollment, enforcement for privileged groups, recovery path, no silent lockout; email delivery impossible without outgoing mail | P0 |
| SEC-02 | partial: ORM-level `UserError` on audit write and unlink (`audit.py:77-81`) | No DB-level protection (superuser owner role), no hash chain, no external sink | P0 |
| SEC-03 | partial: local backup and restore rehearsal PASS (2026-11-16) | No offsite, WORM or NAS copy; no DR test at HEAD | P0 |
| SEC-04 | partial: tests for self-approval, stale revision, reporter field restriction, brute-force detection | No systematic IDOR, CSRF, export and privilege-escalation suite | P1 |

### A.7 Phase 6 (academic ERP and integrations)

| ID | Current coverage | Gap | Priority |
| --- | --- | --- | --- |
| EDU-01 | none (campus users use the Odoo backend; no portal pages) | Student portal: schedule, grades, transcript status, requests | P2 |
| EDU-02 | partial: lecturer record rules and grade-change request (`campus_security.xml`) | Teacher portal: roster, grade entry, attendance | P2 |
| EDU-03 | none | Registration capacity, prerequisites, deadlines | P2 |
| EDU-04 | none | Timetable, attendance, transcript, GPA, graduation rules | P2 |
| EDU-05 | none; scope not defined in `management/case.md` | Admissions, tuition, scholarship only if defined | P2 |
| INT-01 | none in repository (`auth_oauth` / SSO not assessed; NOT VERIFIED) | SSO adapter for chosen IdP | P2 |
| INT-02 | none | Moodle adapter with data ownership and idempotency | P2 |
| INT-03 | none; outgoing mail not configured in staging (`ir_mail_server` active 0) | Notification preferences, templates, retries; required for MFA e-mail and resets | P1 |
| INT-04 | none | SIEM forwarding with privacy-aware payloads | P1 |
| INT-05 | none explicit; Odoo JSON-RPC defaults only (NOT VERIFIED) | API boundary, authentication, rate limiting | P2 |

### A.8 Phase 7 (AI assistant and release)

| ID | Current coverage | Gap | Priority |
| --- | --- | --- | --- |
| AI-01 | none | Permission-aware read-only search and summaries | P2 |
| AI-02 | none | Answers linked to accessible records | P2 |
| AI-03 | none | Suggestions with source and uncertainty | P2 |
| AI-04 | none (human approval is already enforced for grades, incidents, policies, residual risk in server code) | Keep consequential actions human-approved | P2 |
| AI-05 | none | Privacy, provider policy, prompt-injection defence, logging | P2 |
| REL-01 | partial: `run-tests.sh` (47 tests) | Covers 5 of 8 custom addons; all-addon run and upgrade test missing | P1 |
| REL-02 | none (visual QA not done) | Mobile, tablet, desktop and dark captures | P2 |
| REL-03 | none | Dashboard query profiling | P2 |
| REL-04 | partial: local restore rehearsal; migration `university_isms/migrations/18.0.1.1.0` | Upgrade, rollback, deployment failure modes | P1 |
| REL-05 | partial: `management/operations.md`, `management/odoo-guide.md`, `odoo/README.md` | Runbook, user guides, capability matrix, known limits | P2 |

### A.9 Additional findings from this pass (not in master list)

| ID | Current coverage | Gap | Priority |
| --- | --- | --- | --- |
| EXT-01 | `university_isms_helpdesk` live exercise PASS | none beyond routine retest | P2 |
| EXT-02 | RTC fix: `campus_rtc_fix`; real two-device call FAIL (`evidence/tests/rtc-initialization-20261118.json`) | Real browser media path not working; no automated test | P1 |
| EXT-03 | LAN HTTPS (`docker-compose.https.yml`, `config/lan-nginx.conf`) | `proxy_mode=False` while nginx sends `X-Forwarded-*`; audit `ip_address` records `REMOTE_ADDR` (proxy hop) | P1 |
| EXT-04 | TURN coturn `network_mode: host` | Relay path not verified in two-device call; host networking widens exposure | P1 |
| EXT-05 | Discuss `general` channel | All 19 active internal users are members, including student accounts | P1 |
| EXT-06 | `base.group_user` implies Technical Features (core) | Effect on debug mode and technical menus for all internal users, including students, NOT VERIFIED | P1 |
| EXT-07 | `stock.group_stock_manager` | 10 users, 7 with non-default e-mail-form logins; need not verified | P1 |
| EXT-08 | `admin` account and uid 54 | `admin` holds Settings, Access Rights and Inventory Manager; uid 54 holds Settings and Access Rights; separation from business roles only partly done | P0 |
| EXT-09 | staging `max_cron_threads=0` | Daily ISMS monitoring cron cannot run in staging (production template sets 1) | P2 |
| EXT-10 | Docker images | `odoo:18.0`, `postgres:16-alpine`, `nginx:1.30.5-alpine3.24`, `coturn/coturn:4.19.1-r0` are tag-pinned, not digest-pinned | P2 |
| EXT-11 | campus bridge | Campus accounts inherit ISMS Reporter (approved policies visible; `isms.control` ACL read) | P2 |
| EXT-12 | `campus_university` | Campus scope is 3 students, 2 offerings; university features minimal relative to U06 | P1 |

## B. Course requirements (`management/requirements.md` R01-R21, U01-U08)

Status: **met**, **partial**, **unmet**, or **NOT VERIFIED** (cannot be checked from repository or database). Evidence paths relative to repository root.

| ID | Requirement (short) | Status | Evidence / note |
| --- | --- | --- | --- |
| R01 | Odoo CE, Docker or source deployment, version proof | met | `odoo/docker-compose.yml`, `odoo/README.md`; Odoo 18.0 confirmed in staging |
| R02 | Organisation case, Clause 4 context | met | `management/case.md` |
| R03 | Module selection, control mapping, rationale | partial | `management/odoo-guide.md` (module table, line 58); full module-control mapping table not confirmed |
| R04 | Asset register at least 10, with owner, classification, location, risk | met | 16 assets in staging; `evidence/screenshots/05-asset-register.png`; `evidence/tests/inventory-catalog.json` |
| R05 | Risk register at least 10, 5x5 matrix, score | met | 15 risks; `evidence/screenshots/06-risk-register.png`, `07-risk-matrix.png` |
| R06 | 20-25 Annex A controls linked to Odoo, asset to evidence chain | partial | 25 selected controls; chain links exist (risk to control, policy to control); evidence is text only (ISMS-01) |
| R07 | Incident five stages, helpdesk workflow | met | `university_isms/models/incident.py:11-17`; `evidence/tests/live-exercise.json` PASS |
| R08 | 2-3 policies, 1-2 pages each | partial | 4 policy files in `policies/` (EISP, ISSP, RTP, AUP); 4 approved in DB. Page length NOT VERIFIED. Approval metadata is recorded as sample per `management/messages.md` |
| R09 | At least 5 RBAC levels | met | 5 ISMS levels plus campus roles (`university_isms/security/isms_security.xml`, `campus_university/security/campus_security.xml`); `evidence/tests/live-audit-20261118.json` role matrix |
| R10 | Users created | met | 23 users in staging (19 active); synthetic case accounts |
| R11 | Audit log with actor, time, model, action | met | 595 rows in `isms_audit_log`; `evidence/screenshots/11-audit-log.png`. Chatter alone is not counted (per requirement). Integrity limits: SEC-02 |
| R12 | SoA for selected controls: applicable, implementation, justification | met | 25 selected; 15 yes, 10 partial; `evidence/screenshots/08-controls-mapping.png` |
| R13 | One Word or PDF report, roughly 20-30 pages | met (length) | `reports/Formula5_FormulaUniversity_Odoo_ISMS_Report.docx` and `.pdf`; PDF 24 pages. Content QA NOT VERIFIED |
| R14 | Cover: organisation, team, date | partial | cover changed in commit `91dc271`; content NOT VERIFIED against team list |
| R15 | Report section order | partial | `reports/report-outline.md` (21 lines); rendered order NOT VERIFIED |
| R16 | Odoo screenshots embedded in report | partial | 16 captures in `evidence/screenshots/`; embedding in the report NOT VERIFIED |
| R17 | PowerPoint or PDF, 8-12 slides | met (count) | `reports/Formula5_FormulaUniversity_Odoo_ISMS_Presentation.pptx`, 10 slides; render NOT VERIFIED |
| R18 | Demo 10-15 minutes, script | partial | `reports/demo-script.md` (33 lines); timing NOT VERIFIED |
| R19 | Real individual contributions, login and Git trace | NOT VERIFIED | `management/team.md`, `management/worklog.md` exist; cannot be verified by repository inspection |
| R20 | Original work, AI assistance disclosure | NOT VERIFIED | Not checkable from code. Disclosure text not located in this pass |
| R21 | Mongolian with English technical terms | met | Mongolian prose across `management/` and `reports/` |
| U01 | Inter-agent append-only log, work plan | met | `management/messages.md`, `management/worklog.md` |
| U02 | Coordination without overlap | met | `management/coordination.md`, `management/assignments.md` |
| U03 | New case, not copied from earlier seminar | partial | `management/case.md`; originality judgement NOT VERIFIED |
| U04 | Study of lectures and seminars | met | `management/course-review.md`, `management/glossary.md` |
| U05 | Install, run and architecture explanation | met | `odoo/README.md`, `management/operations.md`, `management/architecture.md` |
| U06 | Own university system with ISMS integration and access checks | partial | `campus_university`, `campus_isms_bridge`; 3 students, 2 offerings; grade-change approval enforced server-side |
| U07 | Team of 5, names from prior report | partial | `management/team.md`; name match NOT VERIFIED |
| U08 | VM and server reuse policy, registry | partial | `management/environment-audit.md`; registry state is outside repo (NOT VERIFIED) |

Threshold checks (`management/requirements.md`, section "Баталгаажуулалтын босго"):

| # | Threshold | Status |
| --- | --- | --- |
| 1 | Each requirement linked to canonical file and evidence | partial (this table) |
| 2 | RBAC allow and deny tests pass | partial: `live-audit-20261118.json` role matrix and 47 tests; HEAD run NOT VERIFIED |
| 3 | Grade change: no self-approval, only approved change is effective | met by code (`academic.py:141-159`, `188-191`); campus tests 11 PASS per `evidence/tests/campus-tests.json` |
| 4 | Audit log has actor, timestamp and change | met for ORM writes; tamper evidence not met (SEC-02) |
| 5 | Re-seeding creates no duplicates; DB and filestore backup and restore checked | NOT VERIFIED (seed idempotence not tested); backup and restore rehearsal PASS, local only |
| 6 | No change to shared disk, services or other course evidence | NOT VERIFIED in this pass |

## C. Priority P0 summary

1. **MFA not enrolled or enforced** (SEC-01, EXT-08): 0 TOTP devices; privileged accounts (`admin`, uid 54, CISO uid 53 and 58) have no second factor. Enforcement needs outgoing mail for `auth_totp_mail`, which is not configured.
2. **Audit log not tamper-evident** (SEC-02): ORM-only guard (`audit.py:77-81`). Database role `odoo` is superuser and table owner; no triggers, rules or hash chain; no external sink.
3. **No offsite or immutable backup** (SEC-03, BASE-04): only a local rehearsal (2026-11-16) passed; not re-run at HEAD.
4. **Access review grants Settings and Access Rights** (GOV-05): `access_review.py:243-285` offers `base.group_system` and `base.group_erp_manager`; only self and root/admin are blocked. Not exercised live.
5. **Privileged accounts mix roles** (EXT-08): `admin` holds Settings, Access Rights and Inventory Manager; uid 54 holds Settings and Access Rights.
6. **KPI and report counts run with superuser** (DASH-01): `monitoring.py:86` `self.env(su=True)`; permission filtering for dashboards is not in place yet (phase 2 gate).
7. **Two-device RTC call failed** (EXT-02): remote media not confirmed.

## D. Items NOT VERIFIED in this pass

- HEAD test run (BASE-05), production database and container, staging runtime-to-HEAD identity.
- Discuss auto-join mechanism for the `general` channel (EXT-05).
- Effect of `base.group_no_one` on debug mode (EXT-06).
- TURN relay in a real call (EXT-04).
- Report content, slide render, demo timing and page-length items (R08, R13-R18).
- Each `sudo()` call site (41 occurrences) for justification.
