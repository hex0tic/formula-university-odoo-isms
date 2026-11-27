# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
from lxml import html

from odoo.tests import HttpCase, tagged

from .common import CampusPortalFixtures

ROOT = "/campus/teacher"


@tagged("post_install", "-at_install", "campus_portal")
class TestTeacherWeb(CampusPortalFixtures, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._make_fixtures()

    def setUp(self):
        super().setUp()
        self.authenticate(self.lecturer_a.login, self.lecturer_a.login)

    def _csrf_from_form(self, path):
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200)
        document = html.fromstring(response.text)
        tokens = document.xpath("//form[@action=$path]//input[@name='csrf_token']/@value", path=path)
        self.assertEqual(len(tokens), 1, path)
        return tokens[0]

    def test_web_pages_render_assigned_classes(self):
        dashboard = self.url_open(ROOT, allow_redirects=False)
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("no-store", dashboard.headers.get("Cache-Control", ""))
        self.assertIn("Portal section X", dashboard.text)
        self.assertNotIn("Portal section Y", dashboard.text)

        offering = self.url_open(f"{ROOT}/offerings/{self.offering_x.id}")
        self.assertEqual(offering.status_code, 200)
        self.assertIn("Portal Student A", offering.text)
        self.assertNotIn("Portal Student B", offering.text)
        self.assertIn("CP-R1", offering.text)
        self.assertEqual(self.url_open(f"{ROOT}/notifications").status_code, 200)

    def test_teachers_cannot_open_another_teachers_details(self):
        for route, record in (
            ("offerings", self.offering_y),
            ("sessions", self.session_y),
            ("grades", self.enrollment_b),
        ):
            with self.subTest(route=route):
                self.assertEqual(self.url_open(f"{ROOT}/{route}/{record.id}").status_code, 404)

    def test_web_attendance_requires_csrf_and_saves_selected_status(self):
        path = f"{ROOT}/sessions/{self.session_x.id}"
        token = self._csrf_from_form(path)
        selections = {f"attendance_{self.enrollment_a.id}": "late"}
        domain = [("session_id", "=", self.session_x.id), ("enrollment_id", "=", self.enrollment_a.id)]
        attendance = self.env["campus.attendance"].sudo()

        rejected = self.url_open(path, data=selections, allow_redirects=False)
        self.assertGreaterEqual(rejected.status_code, 400)
        self.assertFalse(attendance.search(domain))

        saved = self.url_open(path, data={**selections, "csrf_token": token}, allow_redirects=False)
        self.assertEqual(saved.status_code, 303)
        record = attendance.search(domain)
        self.assertEqual(record.status, "late")
        self.assertEqual(record.recorded_by, self.lecturer_a)

    def test_grade_request_requires_csrf_and_rolls_back_rejected_draft(self):
        path = f"{ROOT}/grades/{self.enrollment_a.id}"
        token = self._csrf_from_form(path)
        score_before = self.enrollment_a.score
        data = {"score": "88", "reason": "Шалгалтын нийлбэрийг залруулах шаардлагатай."}
        changes = self.env["campus.grade.change"].sudo()
        domain = [("enrollment_id", "=", self.enrollment_a.id)]

        rejected = self.url_open(path, data=data, allow_redirects=False)
        self.assertGreaterEqual(rejected.status_code, 400)
        self.assertFalse(changes.search(domain))

        unchanged = self.url_open(path, data={**data, "score": str(score_before), "csrf_token": token})
        self.assertEqual(unchanged.status_code, 400)
        self.assertIn(data["reason"], unchanged.text)
        self.assertFalse(changes.search(domain))

        submitted = self.url_open(path, data={**data, "csrf_token": token}, allow_redirects=False)
        self.assertEqual(submitted.status_code, 303)
        change = changes.search(domain)
        self.assertEqual(change.state, "submitted")
        self.assertEqual(change.requester_id, self.lecturer_a)
        self.enrollment_a.invalidate_recordset(["score"])
        self.assertEqual(self.enrollment_a.score, score_before)
