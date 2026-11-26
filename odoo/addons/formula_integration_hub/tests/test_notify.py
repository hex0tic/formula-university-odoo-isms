from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import IntegrationCase

TPL_GRADE = 'formula_integration_hub.mail_tpl_grade_decided'
TPL_INCIDENT = 'formula_integration_hub.mail_tpl_incident_assigned'


@tagged('formula_integration_hub')
class TestNotify(IntegrationCase):

    def _change(self):
        return self.env(user=self.lecturer)['campus.grade.change'].create({
            'enrollment_id': self.enrollment.id,
            'proposed_score': 75,
            'reason': 'Нотолгооны дагуу дүнг залруулах хүсэлт.',
        })

    def _mail_count(self, record):
        return self.env['mail.mail'].sudo().search_count([('model', '=', record._name), ('res_id', '=', record.id)])

    def test_default_preferences_queue_email_and_inbox(self):
        change = self._change()
        logs = self.env['formula.notification.log'].notify(self.lecturer, 'academic', TPL_GRADE, change)
        email = logs.filtered(lambda row: row.channel == 'email')
        inbox = logs.filtered(lambda row: row.channel == 'inbox')
        self.assertEqual(email.state, 'queued')
        self.assertEqual(email.mail_id.state, 'outgoing')  # SMTP-д илгээгдээгүй, mail queue-д байна
        self.assertIn(change.name, email.mail_id.subject)
        self.assertEqual(inbox.state, 'queued')
        self.assertTrue(self.env['mail.notification'].sudo().search_count([
            ('mail_message_id', '=', inbox.message_id.id),
            ('notification_type', '=', 'inbox'),
            ('res_partner_id', '=', self.lecturer.partner_id.id)]))

    def test_opt_out_of_academic_email_is_respected(self):
        self.env['formula.notification.preference'].create({
            'user_id': self.lecturer.id, 'category': 'academic', 'email': False, 'inbox': True})
        change = self._change()
        before = self._mail_count(change)
        logs = self.env['formula.notification.log'].notify(self.lecturer, 'academic', TPL_GRADE, change)
        self.assertEqual(logs.filtered(lambda row: row.channel == 'email').state, 'skipped_pref')
        self.assertEqual(self._mail_count(change), before)
        self.assertEqual(logs.filtered(lambda row: row.channel == 'inbox').state, 'queued')

    def test_security_alerts_cannot_be_opted_out(self):
        with self.assertRaises(ValidationError):
            self.env['formula.notification.preference'].create({
                'user_id': self.analyst.id, 'category': 'security', 'email': False, 'inbox': True})
        with self.assertRaises(ValidationError):
            self.env['formula.notification.preference'].create({
                'user_id': self.analyst.id, 'category': 'security', 'email': True, 'inbox': False})
        email_on, inbox_on = self.env['formula.notification.preference'].channels_for(self.analyst, 'security')
        self.assertTrue(email_on and inbox_on)

    def test_incident_assignment_is_security_and_always_queued(self):
        incident = self.env['isms.incident'].create({'name': 'Test incident assignment', 'category': 'phishing'})
        incident.write({'assignee_id': self.analyst.id})
        logs = self.env['formula.notification.log'].sudo().search([
            ('res_model', '=', 'isms.incident'), ('res_id', '=', incident.id),
            ('user_id', '=', self.analyst.id), ('channel', '=', 'email')])
        self.assertEqual(logs.mapped('category'), ['security'])
        self.assertEqual(logs.state, 'queued')

    def test_grade_decision_notifies_requester(self):
        change = self._change()
        self.env(user=self.lecturer)['campus.grade.change'].browse(change.id).action_submit()
        self.env(user=self.registrar)['campus.grade.change'].browse(change.id).action_approve()
        logs = self.env['formula.notification.log'].sudo().search([
            ('template_ref', '=', TPL_GRADE), ('res_id', '=', change.id)])
        self.assertTrue(logs)
        self.assertEqual(set(logs.mapped('user_id').ids), {self.lecturer.id})
        self.assertEqual(logs.filtered(lambda row: row.channel == 'email').state, 'queued')
