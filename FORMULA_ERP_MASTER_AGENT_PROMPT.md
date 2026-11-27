# FORMULA UNIVERSITY ERP — MASTER IMPLEMENTATION PROMPT

> **Purpose:** Give this document to an autonomous coding agent (Codex, Claude Code, Cursor, or another capable agent) with access to the Formula University repository and an authorized development environment.
>
> **Target:** `https://github.com/hex0tic/formula-university-odoo-isms`
>
> **Platform:** Odoo 18 Community, PostgreSQL 16, Docker Compose, Python ORM, XML views, Owl JavaScript, SCSS.
>
> **Mission:** Transform the existing University + ISO/IEC 27001 ISMS project into a polished, maintainable, secure, enterprise-style **Formula ERP** without breaking existing workflows, data, or access controls.

---

## 0. Your role and operating mode

Act as a **senior Odoo 18 architect, full-stack ERP engineer, UI/UX designer, ISMS/GRC specialist, and rigorous QA engineer**. Own the implementation end to end, but act within the user's authorized environment and permissions.

**This is an implementation assignment, not a request for another conceptual proposal.** Inspect the repository, derive an accurate baseline, implement the features in order, verify the results, and document what actually works. Work incrementally. Do not claim something is implemented because a mockup, screenshot, static HTML page, or untested stub exists.

### Non-negotiable operating rules

1. **Read first:** Inspect `AGENTS.md` and repository-specific instructions, `README`, `docker-compose` files, addon manifests, Python models, security CSV/XML, views, tests, existing screenshots, and implementation documentation before editing.
2. **Respect existing work:** Preserve unrelated edits and user data. Check `git status` before starting. Do not reset, clean, or overwrite uncommitted work.
3. **Do not modify Odoo core or vendor addons.** Extend the system with isolated, upgradeable custom addons, inherited XML views, documented services, and standard Odoo extension mechanisms.
4. **Preserve business invariants.** UI changes must never bypass server-side approval rules, ACLs, record rules, grade revision checks, incident state transitions, or ISMS audit controls.
5. **Do not operate on production data without explicit authority.** Use development/staging databases, synthetic data, and a verified backup. Stop for permission barriers, missing credentials, destructive migrations, or materially expanding the scope.
6. **No silent destructive operations:** No unapproved database drop/recreation, mass deletion, resetting user access, broad dependency upgrades, force pushes, or production deployments.
7. **Keep security intact:** Do not log passwords, OTP seeds, API tokens, personal student data, grades, or other sensitive information. Avoid unsafe `sudo()`, insecure controller routes, hardcoded secrets, and unrestricted record access.
8. **No fabricated results:** If a browser test, two-device RTC test, external integration, security test, or database restore was not actually run, clearly mark it as unverified.
9. **Deliver complete vertical slices:** A feature is not complete until its backend, access control, actual GUI, test coverage, and user-facing behavior work together.
10. **Be autonomous within scope:** Continue through the phase backlog when safe. Ask only for truly blocking decisions. At the end of each phase, publish the status, evidence, outstanding issues, and next phase.

**User-facing communication:** Report in concise, technically correct Mongolian; retain English technical terms when useful. Avoid emojis, promotional language, vague claims, and unnecessary long audits. Provide direct evidence for each completed milestone.

---

## 1. Existing project: known starting context (VERIFY, do not assume current)

The repository was previously analyzed and had these custom addons:

| Existing addon | Known responsibilities |
| --- | --- |
| `campus_university` | Programs, students, courses, semesters, enrollment, controlled grade-change requests/approvals and grade revisions. |
| `campus_isms_bridge` | Audit integration between campus workflows and ISMS. |
| `university_isms` | Asset, risk, ISO 27001 controls/SoA, incidents, policies, audit logs, monitoring, PDF reports. |
| `university_access_review` | User/group/model permissions and access-review visibility. |
| `university_isms_helpdesk` | Incident to OCA Helpdesk ticket synchronization and workflow. |
| `university_isms_stock` | ISMS asset and Inventory integration. |
| `university_isms_inventory_catalog` | Inventory product/catalog synchronization. |
| `campus_rtc_fix` | Narrow Odoo Discuss WebRTC initialization patch. |

Previously observed examples: 16 assets, 14 risks, 93 Annex A control catalog records, 25 selected controls, 15 implemented and 10 partial, four approved policies, and seven incident/helpdesk records. **These are historical sample figures, not constants or proof of current database state.** All new dashboards must query actual authorized records and display the true current figures.

Previously observed architectural strengths:

- Grade-change approval is designed to prohibit direct unauthorized grade edits, self-approval, and stale revision approval.
- Risk management has a lifecycle and risk-treatment links.
- Incident management has defined states and helpdesk integration.
- ISMS records have custom audit hooks and permission boundaries.
- The system mostly uses standard Odoo XML form/list/kanban/pivot/graph interfaces.

Previously observed gaps/risks to re-check:

- No dedicated design-system addon, custom SCSS theme, or substantial Owl dashboard was seen; most visuals still resembled stock Odoo.
- Risk matrix visualization was a conventional pivot, not a purpose-built interactive heatmap.
- MFA enrollment was not demonstrated as enforced for users.
- ISMS audit-log protections were ORM-level, not proof of external tamper-evident or immutable storage.
- Offsite/immutable backup, complete disaster-recovery testing, and full latest-suite tests must be revalidated.
- A historical test count is not evidence that the current HEAD passes.

Create an accurate **Current State / Gap Analysis** at Phase 0; update the plan whenever repository reality differs from this context.

---

## 2. Product vision and design direction

Build **Formula Enterprise ERP** with three cohesive product surfaces:

1. **University Operations:** Students, teachers, programs, courses, enrollments, grades, schedule, attendance, academic lifecycle, self-service portals.
2. **ISMS / GRC:** Assets, risks, controls, SoA, policies, incidents, audits, evidence, control testing, remediation, access governance.
3. **Executive Intelligence:** CISO/manager dashboards, trend analysis, real-time alerts, KPI drill-downs, and a carefully constrained AI assistant.

### Design system direction

| Token / principle | Initial target; adapt after visual review |
| --- | --- |
| Background | `#F8FAFC` / `#F1F5F9` |
| Main navigation | `#0F172A` |
| Primary accent | `#635BFF` |
| Security positive | `#0D9488` |
| Warning / critical | `#F59E0B` / `#EF4444` |
| Typography | Inter or Manrope, with reliable Mongolian/Cyrillic rendering |
| Spacing | Consistent 4/8px scale |
| Border radius | 10–16px where appropriate; avoid excessive pill styling |
| Motion | Subtle, purposeful, usually 150–250ms |
| Density | Readable enterprise data tables; compact mode where useful |
| Themes | Light and dark with persistent preference |

**High-quality UX requirements:**

- Collapsible role-aware sidebar; clear breadcrumbs; global search/quick actions when justified.
- Primary/secondary/outline/danger/icon button variants with hover, active, focus, disabled, loading, and success states.
- Consistent semantic badges, toasts, modals, confirmations, skeletons, empty states, charts, tooltips, and workflow steppers.
- Use SVG icons and careful spacing, not flashy gradients or excessive motion everywhere.
- Responsive layouts for 360px mobile, 768px tablet, and 1440px desktop; prioritize review and monitoring tasks on small screens.
- Keyboard navigation, visible focus, semantic labels, accessible contrast, reduced-motion support, and readable dense tables.
- Preserve Odoo's native UX where it already works well; override surgically instead of rewriting every standard view.
- Motion and interactions must not cause excessive CPU/GPU usage or block form workflows.

**Design and engineering must proceed together.** Screens must be operational and tied to real Odoo models; mockups alone do not satisfy acceptance.

---

## 3. Architecture guidelines

Use Odoo 18's supported facilities: Python ORM models, ACL/record rules, inherited XML views, `ir.actions.client`, Owl components, SCSS, Odoo services/registries, and manifest-declared asset bundles. Verify whether `web.assets_backend`, `web.assets_web`, and `web.assets_frontend` are appropriate for the exact installed Odoo version and page type; do not blindly copy an example.

Suggested addon boundaries (adjust names or dependency order if the repository requires it):

```text
odoo/addons/
  formula_design_system/          # tokens, shell tweaks, reusable components
  formula_command_center/        # CISO dashboards, KPIs, heatmap
  formula_workflow_ux/           # grade, incident, SoA, review screens
  university_isms_evidence/      # evidence vault, versioning, attestations
  university_isms_monitoring_plus/ # scheduled testing, alerts, CAPA
  university_access_governance/  # certification, SoD, temporary access
  campus_portal/                 # student and teacher self-service
  formula_integration_hub/       # safe adapters: SSO, LMS, SIEM, notifications
  formula_isms_copilot/          # optional assistive AI
```

Do not create empty modules merely to match this tree. Create only when implementing a real vertical slice. Prefer reuse of existing models and OCA capabilities; evaluate dependency, maintenance, and license compatibility before installing new packages.

### Backend rules

- Centralize access-aware KPI queries in services/models, not unprotected public controllers or client-side hardcoded data.
- ORM permissions and record rules are the source of truth. Never compute sensitive counts from `sudo()` unless narrowly justified and policy-reviewed.
- Preserve transaction boundaries, concurrency checks, grade revision safeguards, audit behavior, and workflow validation.
- For high-volume aggregates, use appropriate `read_group`, indexes, caching, and explicit invalidation; measure before optimizing.
- For long-running checks/integrations, use appropriate jobs/cron with retries, timeouts, idempotency, and recorded outcomes.
- External integration secrets belong in authorized secure configuration; never in tracked code or test fixtures.
- Feature flags should isolate incomplete AI/integration features from standard operations.

### Frontend rules

- Reusable Owl components should have clear JS, XML, and optional SCSS ownership.
- Use design tokens instead of scattered literal styles.
- Avoid fragile DOM monkey-patching, unnecessary external UI frameworks, and CSS selectors that unintentionally restyle the entire Odoo application.
- Use native Odoo navigation, notifications, dialogs, and services where compatible.
- Use the same error-handling and loading convention across all new screens.
- Every actionable UI control must perform its promised operation; do not ship decorative fake buttons.

Official references:

- Odoo 18 assets: https://www.odoo.com/documentation/18.0/developer/reference/frontend/assets.html
- Odoo 18 Owl components: https://www.odoo.com/documentation/18.0/developer/reference/frontend/owl_components.html
- Odoo 18 testing: https://www.odoo.com/documentation/18.0/developer/reference/backend/testing.html
- Odoo 18 JavaScript unit testing: https://www.odoo.com/documentation/18.0/developer/reference/frontend/unit_testing.html
- W3C reduced-motion guidance: https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions

---

## 4. Execution roadmap — implement in phase order

The estimates below are **planning ranges for one experienced full-time developer**, not deadlines or promises. Confirm after Phase 0. Parallel work is allowed only when dependency and integration risks are controlled.

### PHASE 0 — Baseline, safety, and implementation contract (3–5 working days)

**Tasks**

- `BASE-01`: Inspect exact HEAD, modules, manifests, XML views, Python code, tests, Docker configuration, and Git status.
- `BASE-02`: Map models, RBAC/ACL/record rules, navigation, states, integrations, and cross-module dependencies.
- `BASE-03`: Establish repeatable development/staging startup and sample-data procedures.
- `BASE-04`: Safely verify DB/filestore backup and restoration in a disposable environment.
- `BASE-05`: Run existing test suites and record failures with their origins; do not mask them.
- `BASE-06`: Capture current GUI screenshots for all significant roles, screens, and viewport sizes.
- `BASE-07`: Review ISO 27001 assignment/project requirements and record existing coverage vs unmet requirements.
- `BASE-08`: Confirm permission boundaries, historical MFA enrollment concerns, audit-log guarantees, backup strategy, and external dependencies.
- `BASE-09`: Create `docs/roadmap/` with baseline, scoped architecture, backlog, test matrix, and decision log. Avoid a bloated or duplicated documentation tree.

**Acceptance gate:** Existing workflows can be reproduced; test status is known; staging and recoverable backups are available; major architectural and access-control risks are understood.

### PHASE 1 — Formula Design System (10–15 working days)

**Tasks**

- `UI-01`: Create the design-system addon with SCSS tokens, typography, themes, and reusable component conventions.
- `UI-02`: Implement safe sidebar/top-navigation improvements with breadcrumbs and active states.
- `UI-03`: Implement primary, secondary, outline, danger, and icon buttons with every interaction state.
- `UI-04`: Implement consistent cards, status badges, dropdowns, dialogs, toasts, tooltip behavior, and confirmations.
- `UI-05`: Implement subtle hover/press/route/status transitions and skeleton loading. Respect `prefers-reduced-motion`.
- `UI-06`: Implement dark/light mode and consistent tables, filters, forms, loading, and empty states.
- `UI-07`: Make layouts responsive and keyboard accessible; check Cyrillic font rendering.
- `UI-08`: Add component tests and visual screenshots. Test compatibility with Odoo's standard forms and installed addons.

**Acceptance gate:** A reusable, consistent system exists and is demonstrably applied to real Odoo screens. No major Odoo-native UI regression. Every visible control works. Dark mode, desktop/tablet/mobile, keyboard, and reduced-motion states are tested.

### PHASE 2 — Command Center, Analytics, and Risk Heatmap (10–15 working days)

**Tasks**

- `DASH-01`: Implement a role-aware KPI backend (assets, risks, selected/implemented controls, incidents, open tasks, overdue reviews, audit findings).
- `DASH-02`: Build an Owl-based ISMS Command Center with KPI cards, meaningful trends, filters, and authorized record drill-downs.
- `DASH-03`: Replace/augment the generic risk matrix presentation with a **true interactive 5×5 heatmap**, using the existing approved risk scoring rules.
- `DASH-04`: Add inherent vs residual risk visualization, treatment progress, and historical trends when enough data exists.
- `DASH-05`: Add control coverage, incident SLA, audit readiness, and recent security activity panels.
- `DASH-06`: Implement role-specific dashboard content for CISO/ISMS Manager/Auditor/Admin and any justified academic roles.
- `DASH-07`: Add time range, saved filters, graceful empty states, safe exports, and readable charts.
- `DASH-08`: Test that KPI results match the ORM for every role, including intentionally restricted users.

**Acceptance gate:** All counts and heatmap placements are computed from real, permission-filtered records. Clicking a KPI opens the correct filtered dataset. Empty/new databases work. Unauthorized data cannot leak through dashboard APIs or aggregated counts.

### PHASE 3 — High-impact Workflow UX (10–15 working days)

**Tasks**

- `WF-01`: Build a SOC-style Incident Console with severity, status, SLA countdown, assigned analyst, affected assets, and evidence summary.
- `WF-02`: Build incident detail drawer/timeline, investigation notes, related helpdesk ticket, valid status transitions, and escalation visibility.
- `WF-03`: Build a Grade Change Approval Studio: before/after grade comparison, reason, evidence, review history, revision metadata, approve/reject dialog.
- `WF-04`: Clearly distinguish actions the active user may perform; **server must independently validate every action**.
- `WF-05`: Build an ISO Control Explorer: 93-catalog search/filter, selected control status, owner, linked assets/risks/policies, evidence tab, next review, findings.
- `WF-06`: Improve access-review visibility with a clear permission matrix, readable group inheritance, and explainable effective access.
- `WF-07`: Implement meaningful loading/error/empty states and keyboard support throughout.
- `WF-08`: Test invalid transitions, self-approval, stale grade revision, unauthorized action, double click, and concurrency.

**Acceptance gate:** The real database and original approval/incident/business rules remain authoritative. No client-side shortcut bypasses authorization or audit. All screens work with the correct Odoo menus/actions and tests.

### PHASE 4 — Enterprise ISMS / GRC: continuous assurance (15–25 working days)

**Tasks**

- `ISMS-01`: Evidence Vault with metadata, control association, owner, version, cryptographic digest, reviewer, and review status.
- `ISMS-02`: Control Test Plans and test executions, supporting manual and automatable checks.
- `ISMS-03`: Continuous Control Monitoring via safe scheduled jobs; store source, execution time, outcome, and errors.
- `ISMS-04`: Automated findings/alerts on control failures and overdue evidence; avoid duplicate incident creation.
- `ISMS-05`: CAPA flow: finding → corrective action → owner/deadline → remediation → independent verification → closure.
- `ISMS-06`: Policy review and employee attestation, with scope, expiry, revision, and audit history.
- `ISMS-07`: Risk re-evaluation triggers, accepted-risk exceptions/waivers with owner and expiry, and optional asset lifecycle reminders.
- `ISMS-08`: Audit-ready evidence export with explicit completeness/missing-evidence indicators.
- `ISMS-09`: Optional ISO 27001 to NIST/CIS mapping only with verifiable source mappings and proper licensing.
- `ISMS-10`: Test control-job retries, permissions, consistency, evidence version history, reviewer separation, and export completeness.

**Acceptance gate:** A real failed control check produces traceable evidence/finding, assigns remediation, and can be closed only after authorized verification. Audit exports contain truthful and reproducible evidence, not invented compliance conclusions.

### PHASE 5 — Access Governance and Security Hardening (15–25 working days)

**Tasks**

- `GOV-01`: Periodic Access Recertification campaigns with 30/90-day configurable cadence, manager/owner review, approve/revoke, due dates, and escalation.
- `GOV-02`: Separation of Duties (SoD) rules, policy-backed conflict combinations, and reviewer workflow.
- `GOV-03`: Temporary and privileged access requests with justification, approval, expiry, and revocation.
- `GOV-04`: Effective-permission and privileged-access reporting that respects sensitive access boundaries.
- `GOV-05`: Prevent self-certification/unauthorized role mutation; ensure Odoo groups and record rules remain authoritative.
- `SEC-01`: Plan and verify MFA enforcement for privileged/high-risk users, with recovery and enrollment handling. Do not silently lock out users.
- `SEC-02`: Add external centralized security/audit log forwarding with integrity/retention design; clearly distinguish ORM immutability from true tamper-evidence.
- `SEC-03`: Design/test offsite or immutable backups and disaster recovery in a controlled environment.
- `SEC-04`: Security tests: privilege escalation, IDOR, access bypass, self-approval, direct write/unlink, stale revision, CSRF-sensitive routes, sensitive-data exports.

**Important sequencing:** Begin risk assessment and safe preparation of MFA, backups, and audit-integrity from Phase 0; **do not postpone urgent security fixes merely because this is Phase 5**. Any deployment-wide change affecting real users requires explicit authorization and a recovery plan.

**Acceptance gate:** Access is granted/reviewed/revoked with auditable decisions; SoD violations are visible and handled; MFA and log/backup guarantees are explicitly verified rather than assumed.

### PHASE 6 — Full Academic ERP and Integrations (20–35 working days)

**Tasks**

- `EDU-01`: Student Portal: personal schedule, enrollments, grades, transcript status, notifications, requests, and self-service actions.
- `EDU-02`: Teacher Portal: assigned courses, roster, grade entry, attendance, pending approvals, and related notifications.
- `EDU-03`: Course registration with capacity, prerequisites, semester constraints, deadlines, and server-side validation.
- `EDU-04`: Timetable/calendar, attendance, transcript, GPA, and graduation eligibility, with configurable academic policy.
- `EDU-05`: Admissions, tuition, scholarship, and other advanced university modules **only if requirements and ownership are defined**; never invent policy-specific accounting/business rules.
- `INT-01`: Authentication/SSO adapter compatible with a selected IdP and existing security model; do not invent credentials.
- `INT-02`: Moodle LMS integration adapter with documented data ownership, idempotency, and conflict rules.
- `INT-03`: Email/notification integration with user preferences, templates, retries, and event logging.
- `INT-04`: SIEM/security event integration with privacy-aware payloads and retry handling.
- `INT-05`: API integration boundaries, authentication, rate limiting where applicable, and integration tests.

**Acceptance gate:** Students can access only their own records; teachers only authorized courses/rosters; academic rules are enforced server-side; integrations fail safely and document exact tested/live capabilities. No live third-party connection is claimed without a real authorized test.

### PHASE 7 — AI ISMS Copilot and Production Readiness (15–25 working days)

**Tasks**

- `AI-01`: Read-only, permission-aware policy/control/risk/incident search and summarization.
- `AI-02`: Answers link to specific accessible records/evidence; do not present unsupported generated claims as audit proof.
- `AI-03`: Suggest risk controls, incident summaries, and missing audit evidence, with source/uncertainty disclosures.
- `AI-04`: Keep consequential actions human-approved; AI must never independently approve grades, grant rights, close incidents, or accept risk.
- `AI-05`: Respect privacy, sensitive data handling, prompt injection defenses, provider data policy, and audit logging. Do not send production data to an external model without authorized configuration.
- `REL-01`: Run backend, frontend, security, upgrade, and regression suites across all delivered addons.
- `REL-02`: Perform UI visual QA at mobile/tablet/desktop dimensions and light/dark themes.
- `REL-03`: Profile real dashboard queries and verify acceptable responsiveness on representative datasets.
- `REL-04`: Verify backup, restore, upgrade, deployment, rollback, and failure modes.
- `REL-05`: Produce deployment/runbook, operational documentation, user guides, final capability matrix, and known limitations.

**Acceptance gate:** No critical security regressions, no knowingly broken required workflow, reproducible installation and test commands, credible rollback, and unambiguous evidence of every advertised feature.

---

## 5. Mandatory quality gates for every phase

Use a consistent **Definition of Done**. Do not move a task to DONE unless:

1. **Functional:** The feature works in the actual Odoo UI and relevant backend, not a detached prototype.
2. **Permissions:** At least one authorized role and one unauthorized role are tested; records and counts are protected.
3. **Tests:** Relevant automated tests pass; add regression coverage for changed workflows. Test install and upgrade when changing module data or schema.
4. **UX:** Loading, empty, error, disabled, keyboard, and responsive states are covered where applicable.
5. **Security:** Sensitive data, approval boundaries, direct ORM writes, audit trail, input validation, and side effects were reviewed.
6. **Data:** Existing records are preserved, migration is safe, and no hardcoded sample statistics appear in operational dashboards.
7. **Performance:** Measure query counts and client performance for potentially expensive new pages; avoid N+1 patterns and unnecessary polling.
8. **Evidence:** Include screenshots, test logs/commands, and a concise verification summary.
9. **Documentation:** Explain configuration, models/permissions, dependencies, and how to use/maintain the feature.
10. **Truthfulness:** Known limitations and missing external verification are visible to the user.

### Minimum regression scenarios

- Grade-change request cannot directly modify grades before approval; requester cannot approve their own request; stale revision is rejected.
- Incident state restrictions and helpdesk association remain valid; incident escalation does not duplicate tickets unexpectedly.
- ISMS audit write/unlink protections stay intact; new security-sensitive actions produce correct audit evidence.
- Risk score/heatmap and residual-risk semantics match the registered risk policy.
- Access Review actions cannot illegally change a user's own privileged groups.
- Student/teacher/ISMS/auditor roles cannot enumerate forbidden records through dashboards, API endpoints, search, or exports.
- Assets and inventory links preserve integrity; upgrade/uninstall of new UI modules does not corrupt underlying records.
- Dark mode, Odoo standard dialogs, native navigation, Discuss, and existing installed OCA addons still function.

### Recommended verification tools

- Odoo built-in Python test framework and module install/upgrade tests.
- Odoo 18 frontend HOOT tests and relevant Odoo tours / browser tests.
- Browser screenshots at 360px / 768px / 1440px, both themes where relevant.
- PostgreSQL query profiling and ORM access tests.
- Explicit backup/restore verification using disposable data.
- Existing repository scripts, Make targets, lint/format tools, and CI conventions when available.

Do not add large tooling or third-party dependencies without demonstrating why existing capabilities are inadequate.

---

## 6. Scope, ordering, and prioritization

Priorities:

- **P0 / required:** Safety baseline, working UI design-system foundation, real dashboards/heatmap, preserve grade and incident workflow, access checks, test reliability.
- **P1 / high value:** Incident Console, Grade Approval Studio, Control Explorer, Evidence Vault, control monitoring, CAPA, access recertification, SoD, MFA/log/backup hardening.
- **P2 / expandable:** Full academic portals, SSO/LMS/SIEM integrations, advanced analytics, AI Copilot, extensive framework mappings.

**MVP checkpoint:** After Phases 0–3, the system must already deliver a clearly improved Odoo GUI, working CISO dashboard, interactive risk heatmap, incident console, grade approval UI, and control explorer with tests.

**Enterprise ISMS checkpoint:** After Phases 4–5, control testing, evidence, findings/CAPA, access governance, and real security hardening must be operational and defensible.

**Full platform checkpoint:** After Phases 6–7, academic portals, authorized integrations, AI assistance, and production-grade verification are complete or clearly documented as not implemented/blocked.

Do not sacrifice correctness, security, or working functionality just to complete every P2 item.

---

## 7. Working procedure, milestones, and handoff

### At the start

1. Read all local instructions and inspect the repo thoroughly.
2. Explain the **observed** state, not a guessed one.
3. Produce a short implementation plan with dependencies and identified blockers.
4. Start Phase 0 immediately if the environment and authorization permit it.

### During work

1. Implement a small complete slice; test it; then move on.
2. Make small, logically grouped changes and show the changed files.
3. Prefer working within existing project structure and conventions.
4. Keep a concise status file at `docs/roadmap/STATUS.md` (or the repo's existing equivalent), updated after meaningful milestones.
5. Add `docs/roadmap/DECISIONS.md` for architectural changes requiring explanation, only when useful.
6. Record environment-sensitive verification and blockers without leaking credentials or private data.
7. Do not change unrelated features, rename the whole repository, or introduce unrequested product scope.
8. Do not push, deploy, change external services, or modify the production database without the required authority.

### After every phase, report in Mongolian using this exact structure

```markdown
## Phase [N] — [Name]

### Хийгдсэн ажил
- [Actual implemented features, with file/module references]

### Өөрчлөгдсөн файлууд
- [Relevant files/modules]

### Шалгалт
- Command / test name: PASS | FAIL | NOT RUN
- UI checks: PASS | FAIL | NOT RUN
- Security checks: PASS | FAIL | NOT RUN

### Нотолгоо
- [Screenshots, relevant tests, changed records, exact observed behavior]

### Үлдсэн асуудал
- [Confirmed bugs, blockers, limitations]

### Дараагийн ажил
- [Next exact task IDs]
```

### Final completion report

Provide:

1. **Implemented vs planned matrix** with status `DONE`, `PARTIAL`, `BLOCKED`, or `NOT STARTED` for all task IDs.
2. Exact architecture and module dependency explanation.
3. Screenshots of the new real Odoo GUI, not generated conceptual designs.
4. Features and workflows demonstrably tested, with evidence.
5. Security improvements and remaining security limitations.
6. Exact run/install/upgrade/test instructions.
7. New configuration, required secrets/integrations (without exposing secrets), migrations, and rollback process.
8. Known issues, next priorities, and any items requiring explicit user action.

---

## 8. Stop conditions and decision policy

**Continue autonomously** for ordinary code editing, safe local tests, new addons, UI design, non-destructive migrations in isolated staging, and documentation.

**Stop and request direction** before:

- Deleting or overwriting existing user/project data.
- Modifying a production database or deploying to a real public/production service.
- Obtaining unconfigured secrets, SSO/LMS/SIEM provider access, or transmitting sensitive student/security data to an external AI service.
- Force pushing/rebasing shared branches, merging protected branches, or making irreversible Git changes.
- Implementing ambiguous academic/financial policies that affect real users or records.
- Replacing Odoo itself, migrating the entire stack, or materially changing the approved scope.

If external infrastructure is unavailable, build and test a clean integration boundary with local mocks and explicitly report the live integration as **NOT VERIFIED**, then continue with independent work.

---

## 9. Immediate first instruction

**BEGIN NOW:** Inspect the actual Formula University repository, identify the true current state and repository rules, establish Phase 0 safely, then implement `formula_design_system` and the first functional ISMS Command Center slice. Follow the full phase plan and quality gates without requiring the user to repeat these instructions. Keep the implementation secure, polished, testable, and honest about what has been verified.

**The result must be a working Odoo ERP upgrade—not just a report, design proposal, screenshot gallery, or collection of partially connected components.**
