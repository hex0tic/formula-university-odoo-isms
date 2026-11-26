==============================
Formula Command Center (ISMS)
==============================

ISMS Command Center: Phase 2 of the Formula ERP plan (tasks DASH-01, DASH-02,
DASH-03, DASH-05 core, DASH-08).

Model and API
=============

``formula.command.center`` (AbstractModel) exposes ``get_dashboard_data(filters)``:

* ``filters.incident_days`` is one of ``0`` (all time), ``30``, ``90``, ``365``.
  Any other value falls back to ``0``.
* Every count is computed with the calling user's ORM rights (ACL and record rules).
  ``sudo()`` is never used for counts.
* A section whose model the user cannot read (``has_access('read')`` is false) returns
  ``{"available": false}`` and no counts.
* Each KPI carries a ``drill`` descriptor ``{model, domain, name}``. The domain is built
  on the server from whitelisted values; the client cannot inject a domain.

Sections and their visibility (ISMS groups in university_isms):

* Assets: Asset Owner and above (ACL), owner sees all assets (ACL read is unrestricted).
* Risks and heatmap: Asset Owner sees risks they own or whose assets they own; Analyst,
  Auditor and CISO see all. Reporter gets an unavailable section.
* Controls: every ISMS group (Reporter reads the catalog).
* Incidents: Reporter sees only incidents they reported (record rule).
* Policies: Reporter sees approved policies only.
* Treatment tasks (project.task linked to a risk): require read on both project.task
  and isms.risk, so Reporter does not see risk-derived counts.
* Recent audit activity: Auditor and system administrators. Shows timestamp, action,
  model and object name only (no changes, IP, login or record names).

Menu
====

``Command Center`` sits under the ISMS root menu with ``group_isms_reporter``. The root
menu itself already requires that group, so the dashboard is available to every ISMS role.
Each section then shows only what the role may read.

Client
======

Action tag ``formula_command_center`` (``ir.actions.client``). The Owl component lives in
``static/src/command_center``. Drill-downs open ``act_window`` actions through the action
service. Labels are Mongolian. Styles use ``--fds-*`` tokens with fallbacks and do not
depend on ``formula_design_system``.

Tests
=====

``tests/test_command_center.py`` (tags ``post_install``, ``-at_install``,
``formula_command_center``) covers role-based KPI parity with ``search_count``, reporter and
analyst restrictions, heatmap cell parity, drill-down parity, JSON safety and empty data.

Known limitations
=================

* Client-side (OWL) behaviour is not covered by automated HOOT tests in this module.
* Dark theme is not styled.
* Historical trends (DASH-04) and CSV export (DASH-07) are not implemented.
