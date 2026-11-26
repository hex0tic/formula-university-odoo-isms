import uuid
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase

from ..models.transport import HttpTransport

TEST_SECRET_KEY = 'formula_integration_hub.test_secret'
TEST_SECRET_VALUE = 'unit-test-only-not-a-credential'  # тестийн дотоод утга; live credential биш
TEST_BASE_URL = 'https://lms.unit-test.invalid/webservice/rest/server.php'  # .invalid: сүлжээнд хүрэхгүй


class IntegrationCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param(TEST_SECRET_KEY, TEST_SECRET_VALUE)
        cls.group_user = env.ref('base.group_user')
        cls.registrar = cls._make_user(env, 'int_registrar', [
            env.ref('campus_university.group_campus_registrar')])
        cls.lecturer = cls._make_user(env, 'int_lecturer', [
            env.ref('campus_university.group_campus_lecturer')])
        cls.plain = cls._make_user(env, 'int_plain', [])
        cls.analyst = cls._make_user(env, 'int_analyst', [env.ref('university_isms.group_isms_analyst')])
        program = env['campus.program'].create({
            'code': 'CS', 'name': 'Computer Science', 'department': 'IT', 'owner_id': cls.registrar.id})
        cls.course = env['campus.course'].create({'code': 'CS101', 'name': 'Intro', 'credits': 3,
                                                  'program_id': program.id})
        cls.offering = env['campus.offering'].create({
            'name': 'CS101 2026-A', 'course_id': cls.course.id, 'semester': '2026-A',
            'lecturer_id': cls.lecturer.id})
        cls.offering.state = 'open'
        cls.student = env['campus.student'].create({
            'student_code': 'STU001', 'name': 'Test Student', 'program_id': program.id,
            'institutional_email': 'stu001@unit-test.invalid'})
        cls.enrollment = env['campus.enrollment'].create({
            'student_id': cls.student.id, 'offering_id': cls.offering.id})

    @classmethod
    def _make_user(cls, env, login, groups):
        return env['res.users'].create({
            'name': login, 'login': login, 'email': '%s@unit-test.invalid' % login,
            'groups_id': [(6, 0, [env.ref('base.group_user').id] + [g.id for g in groups])],
        })

    def _endpoint(self, kind, enabled=True, **vals):
        data = {'name': '%s-%s' % (kind, uuid.uuid4().hex[:8]), 'kind': kind,
                'base_url': TEST_BASE_URL, 'auth_method': 'bearer', 'secret_source': 'param',
                'secret_key': TEST_SECRET_KEY, 'max_attempts': 3}
        data.update(vals)
        endpoint = self.env['formula.integration.endpoint'].create(data)
        if enabled:
            endpoint.enabled = True
        return endpoint

    def _post_patch(self, side_effect=None, return_value=None):
        """HttpTransport.post-ыг mock хийнэ. Сүлжээний дуудлага ХИЙГДЭХГҮЙ."""
        kwargs = {}
        if side_effect is not None:
            kwargs['side_effect'] = side_effect
        else:
            kwargs['return_value'] = return_value or (200, '{"ok": true}')
        return patch.object(HttpTransport, 'post', **kwargs)

    @staticmethod
    def past(event):
        event.next_attempt_at = fields.Datetime.now() - timedelta(seconds=1)
