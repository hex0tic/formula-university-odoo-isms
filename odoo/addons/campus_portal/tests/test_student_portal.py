# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
import json
from datetime import timedelta
from urllib.parse import urlsplit

from odoo import fields, http
from odoo.tests import HttpCase, tagged

from .common import CampusPortalFixtures


@tagged("post_install", "-at_install", "campus_portal")
class TestStudentPortal(CampusPortalFixtures, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._make_fixtures()

    def _csrf(self):
        return http.Request.csrf_token(self)

    def _login(self, user):
        self.authenticate(user.login, user.login)

    # ------------------------------------------------------------ ownership
    def test_student_sees_only_own_records(self):
        self._login(self.student_a_user)
        resp = self.url_open("/my/campus/grades")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("CP-101", resp.text)
        self.assertNotIn("CP-102", resp.text)
        self.assertNotIn("Portal Student B", resp.text)

    def test_other_students_enrollment_drop_returns_404(self):
        self._login(self.student_a_user)
        resp = self.url_open("/my/campus/drop/%s" % self.enrollment_b.id, data={"csrf_token": self._csrf()})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.enrollment_b.sudo().reg_state, "enrolled")

    def test_unknown_enrollment_id_returns_404_like_foreign_id(self):
        self._login(self.student_a_user)
        resp = self.url_open("/my/campus/drop/999999999", data={"csrf_token": self._csrf()})
        self.assertEqual(resp.status_code, 404)

    def test_user_without_student_record_sees_no_data(self):
        self._login(self.plain_user)
        resp = self.url_open("/my/campus/grades")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("оюутны бүртгэл холбогдоогүй", resp.text.lower())
        self.assertNotIn("CP-101", resp.text)
        transcript = self.url_open("/my/campus/transcript.pdf")
        self.assertEqual(transcript.status_code, 404)

    def test_schedule_contains_only_own_sessions(self):
        self._login(self.student_a_user)
        resp = self.url_open("/my/campus/schedule?week=%s" % fields.Date.context_today(self.env.user))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("CP-R1", resp.text)
        self.assertNotIn("CP-R2", resp.text)

    # ------------------------------------------------------------ registration
    def test_register_post_creates_enrollment_for_own_student(self):
        self._login(self.student_c_user)
        before = self.env["campus.enrollment"].sudo().search_count([("offering_id", "=", self.offering_y.id)])
        resp = self.url_open("/my/campus/register/%s" % self.offering_y.id, data={"csrf_token": self._csrf()})
        self.assertEqual(resp.status_code, 200)
        after = self.env["campus.enrollment"].sudo().search_count([("offering_id", "=", self.offering_y.id)])
        self.assertEqual(after, before + 1)
        enrollment = self.env["campus.enrollment"].sudo().search([
            ("offering_id", "=", self.offering_y.id), ("student_id", "=", self.student_c.id),
        ], limit=1)
        self.assertEqual(enrollment.reg_state, "enrolled")
        self.assertEqual(enrollment.registered_by_id, self.student_c_user)

    def test_register_without_csrf_is_rejected(self):
        self._login(self.student_c_user)
        resp = self.url_open("/my/campus/register/%s" % self.offering_y.id, data={})
        self.assertNotEqual(resp.status_code, 200)
        exists = self.env["campus.enrollment"].sudo().search_count([
            ("offering_id", "=", self.offering_y.id), ("student_id", "=", self.student_c.id),
        ])
        self.assertEqual(exists, 0)

    def test_register_rejected_when_seats_are_full(self):
        self.offering_y.sudo().capacity = 1  # student B already holds the only seat
        self._login(self.student_c_user)
        self.url_open("/my/campus/register/%s" % self.offering_y.id, data={"csrf_token": self._csrf()})
        exists = self.env["campus.enrollment"].sudo().search_count([
            ("offering_id", "=", self.offering_y.id), ("student_id", "=", self.student_c.id),
        ])
        self.assertEqual(exists, 0)

    def test_register_rejected_after_registration_window(self):
        self.term.sudo().registration_end = fields.Date.context_today(self.env.user) - timedelta(days=1)
        self._login(self.student_c_user)
        self.url_open("/my/campus/register/%s" % self.offering_y.id, data={"csrf_token": self._csrf()})
        exists = self.env["campus.enrollment"].sudo().search_count([
            ("offering_id", "=", self.offering_y.id), ("student_id", "=", self.student_c.id),
        ])
        self.assertEqual(exists, 0)

    # ------------------------------------------------------------ drop window
    def test_drop_own_enrollment_inside_window(self):
        self._login(self.student_a_user)
        self.url_open("/my/campus/drop/%s" % self.enrollment_a.id, data={"csrf_token": self._csrf()})
        self.assertEqual(self.enrollment_a.sudo().reg_state, "dropped")

    def test_drop_rejected_after_add_drop_window(self):
        today = fields.Date.context_today(self.env.user)
        # The term constraint requires registration_end <= add_drop_end, so both move back together.
        self.term.sudo().write({
            "registration_end": today - timedelta(days=2),
            "add_drop_end": today - timedelta(days=1),
        })
        self._login(self.student_a_user)
        self.url_open("/my/campus/drop/%s" % self.enrollment_a.id, data={"csrf_token": self._csrf()})
        self.assertEqual(self.enrollment_a.sudo().reg_state, "enrolled")

    def test_drop_without_csrf_is_rejected(self):
        self._login(self.student_a_user)
        resp = self.url_open("/my/campus/drop/%s" % self.enrollment_a.id, data={})
        self.assertNotEqual(resp.status_code, 200)
        self.assertEqual(self.enrollment_a.sudo().reg_state, "enrolled")

    # ------------------------------------------------------------ transcript
    def test_transcript_pdf_is_own_only(self):
        self._login(self.student_a_user)
        resp = self.url_open("/my/campus/transcript.pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/pdf", resp.headers.get("Content-Type", ""))
        # Odoo renders reports as HTML while --test-enable is set (no wkhtmltopdf call), so the body
        # is either a real PDF or the report HTML. Either way it must contain only the own student.
        if not resp.content.startswith(b"%PDF"):
            self.assertIn(b"CP-A", resp.content)
            self.assertNotIn(b"CP-B", resp.content)
            self.assertNotIn(b"Portal Student B", resp.content)

    # ------------------------------------------------------------ smoke: every page renders
    def test_all_student_pages_render_for_own_student(self):
        self._login(self.student_a_user)
        for path in ("/my/campus", "/my/campus/grades", "/my/campus/schedule", "/my/campus/attendance",
                     "/my/campus/register", "/my/campus/requests", "/my/campus/notifications", "/my"):
            resp = self.url_open(path)
            self.assertEqual(resp.status_code, 200, path)
            self.assertNotIn("Server Error", resp.text, path)
            self.assertNotIn("Traceback", resp.text, path)

    def test_home_tile_only_for_campus_student(self):
        self._login(self.student_a_user)
        self.assertIn("/my/campus", self.url_open("/my").text)
        self.authenticate(self.plain_user.login, self.plain_user.login)
        self.assertNotIn("/my/campus", self.url_open("/my").text)

    def test_campus_home_flag_is_not_a_counter(self):
        self._login(self.student_a_user)
        response = self.url_open(
            "/my/counters",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": {"counters": []}}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("campus_has_student", response.json()["result"])

    def test_registration_page_without_academic_access_shows_account_hint(self):
        self._login(self.plain_user)
        response = self.url_open("/my/campus/register")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Оюутны бүртгэл холбогдоогүй", response.text)

    def test_teacher_entry_requires_teacher_account(self):
        self._login(self.student_a_user)
        denied = self.url_open("/campus/teacher", allow_redirects=False)
        self.assertEqual(denied.status_code, 403)
        self.assertIn("/web/session/logout?redirect=/campus/teacher", denied.text)
        self._login(self.lecturer_a)
        allowed = self.url_open("/campus/teacher", allow_redirects=False)
        self.assertEqual(allowed.status_code, 200)
        self.assertIn("Миний хичээлүүд", allowed.text)
        self.assertIn("/odoo/action-campus_portal.action_campus_teacher_portal", allowed.text)

    def test_student_is_portal_user_and_cannot_open_backend(self):
        self.assertTrue(self.student_a_user.has_group("base.group_portal"))
        self.assertFalse(self.student_a_user.has_group("base.group_user"))
        self._login(self.student_a_user)
        response = self.url_open("/odoo", allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn(urlsplit(response.headers["Location"]).path, {"/my", "/web/login_successful"})
