# Formula Integration Hub: integration boundaries (Phase 6, INT-01..INT-05)

Module: `odoo/addons/formula_integration_hub` (version 18.0.1.0.0, LGPL-3).
Depends on: `base`, `mail`, `campus_university`, `university_isms`. It does not depend on
`campus_academic_plus`, `campus_portal`, or `university_isms_audit_chain`, and it does not install
`auth_oauth`.

## Status summary

| Item | Status |
| --- | --- |
| Module installs and loads in a throwaway test DB on the stage Odoo image (`orgil_isms_stage` untouched) | VERIFIED |
| 38 tagged unit tests (`formula_integration_hub`), mock transport, no network | VERIFIED (PASS) |
| Live IdP (OIDC) login, discovery fetch, token exchange | NOT VERIFIED |
| Live Moodle Web Services calls, response shapes, role id 5 | NOT VERIFIED |
| Live SIEM receiver, retry against a real endpoint | NOT VERIFIED |
| SMTP delivery of queued mail | NOT VERIFIED (no SMTP configured; asserts `state = outgoing` only) |
| HTTP routing of `/api/formula/v1/...` end to end (real server, Bearer header) | NOT VERIFIED (service layer tested; controller only imported) |
| Multi-worker rate limiting | NOT VERIFIED (limit is per process) |
| SIEM `mfa_policy_block` events from `university_mfa_policy` | NOT WIRED (event type and emitter exist; the addon is not a dependency) |

## Framework

| Model | Purpose |
| --- | --- |
| `formula.integration.endpoint` | One row per integration target. `enabled` is the feature flag (default OFF). Holds the base URL (https only), auth method, and a secret REFERENCE (`secret_key` + `secret_source`: `param` or `env`). The secret value is read at send time and never stored, displayed, or logged. |
| `formula.integration.event` | Outbox. Fields: endpoint, event type, `payload_json`, `idempotency_key` (unique per endpoint), state `pending/sent/failed/dead`, attempts, `next_attempt_at`, `last_error`. |
| `formula.integration.mapping` | Local model and id to remote id. Unique on both sides. Conflicting links raise and never overwrite. |

Dispatcher: `formula.integration.event._cron_dispatch`, every 5 minutes, batch 100.
- Only events of enabled endpoints are sent.
- Rows are locked with `FOR UPDATE SKIP LOCKED`, so parallel workers do not double-send.
- Each row runs in its own savepoint and every failure is caught. The method never raises.
- Backoff: `60 s * 2^(attempt-1)`, capped at 24 h. Retries stop at `max_attempts` (default 5), then the row becomes `dead` (dead-letter). Admins can requeue with `action_requeue`.
- Errors are passed through `_redact`, which replaces the secret value with `***` and truncates to 500 characters.
- Transport: `HttpTransport.prepare` builds the request (no network). `HttpTransport.post` sends it with `requests`, `timeout` from the endpoint, and `allow_redirects=False`. Tests patch `post`.

Feature flag behavior: a disabled endpoint enqueues nothing (`enqueue` returns an empty recordset), sends nothing, and the API returns 404.

## INT-01 SSO (OIDC adapter)

- Ownership: the IdP owns identity. ERP owns the mapping of IdP group to ERP group (`formula.sso.group.rule`).
- Settings on the endpoint: `issuer`, `client_id`, `allowed_domains` (required before enabling), secret reference. No secret value is stored.
- `formula.sso.adapter.parse_discovery(doc, issuer)`: checks the issuer and requires https for `authorization_endpoint`, `token_endpoint`, `jwks_uri`. No network call.
- `formula.sso.adapter.provision_user(endpoint, claims)`, called at login (must be wired into the login flow; see NOT WIRED):
  - requires `sub`, `email`, and `email_verified` is True; the email domain must be in `allowed_domains`.
  - creates the user with no password (SSO only) and links it via `formula.integration.mapping` (`res.users`, `sub`).
  - an existing account with the same login but no link is NOT adopted; an admin must link it.
  - group sync: removes only groups that are rule-managed and absent from the current claims. `base.group_user` and `base.group_portal` are never removed. Groups granted manually are not touched.
- Allowlist (`ALLOWED_GROUP_XMLIDS`): reporter, asset owner, analyst, auditor (ISMS); campus student, lecturer, auditor; `base.group_user`, `base.group_portal`.
- Forbidden (`FORBIDDEN_GROUP_XMLIDS`): `base.group_system`, `base.group_erp_manager`, `university_isms.group_isms_manager` (CISO), `campus_university.group_campus_registrar`. Enforced on rule creation (direct group and transitively implied groups) and again at provisioning.
- Failure modes: missing claim, unverified email, foreign domain, unlinked existing account, and mapping to a deleted user all raise and do not create or change a user.
- Tested (VERIFIED with mocks): privileged rule refused, privileged group not granted, deterministic re-login, revocation of rule groups only, unverified email and foreign domain rejected, existing account not adopted, discovery validation, SSO enable requires domains.
- NOT VERIFIED live: real IdP, token signature and JWKS validation (this adapter does not verify tokens; the auth layer must do so), groups claim naming per IdP.

## INT-02 Moodle LMS

Data ownership:
- ERP is the source of truth for course offerings, student records, enrolments, and final grades (`campus.enrollment.score`).
- ERP to Moodle: course create, user create, manual enrolment.
- Moodle to ERP: activity grades only, as SUGGESTIONS. They create `campus.grade.change` drafts in state `draft`. Moodle never writes a score, and enrolments are never deleted or changed from Moodle.

Moodle Web Services functions (names from Moodle documentation):
- `core_course_create_courses` (payload `courses[]`, `idnumber = ERP-OFF-<offering id>`)
- `core_user_create_users` (`users[]`, `auth = nologin`; no password is ever sent; SSO is expected on the Moodle side)
- `enrol_manual_enrol_users` (`enrolments[]`, role id 5 = student, a site-specific value)
- `gradereport_user_get_grade_items` (read; the reader that produces the suggestion input)

Request format: form-encoded POST with `wsfunction`, `moodlewsrestformat=json`, `wstoken` (from the secret reference), and flattened params (`courses[0][fullname]`). The token is sent only in the form body, never in the URL or `payload_json`.

Success rule: 2xx status AND a JSON list or object without an `exception` key. A Moodle error arrives with HTTP 200 and `{"exception": ...}`, so it is treated as failure.

Idempotency:
- Outbox key per object: `lms:course:<offering>`, `lms:user:<student>`, `lms:enrol:<enrollment>`. A key that already exists is not re-enqueued.
- Enqueueing is skipped when a mapping already exists.
- After a successful create, the response ids are mapped by position to the `erp_refs` in the payload (`after_delivery`).
- Moodle does not honor an Idempotency-Key header, so a crash between Moodle's create and our mapping write could create a duplicate. Mitigation is manual reconciliation. NOT VERIFIED.

Grade suggestions (`formula.moodle.adapter.import_grade_suggestions`):
- Caller must be registrar or lecturer (or superuser). The endpoint must be an enabled LMS endpoint.
- Each item: `remote_user_id`, `remote_course_id`, `remote_item_id`, `grade` (0 to 100).
- Creates `campus.grade.change` through the caller's own environment, so the normal ERP rules apply: lecturers only for their offerings, reason of at least 10 characters, and the approver must differ from the requester.
- Skips with reasons: `invalid`, `out_of_range`, `duplicate` (dedupe key `grade:<user>:<course>:<item>:<score>` stored in the mapping table), `unmapped` (student or course has no mapping), `no_enrollment`, `rejected: <error>`.

Conflict rules (tested):
- ERP wins on enrolment existence and on the score. A suggestion never changes `score` or `grade_revision`.
- A remote id already linked to a different local object is refused (`ValidationError`), never overwritten.
- A remote grade differing from ERP creates a draft for registrar review. It does not overwrite.

Tested (VERIFIED with mocks): WS function names in payloads, token only in form body, idempotent enqueue, remote id mapping from response, Moodle exception body is failure, enrolment needs both mappings, grade import creates drafts only and never changes score, duplicate and invalid suggestions skipped, permission check, mapping idempotency and conflict refusal.

NOT VERIFIED live: Moodle version compatibility, exact response shapes, `categoryid = 1`, role id 5, `nologin` auth on the target site, rate limits, and unenrolment (not implemented: removing an enrolment in ERP does not remove it in Moodle).

## INT-03 Notifications

- Preferences: `formula.notification.preference` (user, category, email, inbox). Categories: `academic`, `security`, `system`. No row means both channels ON.
- Mandatory: `security` cannot be switched off on either channel (constraint plus `channels_for` override).
- Templates (`mail.template`, noupdate): `mail_tpl_grade_decided` (campus.grade.change), `mail_tpl_incident_assigned` (isms.incident). The templates contain no grade values.
- Triggers (minimal overrides): grade change reaching `approved` or `rejected` notifies the requester (academic). Incident assignee change notifies the new assignee (security).
- Email channel: `mail.mail` created with `state='outgoing'` (Odoo mail queue; Odoo's own mail cron sends it when SMTP is configured). Odoo's own retries apply.
- Inbox channel: `mail.message` (`user_notification`, no thread) plus `mail.notification` with `notification_type='inbox'` for the recipient partner.
- Event log: `formula.notification.log` (user, category, channel, template, record reference, state `queued/skipped_pref/skipped_no_email/failed`, mail or message link). Read-only.
- Failures in one channel are logged and do not block the other channel or the business write (savepoint per channel, try/except per hook).

Tested (VERIFIED): queued email with `outgoing` state and inbox notification, opt-out respected for academic, security opt-out refused and security still queued, incident assignment notifies as security, grade decision notifies the requester.

NOT VERIFIED: SMTP delivery, rendering in a real mail client, and the access-request template (no access-request model is in the dependency set; not built).

## INT-04 SIEM (security events)

This is a separate stream from `university_isms_audit_chain` (`isms.audit.forward`, which forwards the audit hash chain). This module forwards security EVENTS:
- `login_success`, `login_failed` (hook on `res.users._login`; uses its own cursor so failed logins are still recorded).
- `incident_created`, `incident_state_changed`, `incident_escalated` (severity increase) on `isms.incident`.
- `privileged_group_change` on `res.users.write` when `groups_id` changes for system, erp manager, CISO, or registrar.
- `mfa_policy_block`: event type and `_emit_siem` exist. Not wired (see status table).

Privacy-aware payload (`formula.security-event.v1`):
```
schema, event_id (uuid), event_type, occurred_at (UTC), source, outcome,
actor: { user_id, login_hash = HMAC-SHA256(pseudonym_key, lower(login)), ip_hmac = HMAC-SHA256(pseudonym_key, ip) },
object: { model, record_id, ref }   (ref = ISMS incident code only)
attributes: whitelisted keys only (severity, state, from/to, category, groups names, ...)
```
- The pseudonym key is generated once into `ir.config_parameter` (`formula_integration_hub.pseudonym_key`). It is not tracked data.
- Never sent: raw IP, raw login, names, emails, incident title or description, grades.
- Only enabled SIEM endpoints receive events. With none enabled, the hooks do nothing.
- Delivery: outbox, backoff and dead-letter as above. Idempotency key is the event uuid.

Tested (VERIFIED): payload contains no raw IP, login, or name; HMAC format; unknown event type refused; login failure event without raw login; incident events emitted only when enabled; no event when disabled; privileged change event without login.

NOT VERIFIED: real SIEM ingestion, rotation of the pseudonym key (rotation breaks correlation with history by design), and `res.groups.users` writes (only `res.users.groups_id` writes are hooked).

## INT-05 API boundary

- Endpoints: `GET /api/formula/v1/ism/incidents/summary` (counts by state and severity), `GET /api/formula/v1/campus/offerings?limit=` (id, code, name, semester, state; no lecturer data).
- Enabled only when an endpoint of kind `api` is enabled. Otherwise 404 (no authentication attempted).
- Authentication: `Authorization: Bearer <Odoo API key>`, checked with `res.users.apikeys._check_credentials(scope='rpc')`. The key lookup is the only sudo step. Failures return 401 with `WWW-Authenticate: Bearer`.
- Authorization: the data call runs as the key owner (`request.env(user=uid)`), so ACLs and record rules apply. Insufficient rights return 403.
- Rate limiting: token bucket per key. Defaults: capacity 60 requests, refill 60 per minute. Configurable with `formula_integration_hub.api_rate_capacity` and `formula_integration_hub.api_rate_per_minute`. Exceeded returns 429 with `Retry-After`. Keys are identified by a SHA-256 prefix, never the raw key. The bucket lives in process memory (per worker) and is cleared above 10000 entries.
- CSRF: not applicable. The routes use `csrf=False` because they accept only a bearer header and never a browser session cookie. Do not add cookie-based auth to these routes.
- Errors are JSON: `{"error": {"code", "message"}}`.

Tested (VERIFIED): key authentication (valid, invalid, malformed header), per-key bucket and refill, service raises `RateLimited`, plain user receives `AccessError` on both resources, analyst summary counts, offerings field whitelist.

NOT VERIFIED: the HTTP layer (routing, headers, 404/401/403/429 status codes on a running server), `Retry-After` handling by clients, and multi-worker limits.

## Security decisions (summary)

1. Feature flags default OFF. Disabled endpoints send nothing and expose nothing.
2. Secrets are references only. Values come from `ir.config_parameter` or environment variables at send time. Errors are redacted. Secret values are never in views, payloads, or logs.
3. SSO cannot grant administrative groups automatically; the allowlist is enforced twice.
4. Moodle can only create drafts; ERP keeps final authority over scores and enrolments.
5. SIEM payloads are pseudonymized and whitelisted. The audit chain forwarder is untouched.
6. Security notifications are mandatory.
7. The API runs as the key owner with rate limits and no cookie auth.
8. Admin-only models: endpoints, outbox (contains payloads), mappings. CISO and auditor have read-only access to outbox, mappings, and the notification log.

## Test command and result

`MODULES=formula_integration_hub TAGS=/formula_integration_hub stage-test.sh`
Result: 38 tests, 0 failed, 0 errors. Log: `isms_ci_20261126204304_299677.log` (throwaway test database run).

## Known limitations and follow-ups

- Login hook (`res.users._login`) runs on a separate cursor and commits its event. It is not covered by an automated HTTP login test.
- SSO `provision_user` is not yet called from a login path. Wire it into `auth_oauth` (or another OIDC layer) only after the IdP is selected, and verify tokens there.
- Moodle create calls are not idempotent on the server side. Add `core_course_get_courses_by_field` and `core_user_get_users_by_field` lookups before create (future work).
- No automatic unenrolment from Moodle when an ERP enrolment is removed.
- Access-request mail template is not built.
- Rate limit is per worker. Use a DB-backed bucket if the API runs on several workers.
