from lxml.html import fromstring

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestCampusIncidentPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = new_test_user(cls.env, login="incident_student",
                                    groups="campus_university.group_campus_student")
        cls.teacher = new_test_user(cls.env, login="incident_teacher",
                                    groups="campus_university.group_campus_lecturer")
        cls.other = new_test_user(cls.env, login="incident_staff", groups="base.group_user")
        cls.analyst = new_test_user(cls.env, login="incident_ciso",
                                    groups="university_isms.group_isms_analyst")
        program = cls.env["campus.program"].create({
            "code": "INC-CP", "name": "Incident test programme", "department": "Technology",
        })
        cls.env["campus.student"].create({
            "student_code": "INC-CP-01", "name": "Incident test student",
            "user_id": cls.student.id, "program_id": program.id,
        })

    def _submit(self, user, title):
        self.authenticate(user.login, user.login)
        page = self.url_open("/my/campus/incidents")
        self.assertEqual(page.status_code, 200)
        csrf = fromstring(page.text).xpath("//form[@action='/my/campus/incidents']/input[@name='csrf_token']/@value")[0]
        response = self.url_open("/my/campus/incidents", data={
            "csrf_token": csrf, "name": title, "category": "phishing",
            "description": "A fake invitation to a grade portal arrived in my inbox.",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("Мэдээллийг хүлээн авлаа", response.text)
        return response

    def test_student_and_teacher_can_report_without_direct_isms_access(self):
        student_report = "Suspicious email reported by student"
        teacher_report = "Suspicious email reported by lecturer"
        self._submit(self.student, student_report)
        response = self._submit(self.teacher, teacher_report)
        self.assertNotIn(student_report, response.text)
        self.authenticate(self.student.login, self.student.login)
        self.assertNotIn(teacher_report, self.url_open("/my/campus/incidents").text)
        model = self.env["isms.incident"]
        for user, title, role in [(self.student, student_report, "student"),
                                  (self.teacher, teacher_report, "faculty")]:
            case = model.with_user(self.analyst).search([("name", "=", title)], limit=1)
            self.assertEqual((case.reporter_id.id, case.reporter_type, case.state), (user.id, role, "report"))
            self.assertEqual(case.create_uid.id, user.id)
            self.assertTrue(self.env["isms.audit.log"].sudo().search_count([
                ("model", "=", "isms.incident"), ("res_id", "=", case.id), ("action", "=", "create"),
                ("user_id", "=", user.id),
            ]))
            self.assertFalse(user.has_group("university_isms.group_isms_reporter"))
            with self.assertRaises(AccessError):
                case.with_user(user).read(["name"])

    def test_unrelated_user_denied_and_csrf_required(self):
        self.authenticate(self.other.login, self.other.login)
        self.assertEqual(self.url_open("/my/campus/incidents").status_code, 404)
        self.authenticate(self.student.login, self.student.login)
        response = self.url_open("/my/campus/incidents", data={
            "name": "Should not create report", "category": "phishing", "description": "Without CSRF token",
        })
        self.assertEqual(response.status_code, 400)
