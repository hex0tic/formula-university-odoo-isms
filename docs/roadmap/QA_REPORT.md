# QA report: REL-02 visual QA and REL-03 performance

Scope: Phase 7 tasks REL-02 (mobile, tablet and desktop widths, light and dark themes) and REL-03 (dashboard query profiling). Environment: staging Odoo 18 at 127.0.0.1:8070, database orgil_isms_stage, all Formula addons installed. Production was not touched.

Status legend: PASS, FAIL, NOT VERIFIED. Contrast is the lowest WCAG 2.x ratio among sampled visible text (disabled controls excluded). Screenshots: docs/roadmap/screenshots/qa_*.png (after fixes); qa_before_*.png for the failing 1440 px captures before the fixes.

## 1. REL-02 matrix (after fixes)

Widths: 360x780, 768x1024, 1440x900. Each cell covers all three widths and both themes unless noted. Dark theme is the cookie color_scheme=dark, which Odoo 18 uses to serve the dark bundle to backend pages.

| Screen (role) | Light | Dark | Before (light / dark) | Notes |
|---|---|---|---|---|
| Command Center (auditor) | PASS, min 4.7 | PASS, min 4.7 | PASS / FAIL 3.78 | Dark link tone fixed |
| Incident Console (analyst) | PASS, min 6.37 | PASS, min 6.37 | FAIL 3.76 / PASS 4.71 | SLA text tone fixed |
| Grade Studio (registrar) | PASS, min 4.7 | PASS, min 4.7 | FAIL 1.43 / FAIL 1.23 | Primary button, status text, notification |
| Control Explorer (auditor) | PASS, min 4.7 | PASS, min 4.7 | FAIL 3.24 / FAIL 1.13 | Dark tags were light-on-light |
| Risk list (auditor, kanban and list) | PASS, min 4.53 | PASS, min 4.53 | FAIL 3.13 / FAIL 1.23 | Badge, kanban cards, list cells |
| Policy form (auditor) | FAIL, min 4.45 (Follow button, borderline) | FAIL, min 2.86 (chatter author name) | FAIL 3.13 / FAIL 1.11 | Status bar fixed; two items remain |
| Student portal /my/campus and /my/campus/grades | PASS, min 4.83 | FAIL (no dark theme) | PASS / FAIL | Website layout ignores the dark cookie; screenshot identical to light |
| Teacher portal (lecturer) | PASS, min 4.7 | PASS, min 4.7 | PASS / PASS | No change needed |

Per-check results (54 page visits before fixes, re-run after fixes):

- Horizontal page scroll (document scrollWidth greater than innerWidth): none at any width or theme. Risk list kanban columns scroll inside their own container at 360 and 768 px; this is intended Odoo behaviour.
- Console errors: 0 on every visit.
- Clipped text or text past the viewport edge: 0 clipped elements; only the kanban column headers mentioned above.
- Focus indicator on Tab: at 360 px the Command Center shows a visible ring on 12 of 12 tab stops. The campus portal shows a ring on 11 to 12 of 12 stops at 1440 px. On backend desktop pages the first 12 Tab stops were systray dropdown items with outline none and no box-shadow, so the check is inconclusive: NOT VERIFIED by hand.
- Reduced motion (prefers-reduced-motion: reduce) on the Command Center: 40 of 64 transitions active normally, 0 of 64 under reduce. Checked on that page only.

Contrast numbers after fixes (sampled minimum, WCAG ratio): Command Center 4.7 light and dark; Incident Console 6.37; Grade Studio 4.7; Control Explorer 4.7; Risk list 4.53; Campus 4.83 to 6.24; Teacher 4.7. Before fixes the worst values were 1.11 to 1.43 (Grade Studio, Control Explorer, Policy form).

## 2. REL-03 performance

Method: Odoo shell against staging, each call run as a representative user (auditor, analyst, registrar, student, lecturer, reporter), ORM query count from env.cr.sql_log_count, wall time with time.perf_counter. Every run was rolled back; staging row counts were checked afterwards (campus_grade_change 2, isms_incident 22, isms_risk 15, unchanged).

Warm median of 3 runs (first run in brackets is cold cache):

| Call | Before ms (queries) | After ms (queries) | JSON bytes |
|---|---|---|---|
| Command Center get_dashboard_data, auditor | 41.2 (32) [cold 241, 69 q] | 53.4 (32) [cold 69 q] | 38.7 k |
| Command Center get_dashboard_data, reporter | 16.1 (14) | 14.1 (14) | 11.4 k |
| Incident Console get_incident_rows, analyst | 15.2 (7) | 14.7 (7) | 23.2 k |
| Incident Console get_incident_detail | 5.8 (14) | 16.7 (14) | 5.2 k |
| Control Explorer get_catalog, auditor | 4.3 (13) | 7.3 (13) | 63.9 k |
| Grade Studio get_queue, registrar | 4.9 (10) | 5.4 (10) | 1.8 k |
| Campus overview, grades, attendance, requests | 2.2 / 4.1 / 16.1 / 2.7 (8, 8, 6, 3) | 3.6 / 3.5 / 2.7 / 1.6 (same) | under 1 k |
| Campus schedule, registration catalog | 17.2 / 24.4 (9, 12) | 7.7 / 4.4 (9, 12) | 1.6 k / 0.8 k |

Before and after differ only by run noise: no Python code changed, and query counts are identical. All dashboard calls are below 1 s, including cold runs (max 241 ms).

Scale check (rolled back): Incident Console rows with 22 and then 82 incidents, 7 queries each. Command Center with 82 incidents, 32 queries (constant). Grade queue with 2 and then 42 change records, about 17 to 20 queries (constant). No per-row query growth was found, so no N+1 fix was needed in these three paths.

Browser page load (time until main content is visible, 1440 px light, after fixes): Command Center 506 ms, Incident Console 476 ms, Grade Studio 488 ms, Control Explorer 271 ms, Teacher portal 347 ms, Campus overview 184 ms. Risk list page load is NOT RELIABLE: its wait selector fell back to a 15 s timeout.

## 3. Fixes made (uncommitted working tree on branch formula-erp)

- formula_grade_studio/static/src/grade_studio/grade_studio.scss: primary button text is white (was the link tone, 1.43 light and 2.03 dark); danger, success and warning text use the dedicated text tokens; new --fgs-danger-text, --fgs-success-text and --fgs-warning-text variables.
- formula_incident_console/static/src/incident_console/incident_console.scss: SLA tone colours use fds text tokens (danger 3.76 light, warning about 2.1).
- formula_control_explorer/static/src/control_explorer/control_explorer.scss: hard-coded light surfaces and tone backgrounds mapped to design tokens (dark tags were 1.13); active chip count background darkened (3.24); success text token (3.74).
- formula_command_center/static/src/command_center/command_center.scss: .fcc-link uses the text-safe primary tone (dark 3.78 to 7.7).
- formula_design_system/static/src/scss/fds_components.scss: Bootstrap success badge and button fill darkened to the accessible token (3.13 to 5.5); .text-muted, .o_form_label and .text-info use text tokens (3.23 to about 7).
- formula_design_system/static/src/scss/fds_dark_surfaces.scss (dark bundle only): notifications get a dark surface (1.23); kanban cards get the dark surface, overriding Odoo's white card rule (cards were white with light text); list data cells use the dark text colour (3.81); form status bar arrow buttons get dark fills (1.11); inline code is lighter (3.77).

No Python, manifest or data changes. No module upgrade needed; staging assets were cleared and the staging container restarted four times for these CSS changes.

## 4. Tests

Command: MODULES=formula_design_system,formula_command_center,formula_incident_console,formula_grade_studio,formula_control_explorer with TAGS set to the five /module tags, on a fresh throwaway database.

- First run (before the last small CSS edits): 71 tests, 0 failed, 0 errors, exit 0.
- Final run (after all CSS edits, fresh throwaway database, 2026-11-26 14:49): `exit=0`, `71 post-tests`, `0 failed, 0 error(s) of 71 tests`.

campus_portal and the other addons were not changed, so their tests were not rerun.

## 5. Remaining issues (not fixed)

1. Student portal (/my/campus) has no dark theme. The dark bundle is backend-only, so the portal stays light. Fix would need a website dark stylesheet; outside the time box.
2. Policy form, dark: the chatter author name is 2.86:1 (purple text on the dark surface). Policy form, light: the Follow button is 4.45:1, just under AA.
3. Chatter tracking values in light mode were 4.3:1 before the text-info fix; the fix was verified by a probe only, not by a full screenshot pass.
4. Write-path N+1 (outside scope, not edited): campus_academic_plus/models/catalog.py, _compute_seats_taken runs one search_count per offering. It is stored and read cheaply, but a batch write touching many offerings recomputes one query each. Fix with _read_group.
5. Campus portal read paths were not scale-tested; the staging dataset is small (4 enrollments, 2 grade changes, 22 incidents, 15 risks).

## 6. NOT VERIFIED

- Keyboard focus ring on backend desktop pages (see section 1).
- Reduced-motion behaviour on pages other than the Command Center.
- Real touch devices, screen readers, Lighthouse or other accessibility audits.
- Performance at production-scale data volumes.
- Campus portal query counts under load.
- Dark theme for teacher-portal beyond the screens sampled.
