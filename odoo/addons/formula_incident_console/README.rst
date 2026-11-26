==========================
Formula Incident Console
==========================

ISMS Incident Console (Phase 3 of the Formula ERP plan: WF-01, WF-02, WF-04 incident
part, WF-07, WF-08 incident part).

Model and API
=============

``formula.incident.console`` (AbstractModel), all methods run with the calling user's rights:

* ``get_incident_rows(filters)``: visible incidents, sorted by SLA urgency (open first, then
  remaining seconds ascending). ``filters`` keys: ``state``, ``severity``, ``overdue``, ``mine``.
  Invalid values are ignored. Capped at 200 rows, with the total count.
* ``get_incident_detail(incident_id)``: one incident. Raises ``AccessError`` when the record
  is not visible (no existence leak). Returns the timeline, affected assets (only if the
  ``asset_ids`` field is readable), attachment count, linked Helpdesk ticket (only if the
  ticket model is installed and readable), the investigation notes (analyst and auditor only),
  audit entries (auditor only) and the transitions with ``allowed`` and ``reason``.
* ``save_investigation(incident_id, values)``: writes only the note fields
  (containment, root_cause, resolution, lessons_learned, notification_note) through ORM ``write``.

Permissions
===========

* Lists and details come from ACL and record rules. Reporters see their own incidents only;
  analysts, auditors and CISO see all.
* Transition buttons call the existing ``isms.incident`` methods (``action_report``,
  ``action_investigate``, ``action_resolve``, ``action_close``, ``action_reopen``) through
  ``orm.call``. The UI only hides or disables buttons; the model re-checks group, state and
  required fields on every call.
* ``mail.tracking.value`` is admin-only in Odoo. The timeline reads it with ``sudo()`` and then
  keeps only the values the user may read (``_filter_has_field_access``), the same pattern as
  the Odoo chatter. Messages are still selected with the user's rights.

Dependencies
============

Depends on ``web`` and ``university_isms``. ``university_isms_helpdesk`` is not a declared
dependency: the linked ticket is shown only when that module and ``helpdesk_mgmt`` are installed.

Tests
=====

``odoo/addons/formula_incident_console/tests``, tags ``post_install``, ``-at_install``,
``formula_incident_console``. The bundle test compiles ``web.assets_backend`` CSS and fails on
any ``css_errors``.
