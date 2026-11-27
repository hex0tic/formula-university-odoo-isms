from lxml.html import fromstring

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user

from ..models.admission import token_digest


@tagged("post_install", "-at_install")
class TestAdmissions(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrar = new_test_user(cls.env, login="admissions_registrar",
                                      groups="campus_university.group_campus_registrar")
        cls.teacher = new_test_user(cls.env, login="admissions_teacher",
                                    groups="campus_university.group_campus_lecturer")
        academic = cls.env["campus.program"].create({
            "code": "TEST-ADM", "name": "Admissions Academic", "department": "Testing",
        })
        cls.program = cls.env.ref("formula_campus_web.program_cybersecurity")
        cls.program.write({"academic_program_id": academic.id})
        cls.Model = cls.env["formula.campus.admission"]

    def _csrf(self, url):
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        return fromstring(response.text).xpath("//form/input[@name='csrf_token']/@value")[0]

    def _submit(self):
        url = "/university/admissions/apply"
        response = self.url_open(url, data={
            "csrf_token": self._csrf(url),
            "name": "Applicant Student",
            "email": "applicant@example.invalid",
            "program": self.program.slug,
            "motivation": "I would like to study information systems and their protection.",
        })
        self.assertEqual(response.status_code, 200)
        page = fromstring(response.text)
        return page.get_element_by_id("admission-reference").text_content(), page.get_element_by_id("admission-token").text_content()

    def _status(self, reference, code):
        url = "/university/admissions/status"
        return self.url_open(url, data={"csrf_token": self._csrf(url), "reference": reference, "code": code})

    def test_catalogue_and_application_agree_on_closed_programme(self):
        closed = self.env["formula.public.program"].search([("slug", "=", "business-analytics")])
        self.assertTrue(closed.published)
        closed.academic_program_id = False
        detail = self.url_open("/university/programs/" + closed.slug)
        self.assertEqual(detail.status_code, 200)
        self.assertIn("Элсэлт нээгдээгүй", detail.text)
        self.assertNotIn("admissions/apply?program=" + closed.slug, detail.text)
        response = self.url_open("/university/admissions/apply?program=" + closed.slug)
        self.assertIn("Сонгосон хөтөлбөрийн элсэлт нээгдээгүй", response.text)
        options = fromstring(response.text).xpath("//select[@name='program']/option/@value")
        self.assertNotIn(closed.slug, options)
        self.assertIn(self.program.slug, options)
        detail = self.url_open("/university/programs/" + self.program.slug)
        self.assertIn("admissions/apply?program=" + self.program.slug, detail.text)

    def test_public_application_and_registrar_admission(self):
        reference, code = self._submit()
        record = self.Model.search([("reference", "=", reference)])
        self.assertEqual(record.token_digest, token_digest(code))
        self.assertNotIn("Applicant Student", self._status(reference, "A" * 32).text)
        self.assertIn("Хүлээн авсан", self._status(reference, code).text)
        with self.assertRaises(AccessError):
            record.with_user(self.teacher).action_start_review()
        reviewed = record.with_user(self.registrar)
        with self.assertRaises(AccessError):
            reviewed.write({"state": "accepted"})
        reviewed.action_start_review()
        reviewed.write({"review_note": "Internal-only note", "decision_message": "Accepted for the next term"})
        reviewed.action_decide_accept()
        with self.assertRaises(UserError):
            reviewed.action_decide_accept()
        user = record.student_id.user_id
        self.assertEqual(record.student_id.program_id, self.program.academic_program_id)
        self.assertEqual(record.checked_by_id, self.registrar)
        self.assertTrue(user.has_group("base.group_portal"))
        self.assertFalse(user.has_group("base.group_user"))
        page = self._status(reference, code).text
        self.assertIn("Элсэх эрх олгосон", page)
        self.assertIn("Accepted for the next term", page)
        self.assertNotIn("Internal-only note", page)
        self.assertNotIn(record.email, page)

    def test_decline_does_not_provision_student(self):
        ref, code = self._submit()
        record = self.Model.search([("reference", "=", ref)]).with_user(self.registrar)
        record.action_start_review()
        with self.assertRaises(UserError):
            record.action_decide_decline()
        record.decision_message = "Try again next term"
        record.action_decide_decline()
        self.assertFalse(record.student_id)
        self.assertIn("Try again next term", self._status(ref, code).text)
