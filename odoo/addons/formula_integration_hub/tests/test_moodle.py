import json

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from ..models.transport import HttpTransport
from .common import IntegrationCase, TEST_SECRET_VALUE


@tagged('formula_integration_hub')
class TestMoodle(IntegrationCase):

    def _lms(self):
        return self._endpoint('lms', max_attempts=2)

    def test_moodle_requests_use_ws_function_names_and_form_token(self):
        endpoint = self._lms()
        event = self.env['formula.moodle.adapter'].enqueue_offering_sync(endpoint, self.offering)
        self.assertEqual(event.event_type, 'lms.course.create')
        self.assertIn('core_course_create_courses', event.payload_json)
        self.assertNotIn(TEST_SECRET_VALUE, event.payload_json)
        self.assertNotIn('erp_refs', HttpTransport.prepare(endpoint, event)['form'])
        form = HttpTransport.prepare(endpoint, event)['form']
        self.assertEqual(form['wsfunction'], 'core_course_create_courses')
        self.assertEqual(form['wstoken'], TEST_SECRET_VALUE)
        self.assertIn('courses[0][idnumber]', form)
        self.assertIsNone(HttpTransport.prepare(endpoint, event)['data'])

    def test_offering_sync_is_idempotent_and_maps_remote_id(self):
        endpoint = self._lms()
        Moodle = self.env['formula.moodle.adapter']
        event = Moodle.enqueue_offering_sync(endpoint, self.offering)
        with self._post_patch(return_value=(200, json.dumps([{'id': 77, 'shortname': 'CS101-2026-A'}]))):
            self.assertTrue(event._dispatch_one())
        self.assertEqual(self.env['formula.integration.mapping'].remote_for(
            endpoint, 'campus.offering', self.offering.id), '77')
        again = Moodle.enqueue_offering_sync(endpoint, self.offering)
        self.assertFalse(again)

    def test_moodle_exception_body_is_failure_not_success(self):
        endpoint = self._lms()
        event = self.env['formula.moodle.adapter'].enqueue_offering_sync(endpoint, self.offering)
        body = json.dumps({'exception': 'moodle_exception', 'errorcode': 'invalidtoken'})
        with self._post_patch(return_value=(200, body)):
            self.assertFalse(event._dispatch_one())
        self.assertEqual(event.state, 'failed')
        self.assertIn('invalidtoken', event.last_error)

    def test_enrolment_needs_mapped_user_and_course(self):
        endpoint = self._lms()
        Moodle = self.env['formula.moodle.adapter']
        self.assertFalse(Moodle.enqueue_enrolment_sync(endpoint, self.enrollment))
        self.env['formula.integration.mapping'].link(endpoint, 'campus.student', self.student.id, 501)
        self.env['formula.integration.mapping'].link(endpoint, 'campus.offering', self.offering.id, 77)
        event = Moodle.enqueue_enrolment_sync(endpoint, self.enrollment)
        self.assertEqual(event.event_type, 'lms.enrol.create')
        self.assertIn('enrol_manual_enrol_users', event.payload_json)
        self.assertEqual(self.enrollment.score, 0)

    def test_grade_import_creates_drafts_only_and_never_writes_score(self):
        endpoint = self._lms()
        mapping = self.env['formula.integration.mapping']
        mapping.link(endpoint, 'campus.student', self.student.id, '501')
        mapping.link(endpoint, 'campus.offering', self.offering.id, '77')
        before = (self.enrollment.score, self.enrollment.grade_revision)
        items = [
            {'remote_user_id': '501', 'remote_course_id': '77', 'remote_item_id': '9001', 'grade': 85},
            {'remote_user_id': '501', 'remote_course_id': '77', 'remote_item_id': '9001', 'grade': 85},
            {'remote_user_id': '501', 'remote_course_id': '77', 'remote_item_id': '9002', 'grade': 150},
            {'remote_user_id': '999', 'remote_course_id': '77', 'remote_item_id': '9003', 'grade': 70},
            {'remote_user_id': 'x'},
        ]
        Moodle = self.env(user=self.registrar)['formula.moodle.adapter']
        summary = Moodle.import_grade_suggestions(endpoint, items)
        self.assertEqual(len(summary['created']), 1)
        reasons = [row['reason'] for row in summary['skipped']]
        self.assertIn('duplicate', reasons)
        self.assertIn('invalid', reasons)
        self.assertIn('out_of_range', reasons)
        self.assertIn('unmapped', reasons)
        change = self.env['campus.grade.change'].browse(summary['created'])
        self.assertEqual(change.state, 'draft')
        self.assertEqual(change.proposed_score, 85)
        self.assertEqual((self.enrollment.score, self.enrollment.grade_revision), before)

    def test_grade_import_requires_registrar_or_lecturer(self):
        endpoint = self._lms()
        with self.assertRaises(AccessError):
            self.env(user=self.plain)['formula.moodle.adapter'].import_grade_suggestions(endpoint, [])

    def test_mapping_is_idempotent_and_never_overwrites(self):
        endpoint = self._lms()
        Mapping = self.env['formula.integration.mapping']
        first = Mapping.link(endpoint, 'campus.student', self.student.id, 'R-1')
        self.assertEqual(first, Mapping.link(endpoint, 'campus.student', self.student.id, 'R-1'))
        with self.assertRaises(ValidationError):
            Mapping.link(endpoint, 'campus.student', self.student.id, 'R-2')
        with self.assertRaises(ValidationError):
            Mapping.link(endpoint, 'campus.student', self.plain.id, 'R-1')
