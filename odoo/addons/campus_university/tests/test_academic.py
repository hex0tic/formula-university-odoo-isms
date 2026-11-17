from psycopg2 import IntegrityError
from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestCampusAcademic(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.users = {}
        for login, role in [
            ("lecturer", "lecturer"), ("other_lecturer", "lecturer"),
            ("registrar", "registrar"), ("second_registrar", "registrar"),
            ("student", "student"), ("other_student", "student"), ("auditor", "auditor"),
        ]:
            cls.users[login] = cls.env["res.users"].with_context(no_reset_password=True).create({
                "name": "Campus test " + login,
                "login": "campus.test." + login,
                "groups_id": [Command.set([cls.env.ref("campus_university.group_campus_" + role).id])],
            })
        cls.program = cls.env["campus.program"].create({
            "code": "TEST-SEC", "name": "Test security", "department": "Test faculty",
        })
        cls.course = cls.env["campus.course"].create({
            "code": "TEST-338", "name": "Test governance", "credits": 3, "program_id": cls.program.id,
        })
        cls.offering = cls.env["campus.offering"].create({
            "name": "Test closed semester", "course_id": cls.course.id,
            "semester": "TEST-2026-A", "lecturer_id": cls.users["lecturer"].id, "state": "locked",
        })
        cls.other_offering = cls.env["campus.offering"].create({
            "name": "Other faculty semester", "course_id": cls.course.id,
            "semester": "TEST-2026-A", "lecturer_id": cls.users["other_lecturer"].id, "state": "open",
        })
        cls.students = cls.env["campus.student"].create([
            {"student_code": "TEST-001", "name": "Test Anar", "user_id": cls.users["student"].id,
             "program_id": cls.program.id, "institutional_email": "test.anar@orgil.example"},
            {"student_code": "TEST-002", "name": "Test Nomin", "user_id": cls.users["other_student"].id,
             "program_id": cls.program.id, "institutional_email": "test.nomin@orgil.example"},
        ])
        cls.enrollment = cls.env["campus.enrollment"].sudo().create({
            "student_id": cls.students[0].id, "offering_id": cls.offering.id, "score": 72,
        })
        cls.other_enrollment = cls.env["campus.enrollment"].sudo().create({
            "student_id": cls.students[1].id, "offering_id": cls.other_offering.id, "score": 81,
        })

    def _request(self, user="lecturer", score=85):
        return self.env["campus.grade.change"].with_user(self.users[user]).create({
            "enrollment_id": self.enrollment.id,
            "proposed_score": score,
            "reason": "Шалгалтын баталгаажсан протоколын нийлбэрийг залруулах.",
            "evidence_ref": "TEST-MINUTES-01",
        })

    def test_independent_approval_changes_grade_once(self):
        request = self._request()
        request.action_submit()
        self.assertEqual(self.enrollment.score, 72)
        request.with_user(self.users["registrar"]).action_approve()
        self.enrollment.invalidate_recordset()
        self.assertEqual(self.enrollment.score, 85)
        self.assertEqual(self.enrollment.grade_revision, 1)
        self.assertEqual(request.approver_id, self.users["registrar"])
        self.assertEqual(request.requester_id, self.users["lecturer"])
        self.assertEqual(request.state, "approved")
        self.assertTrue(request.approved_at)
        with self.assertRaises(ValidationError):
            request.with_user(self.users["registrar"]).action_approve()

    def test_requester_cannot_approve_own_request(self):
        request = self._request(user="registrar")
        request.action_submit()
        with self.assertRaises(AccessError):
            request.action_approve()
        self.assertEqual(request.state, "submitted")
        self.assertEqual(self.enrollment.score, 72)

    def test_student_record_isolation_and_write_denial(self):
        student_env = self.env["campus.student"].with_user(self.users["student"])
        visible = student_env.search([])
        self.assertIn(self.students[0].id, visible.ids)
        self.assertNotIn(self.students[1].id, visible.ids)
        with self.assertRaises(AccessError):
            self.students[1].with_user(self.users["student"]).read(["name"])
        with self.assertRaises(AccessError):
            self.enrollment.with_user(self.users["student"]).write({"score": 99})
        with self.assertRaises(AccessError):
            self._request(user="student")

    def test_lecturer_cannot_access_other_class(self):
        own = self.env["campus.enrollment"].with_user(self.users["lecturer"]).search([])
        self.assertIn(self.enrollment.id, own.ids)
        self.assertNotIn(self.other_enrollment.id, own.ids)
        with self.assertRaises(AccessError):
            self.env["campus.grade.change"].with_user(self.users["lecturer"]).create({
                "enrollment_id": self.other_enrollment.id, "proposed_score": 91,
                "reason": "Өөр багшийн хичээлийн бүртгэлийг өөрчлөх оролдлого.",
            })

    def test_enrollment_picker_search_finds_only_assigned_student(self):
        picker = self.env["campus.enrollment"].with_user(self.users["lecturer"])
        found = dict(picker.name_search("Test Anar"))
        self.assertIn(self.enrollment.id, found)
        self.assertIn("Test Anar", found[self.enrollment.id])
        self.assertNotIn(self.other_enrollment.id, dict(picker.name_search("Test Nomin")))

    def test_auditor_is_read_only(self):
        self.assertTrue(self.enrollment.with_user(self.users["auditor"]).read(["score"]))
        with self.assertRaises(AccessError):
            self.enrollment.with_user(self.users["auditor"]).write({"student_id": self.students[1].id})
        with self.assertRaises(AccessError):
            self._request(user="auditor")

    def test_forged_context_and_direct_state_write_are_denied(self):
        with self.assertRaises(AccessError):
            self.enrollment.with_user(self.users["registrar"]).with_context(
                _campus_grade_authority=True,
            ).write({"score": 100})
        request = self._request()
        with self.assertRaises(AccessError):
            request.with_context(_campus_review_authority=True).write({"state": "approved"})
        with self.assertRaises(AccessError):
            request.write({"requester_id": self.users["registrar"].id})
        with self.assertRaises(AccessError):
            request.write({"old_score": 100})

    def test_stale_approval_cannot_overwrite_new_grade(self):
        first = self._request(score=85)
        second = self._request(score=90)
        first.action_submit()
        second.action_submit()
        first.with_user(self.users["registrar"]).action_approve()
        with self.assertRaises(ValidationError):
            second.with_user(self.users["registrar"]).action_approve()
        self.assertEqual(self.enrollment.score, 85)
        self.assertEqual(self.enrollment.grade_revision, 1)
        self.assertEqual(second.state, "submitted")

    def test_submitted_request_is_frozen_and_rejection_needs_reason(self):
        request = self._request()
        request.action_submit()
        with self.assertRaises(AccessError):
            request.write({"proposed_score": 99})
        with self.assertRaises(AccessError):
            request.unlink()
        reviewer = request.with_user(self.users["registrar"])
        with self.assertRaises(ValidationError):
            reviewer.action_reject()
        reviewer.write({"review_note": "Протоколын эх баримт хангалтгүй тул татгалзав."})
        reviewer.action_reject()
        self.assertEqual(request.state, "rejected")
        self.assertEqual(self.enrollment.score, 72)

    def test_create_cannot_forge_requester_or_approval(self):
        for extra in [{"requester_id": self.users["registrar"].id}, {"state": "approved"},
                      {"old_score": 0}, {"approver_id": self.users["registrar"].id}]:
            with self.assertRaises(AccessError):
                self.env["campus.grade.change"].with_user(self.users["lecturer"]).create({
                    "enrollment_id": self.enrollment.id, "proposed_score": 88,
                    "reason": "Үндсэн бүртгэл хуурч оруулах оролдлогын тест.", **extra,
                })

    @mute_logger("odoo.sql_db")
    def test_out_of_range_score_is_rejected(self):
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self._request(score=101)
