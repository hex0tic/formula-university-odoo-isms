# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from .common import CampusPortalFixtures

REASON = "Шалгалтын протоколын нийлбэрийг залруулах шаардлагатай."


@tagged("post_install", "-at_install", "campus_portal")
class TestTeacherPortal(CampusPortalFixtures, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._make_fixtures()

    def _svc(self, user):
        return self.env["campus.portal.teacher"].with_user(user)

    # ------------------------------------------------------------ own offerings only
    def test_dashboard_lists_only_own_offerings(self):
        data = self._svc(self.lecturer_a).get_dashboard()
        ids = [o["id"] for o in data["offerings"]]
        self.assertEqual(ids, [self.offering_x.id])
        self.assertNotIn(self.offering_y.id, ids)

    def test_roster_of_other_lecturer_is_refused(self):
        with self.assertRaises(AccessError):
            self._svc(self.lecturer_a).get_roster(self.offering_y.id)

    def test_roster_of_own_offering_is_returned(self):
        data = self._svc(self.lecturer_a).get_roster(self.offering_x.id)
        self.assertEqual([r["enrollment_id"] for r in data["rows"]], [self.enrollment_a.id])

    def test_student_cannot_use_teacher_service(self):
        with self.assertRaises(AccessError):
            self._svc(self.student_a_user).get_dashboard()

    def test_plain_user_cannot_use_teacher_service(self):
        with self.assertRaises(AccessError):
            self._svc(self.plain_user).get_dashboard()

    # ------------------------------------------------------------ attendance
    def test_attendance_for_other_sessions_is_refused(self):
        with self.assertRaises(AccessError):
            self._svc(self.lecturer_a).save_attendance(
                self.session_y.id, [{"enrollment_id": self.enrollment_b.id, "status": "present"}])
        self.assertFalse(self.env["campus.attendance"].sudo().search_count([("session_id", "=", self.session_y.id)]))

    def test_attendance_rejects_enrollment_of_other_offering(self):
        with self.assertRaises(AccessError):
            self._svc(self.lecturer_a).save_attendance(
                self.session_x.id, [{"enrollment_id": self.enrollment_b.id, "status": "present"}])

    def test_attendance_rejects_unknown_status(self):
        with self.assertRaises(ValidationError):
            self._svc(self.lecturer_a).save_attendance(
                self.session_x.id, [{"enrollment_id": self.enrollment_a.id, "status": "vacation"}])

    def test_attendance_for_own_session_is_recorded_by_lecturer(self):
        self._svc(self.lecturer_a).save_attendance(
            self.session_x.id, [{"enrollment_id": self.enrollment_a.id, "status": "late"}])
        record = self.env["campus.attendance"].sudo().search([
            ("session_id", "=", self.session_x.id), ("enrollment_id", "=", self.enrollment_a.id),
        ])
        self.assertEqual(record.status, "late")
        self.assertEqual(record.recorded_by, self.lecturer_a)

    # ------------------------------------------------------------ grade entry
    def test_grade_entry_creates_submitted_request_and_keeps_score(self):
        score_before = self.enrollment_a.sudo().score
        result = self._svc(self.lecturer_a).request_grade_change(
            self.enrollment_a.id, 88, REASON, "MINUTES-1")
        self.assertEqual(result["state"], "submitted")
        change = self.env["campus.grade.change"].sudo().browse(result["id"])
        self.assertEqual(change.requester_id, self.lecturer_a)
        self.assertEqual(change.proposed_score, 88)
        self.assertEqual(self.enrollment_a.sudo().score, score_before)
        self.assertEqual(self.enrollment_a.sudo().grade_revision, 0)

    def test_grade_entry_for_other_lecturers_enrollment_is_refused(self):
        with self.assertRaises(AccessError):
            self._svc(self.lecturer_a).request_grade_change(self.enrollment_b.id, 90, REASON)

    def test_grade_entry_rejects_out_of_range_score(self):
        with self.assertRaises(ValidationError):
            self._svc(self.lecturer_a).request_grade_change(self.enrollment_a.id, 140, REASON)

    def test_lecturer_cannot_approve_own_request(self):
        result = self._svc(self.lecturer_a).request_grade_change(self.enrollment_a.id, 88, REASON)
        change = self.env["campus.grade.change"].with_user(self.lecturer_a).browse(result["id"])
        with self.assertRaises(AccessError):
            change.action_approve()
        self.assertEqual(self.enrollment_a.sudo().score, 0)

    def test_pending_count_counts_only_own_submitted_requests(self):
        self._svc(self.lecturer_a).request_grade_change(self.enrollment_a.id, 88, REASON)
        data = self._svc(self.lecturer_a).get_dashboard()
        self.assertEqual(data["pending_count"], 1)
        other = self._svc(self.lecturer_b).get_dashboard()
        self.assertEqual(other["pending_count"], 0)

    # ------------------------------------------------------------ read methods stay scoped
    def test_sessions_and_notifications_are_own_only(self):
        sessions = self._svc(self.lecturer_a).get_sessions(self.offering_x.id)
        self.assertEqual([s["id"] for s in sessions["sessions"]], [self.session_x.id])
        with self.assertRaises(AccessError):
            self._svc(self.lecturer_a).get_sessions(self.offering_y.id)
        self.assertIsInstance(self._svc(self.lecturer_a).get_notifications(), list)
