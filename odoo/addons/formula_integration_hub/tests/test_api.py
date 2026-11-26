from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from ..models.api_service import ApiAuthError, RateLimited, take_token
from .common import IntegrationCase


@tagged('formula_integration_hub')
class TestApi(IntegrationCase):

    def test_api_disabled_without_enabled_endpoint(self):
        self.assertFalse(self.env['formula.integration.api'].api_endpoint())
        self._endpoint('api', enabled=False, auth_method='none', secret_key='')
        self.assertFalse(self.env['formula.integration.api'].api_endpoint())
        self.assertTrue(self._endpoint('api', enabled=True, auth_method='none', secret_key=''))

    def test_bearer_api_key_authenticates_owner(self):
        key = self.env(user=self.analyst)['res.users.apikeys']._generate(
            'rpc', 'unit-test-key', fields.Datetime.now() + timedelta(days=1))
        uid, key_id = self.env['formula.integration.api'].authenticate('Bearer ' + key)
        self.assertEqual(uid, self.analyst.id)
        self.assertEqual(len(key_id), 24)
        self.assertNotIn(key, key_id)
        with self.assertRaises(ApiAuthError):
            self.env['formula.integration.api'].authenticate('Bearer not-a-valid-key-value')
        with self.assertRaises(ApiAuthError):
            self.env['formula.integration.api'].authenticate('Basic abc')
        with self.assertRaises(ApiAuthError):
            self.env['formula.integration.api'].authenticate('')

    def test_token_bucket_limits_per_key(self):
        key = 'unit-bucket-a'
        self.assertTrue(take_token(key, 2, 60, now=0.0)[0])
        self.assertTrue(take_token(key, 2, 60, now=0.0)[0])
        allowed, retry_after = take_token(key, 2, 60, now=0.0)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)
        self.assertTrue(take_token(key, 2, 60, now=61.0)[0])  # 60/мин: 1 токен секунд тутамд сэргэнэ
        self.assertTrue(take_token('unit-bucket-b', 2, 60, now=0.0)[0])  # өөр key бие даасан

    def test_service_raises_rate_limited_when_bucket_empty(self):
        self.env['ir.config_parameter'].sudo().set_param('formula_integration_hub.api_rate_capacity', '1')
        service = self.env['formula.integration.api']
        service.check_rate_limit('unit-service-key-1')
        with self.assertRaises(RateLimited):
            service.check_rate_limit('unit-service-key-1')

    def test_results_respect_key_owner_permissions(self):
        plain_api = self.env(user=self.plain)['formula.integration.api']
        with self.assertRaises(AccessError):
            plain_api.incidents_summary()
        with self.assertRaises(AccessError):
            plain_api.offerings()

    def test_analyst_summary_counts_visible_incidents(self):
        self.env['isms.incident'].create({'name': 'Summary incident', 'category': 'other'})
        summary = self.env(user=self.analyst)['formula.integration.api'].incidents_summary()
        self.assertGreaterEqual(summary['total'], 1)
        self.assertEqual(set(summary['by_state']), {'incident', 'report', 'investigate', 'resolve', 'close'})
        self.assertEqual(set(summary['by_severity']), {'low', 'medium', 'high', 'critical'})

    def test_offerings_exclude_staff_contact_fields(self):
        rows = self.env(user=self.registrar)['formula.integration.api'].offerings(limit='bad')
        self.assertTrue(rows)
        self.assertEqual(set(rows[0]), {'id', 'code', 'name', 'semester', 'state'})
