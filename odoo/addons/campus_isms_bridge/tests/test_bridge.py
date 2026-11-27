from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCampusIsmsBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrar = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Bridge test registrar", "login": "bridge.test.registrar",
            "groups_id": [Command.set([cls.env.ref("campus_university.group_campus_registrar").id])],
        })
        cls.reviewer = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Bridge test reviewer", "login": "bridge.test.reviewer",
            "groups_id": [Command.set([cls.env.ref("campus_university.group_campus_registrar").id])],
        })
        cls.program = cls.env["campus.program"].create({
            "code": "BRIDGE-TEST", "name": "Test", "department": "Test",
        })
        cls.course = cls.env["campus.course"].create({
            "code": "BRIDGE-338", "name": "Test", "program_id": cls.program.id,
        })
        cls.offering = cls.env["campus.offering"].create({
            "name": "Bridge test", "course_id": cls.course.id,
            "lecturer_id": cls.registrar.id, "state": "locked",
        })
        cls.student = cls.env["campus.student"].sudo().create({
            "student_code": "BRIDGE-001", "name": "Bridge synthetic student",
            "program_id": cls.program.id,
        })
        cls.enrollment = cls.env["campus.enrollment"].sudo().create({
            "student_id": cls.student.id, "offering_id": cls.offering.id, "score": 70,
        })

    def test_approval_has_correct_actor_and_grade_preimage(self):
        request = self.env["campus.grade.change"].with_user(self.registrar).create({
            "enrollment_id": self.enrollment.id, "proposed_score": 82,
            "reason": "Баталгаатай шалгалтын протоколын нийт оноог залруулах.",
        })
        request.action_submit()
        request.with_user(self.reviewer).action_approve()
        logs = self.env["isms.audit.log"].sudo().search([
            ("model", "=", "campus.enrollment"), ("res_id", "=", self.enrollment.id),
            ("action", "=", "write"),
        ])
        self.assertTrue(logs, "Approved score change must enter the audit log")
        self.assertEqual(logs[0].user_id, self.reviewer)
        self.assertIn("70", logs[0].changes)
        self.assertIn("82", logs[0].changes)
        decision_log = self.env["isms.audit.log"].sudo().search([
            ("model", "=", "campus.grade.change"), ("res_id", "=", request.id),
            ("action", "=", "state"), ("user_id", "=", self.reviewer.id),
        ])
        self.assertTrue(decision_log)

    def test_untrusted_skip_context_cannot_disable_academic_audit(self):
        student = self.student.with_user(self.registrar)
        before = self.env["isms.audit.log"].sudo().search_count([
            ("model", "=", "campus.student"), ("res_id", "=", student.id),
        ])
        student.with_context(isms_audit_skip=True).write({"institutional_email": "changed@orgil.example"})
        after = self.env["isms.audit.log"].sudo().search_count([
            ("model", "=", "campus.student"), ("res_id", "=", student.id),
        ])
        self.assertGreater(after, before)

    def test_registrar_cannot_tamper_with_logs(self):
        log = self.env["isms.audit.log"].sudo().search([
            ("model", "=", "campus.student"), ("res_id", "=", self.student.id),
        ], limit=1)
        self.assertTrue(log)
        with self.assertRaises(UserError):
            log.with_user(self.registrar).write({"changes": "forged"})
        with self.assertRaises(UserError):
            log.with_user(self.registrar).unlink()

    def test_internal_isms_rights_are_assigned_separately(self):
        reporter = self.env.ref("university_isms.group_isms_reporter")
        self.assertFalse(self.registrar.has_group("university_isms.group_isms_reporter"))
        with self.assertRaises(AccessError):
            self.env["isms.incident"].with_user(self.registrar).search([])
        self.registrar.write({"groups_id": [Command.link(reporter.id)]})
        incident = self.env["isms.incident"].with_user(self.registrar).create({
            "name": "Сэжигтэй «дүн засах» и-мэйл ирсэн", "category": "phishing", "reporter_type": "staff",
        })
        incident.with_user(self.registrar).action_report()
        self.assertEqual((incident.state, incident.reporter_id), ("report", self.registrar))
        with self.assertRaises(AccessError):
            self.env["isms.asset"].with_user(self.registrar).search([])
