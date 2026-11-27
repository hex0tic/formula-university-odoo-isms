# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
"""Shared fixtures. Fixtures are created with sudo in setUp only; the tests then act as real users."""
from datetime import timedelta

from odoo import fields
from odoo.tests.common import new_test_user

STUDENT_GROUPS = "campus_university.group_campus_student"
LECTURER_GROUPS = "base.group_user,campus_university.group_campus_lecturer"
REGISTRAR_GROUPS = "base.group_user,campus_university.group_campus_registrar"
PLAIN_GROUPS = "base.group_user"


class CampusPortalFixtures:
    """Mixin with two students, two lecturers, one registrar and one open term."""

    @classmethod
    def _make_fixtures(cls):
        env = cls.env
        today = fields.Date.context_today(env.user)
        cls.student_a_user = new_test_user(env, login="cp_student_a", groups=STUDENT_GROUPS)
        cls.student_b_user = new_test_user(env, login="cp_student_b", groups=STUDENT_GROUPS)
        cls.student_c_user = new_test_user(env, login="cp_student_c", groups=STUDENT_GROUPS)
        cls.lecturer_a = new_test_user(env, login="cp_lecturer_a", groups=LECTURER_GROUPS)
        cls.lecturer_b = new_test_user(env, login="cp_lecturer_b", groups=LECTURER_GROUPS)
        cls.registrar = new_test_user(env, login="cp_registrar", groups=REGISTRAR_GROUPS)
        cls.plain_user = new_test_user(env, login="cp_plain_user", groups=PLAIN_GROUPS)

        Sudo = env(su=True)
        cls.program = Sudo["campus.program"].create({
            "code": "CP-PRG", "name": "Portal test program", "department": "Test faculty",
            "required_credits": 6,
        })
        cls.course_x = Sudo["campus.course"].create({
            "code": "CP-101", "name": "Portal course X", "credits": 3, "program_id": cls.program.id,
        })
        cls.course_y = Sudo["campus.course"].create({
            "code": "CP-102", "name": "Portal course Y", "credits": 3, "program_id": cls.program.id,
        })
        Term = Sudo["campus.academic.term"]
        # Keep the fixture current even when testing against a populated campus.
        # The surrounding test transaction rolls back these state changes.
        Term.search([("state", "=", "open")]).write({"state": "closed"})
        cls.term = Term.create({
            "name": "Portal test term", "code": "CP-2026-A",
            "date_start": today - timedelta(days=30), "date_end": today + timedelta(days=90),
            "registration_start": today - timedelta(days=10), "registration_end": today + timedelta(days=10),
            "add_drop_end": today + timedelta(days=14), "state": "open",
        })
        cls.student_a = Sudo["campus.student"].create({
            "student_code": "CP-A", "name": "Portal Student A", "user_id": cls.student_a_user.id,
            "program_id": cls.program.id,
        })
        cls.student_b = Sudo["campus.student"].create({
            "student_code": "CP-B", "name": "Portal Student B", "user_id": cls.student_b_user.id,
            "program_id": cls.program.id,
        })
        cls.student_c = Sudo["campus.student"].create({
            "student_code": "CP-C", "name": "Portal Student C", "user_id": cls.student_c_user.id,
            "program_id": cls.program.id,
        })
        cls.offering_x = Sudo["campus.offering"].create({
            "name": "Portal section X", "course_id": cls.course_x.id, "semester": "CP-2026-A",
            "lecturer_id": cls.lecturer_a.id, "state": "open", "term_id": cls.term.id, "capacity": 30,
        })
        cls.offering_y = Sudo["campus.offering"].create({
            "name": "Portal section Y", "course_id": cls.course_y.id, "semester": "CP-2026-A",
            "lecturer_id": cls.lecturer_b.id, "state": "open", "term_id": cls.term.id, "capacity": 30,
        })
        # Student A is enrolled in X; student B is enrolled in Y (the other student's record).
        cls.enrollment_a = Sudo["campus.enrollment"].create({
            "student_id": cls.student_a.id, "offering_id": cls.offering_x.id,
        })
        cls.enrollment_b = Sudo["campus.enrollment"].create({
            "student_id": cls.student_b.id, "offering_id": cls.offering_y.id,
        })
        cls.session_x = Sudo["campus.session"].create({
            "offering_id": cls.offering_x.id,
            "start": fields.Datetime.now().replace(hour=2, minute=0, second=0, microsecond=0) + timedelta(days=1),
            "end": fields.Datetime.now().replace(hour=3, minute=30, second=0, microsecond=0) + timedelta(days=1),
            "room": "CP-R1", "kind": "lecture",
        })
        cls.session_y = Sudo["campus.session"].create({
            "offering_id": cls.offering_y.id,
            "start": fields.Datetime.now().replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1),
            "end": fields.Datetime.now().replace(hour=7, minute=30, second=0, microsecond=0) + timedelta(days=1),
            "room": "CP-R2", "kind": "lab",
        })
