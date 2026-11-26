Formula Campus Portal
=====================

Student self-service pages and the lecturer portal for the Formula Campus records.
Depends on ``campus_university`` and ``campus_academic_plus``. Author Formula5 баг (ШУТИС МХТС),
license LGPL-3.

Student portal (``/my``)
------------------------

A "Миний хичээл" tile is added to the portal home for users that have a ``campus.student``
record. The pages live under ``/my/campus``:

* ``/my/campus``: GPA, credits, graduation eligibility and missing requirements, transcript link
* ``/my/campus/schedule?week=YYYY-MM-DD``: week view of sessions of enrolled offerings
* ``/my/campus/grades``: enrollments. Letter grade and grade point are shown only when completed.
  "Хичээл хасах" (POST) is shown only inside the add/drop window.
* ``/my/campus/attendance``: attendance counts per enrollment (own rows only)
* ``/my/campus/register``: open offerings of the open term with seats left.
  "Бүртгүүлэх" (POST ``/my/campus/register/<offering_id>``) calls ``register_offering``.
* ``/my/campus/requests``: grade-change decisions on own enrollments (read-only)
* ``/my/campus/notifications``: mail messages on the student's own record, enrollments and requests
* ``/my/campus/transcript.pdf``: transcript of the own student (academic report
  ``campus_academic_plus.action_report_transcript``)

Ownership and CSRF
~~~~~~~~~~~~~~~~~~

* Every route is ``auth='user'``. No route accepts a student id. The student is looked up as
  ``campus.student`` with ``user_id = current uid``.
* Every read runs in the user's environment, so the record rules of ``campus_university`` and
  ``campus_academic_plus`` apply. The module does not use ``sudo()``.
* POST routes keep Odoo's CSRF check. Foreign or unknown enrollment ids return 404.
* Registration and drop call ``campus.offering.register_student`` and
  ``campus.enrollment.action_drop`` in the user environment. Those methods check ownership,
  capacity, prerequisites, credit limit and clashes. Do not call them through ``sudo()``:
  ``is_registrar()`` treats a sudo environment as a registrar.

Lecturer portal (backend)
-------------------------

Menu "Багшийн портал" (``group_campus_lecturer``) opens the client action
``campus_portal_teacher`` (Owl component ``CampusTeacherPortal``). It calls the AbstractModel
``campus.portal.teacher`` with these methods:

* ``get_dashboard``, ``get_roster(offering_id)``, ``get_sessions(offering_id)``
* ``save_attendance(session_id, rows)``: calls ``campus.attendance.record`` per row
* ``request_grade_change(enrollment_id, proposed_score, reason, evidence_ref)``: creates
  ``campus.grade.change`` and calls ``action_submit``. The enrollment score is never written.
* ``get_notifications``

Each method checks the lecturer group. Offering ownership is checked explicitly, and the
record rules of the campus models apply on top. Lecturers cannot approve; the registrar
approves through ``campus.grade.change.action_approve``.

Limitations
-----------

* Portal-only accounts (no internal access) are not supported for campus data. The campus
  groups imply ``base.group_user``, and the campus record rules grant students nothing else.
  Those users see the "no student record" page. Supporting them requires new access rules
  in the academic addons, which are outside this addon.
* The lecturer Owl UI is checked by the asset compile test only. Browser checks at
  360/768/1440 px are NOT VERIFIED.

Tests
-----

Tags ``campus_portal``: HTTP tests for the student portal (ownership, 404 on foreign ids,
CSRF, registration, window and capacity rules, drop window, transcript), service tests for
the lecturer portal, and the asset compile test. Run with the project's test helper:

.. code-block:: bash

    MODULES=campus_portal TAGS=/campus_portal <stage-test-helper>
