import json

from odoo.tests import tagged

from ..models.siem import build_siem_payload, get_pseudonym_key, pseudonym
from .common import IntegrationCase

LOGIN = 'Alice.Student@univ.unit-test.invalid'
IP = '203.0.113.77'


@tagged('formula_integration_hub')
class TestSiem(IntegrationCase):

    def _siem(self, enabled=True):
        return self._endpoint('siem', enabled=enabled, auth_method='none', secret_key='')

    def test_payload_has_no_raw_ip_login_or_name(self):
        payload = build_siem_payload(self.env, 'login_failed', {
            'login': LOGIN, 'ip': IP, 'outcome': 'failure'})
        text = json.dumps(payload)
        for raw in (IP, 'Alice', 'alice.student', 'Student', LOGIN):
            self.assertNotIn(raw, text)
        self.assertRegex(payload['actor']['ip_hmac'], r'^[0-9a-f]{64}$')
        key = get_pseudonym_key(self.env)
        self.assertEqual(payload['actor']['login_hash'], pseudonym(key, LOGIN.lower()))
        self.assertEqual(payload['schema'], 'formula.security-event.v1')

    def test_unknown_event_type_rejected(self):
        with self.assertRaises(ValueError):
            build_siem_payload(self.env, 'grade_changed', {})

    def test_login_failure_event_written_without_raw_login(self):
        self._siem()
        self.env['res.users']._formula_siem_login_cr(self.env.cr, 'int_plain', False, None)
        event = self.env['formula.integration.event'].search([('event_type', '=', 'siem.login_failed')])
        self.assertEqual(len(event), 1)
        self.assertNotIn('int_plain', event.payload_json)

    def test_incident_events_emitted_only_when_siem_enabled(self):
        Event = self.env['formula.integration.event']
        self._siem(enabled=True)
        incident = self.env['isms.incident'].create({'name': 'Phishing Bob Secret Title', 'category': 'phishing'})
        created = Event.search([('event_type', '=', 'siem.incident_created')])
        self.assertEqual(len(created), 1)
        self.assertNotIn('Phishing Bob', created.payload_json)
        self.assertNotIn('Secret Title', created.payload_json)
        incident.write({'state': 'report'})
        self.assertEqual(Event.search_count([('event_type', '=', 'siem.incident_state_changed')]), 1)
        incident.write({'severity': 'critical'})
        self.assertEqual(Event.search_count([('event_type', '=', 'siem.incident_escalated')]), 1)

        self.env['formula.integration.endpoint'].search([('kind', '=', 'siem')]).enabled = False
        before = Event.search_count([])
        self.env['isms.incident'].create({'name': 'While disabled', 'category': 'other'})
        self.assertEqual(Event.search_count([]), before)

    def test_privileged_group_change_emits_event_without_login(self):
        self._siem()
        system_group = self.env.ref('base.group_system')
        self.plain.write({'groups_id': [(4, system_group.id)]})
        event = self.env['formula.integration.event'].search([('event_type', '=', 'siem.privileged_group_change')])
        self.assertEqual(len(event), 1)
        self.assertNotIn('int_plain', event.payload_json)
        self.assertIn('groups_added', event.payload_json)
