from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

TOTP_SECRET = 'JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'  # test-only fixture, not a real account secret


@tagged('post_install', '-at_install', 'university_mfa_policy')
class TestMfaPolicy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.ciso = new_test_user(env, 't_mfa_ciso', groups='university_isms.group_isms_manager')
        cls.admin2 = new_test_user(env, 't_mfa_admin', groups='base.group_user,base.group_system')
        cls.analyst = new_test_user(env, 't_mfa_analyst', groups='university_isms.group_isms_analyst')
        cls.target = new_test_user(env, 't_mfa_target', groups='university_isms.group_isms_reporter')
        cls.policy = env['isms.policy'].create({'name': 'MFA тест бодлого', 'code': 'POL-T-MFA'}) \
            if 'code' in env['isms.policy']._fields else env['isms.policy'].create({'name': 'MFA тест бодлого'})

    def _enforce(self, days=0):
        date = fields.Date.today() + timedelta(days=days)
        self.env['ir.config_parameter'].sudo().set_param('university_mfa_policy.enforce_date', fields.Date.to_string(date))

    def _enable_totp(self, user):
        user.sudo().totp_secret = TOTP_SECRET
        user.invalidate_recordset(['totp_enabled'])

    def test_not_enforced_without_date(self):
        self.env['ir.config_parameter'].sudo().set_param('university_mfa_policy.enforce_date', '')
        self.env['res.users'].with_user(self.ciso)._mfa_step_up_check('x')  # no raise
        self.assertFalse(self.env['res.users'].with_user(self.ciso).get_mfa_status()['enforced'])

    def test_future_date_only_warns(self):
        self._enforce(days=7)
        status = self.env['res.users'].with_user(self.ciso).get_mfa_status()
        self.assertTrue(status['privileged'])
        self.assertFalse(status['enforced'])
        self.env['res.users'].with_user(self.ciso)._mfa_step_up_check('x')

    def test_enforced_blocks_privileged_without_totp(self):
        self._enforce()
        with self.assertRaises(AccessError):
            self.env['res.users'].with_user(self.ciso)._mfa_step_up_check('x')
        with self.assertRaises(AccessError):
            self.policy.with_user(self.ciso).action_approve()

    def test_enforced_blocks_group_change_by_admin_without_totp(self):
        self._enforce()
        group = self.env.ref('university_isms.group_isms_asset_owner')
        with self.assertRaises(AccessError):
            self.target.with_user(self.admin2).write({'groups_id': [(4, group.id)]})
        self.assertFalse(self.target.has_group('university_isms.group_isms_asset_owner'))

    def test_totp_enabled_user_passes(self):
        self._enforce()
        self._enable_totp(self.admin2)
        group = self.env.ref('university_isms.group_isms_asset_owner')
        self.target.with_user(self.admin2).write({'groups_id': [(4, group.id)]})
        self.assertTrue(self.target.has_group('university_isms.group_isms_asset_owner'))

    def test_non_privileged_user_not_affected(self):
        self._enforce()
        self.env['res.users'].with_user(self.analyst)._mfa_step_up_check('x')
        self.assertFalse(self.env['res.users'].with_user(self.analyst).get_mfa_status()['privileged'])

    def test_system_calls_bypass(self):
        self._enforce()
        self.env['res.users']._mfa_step_up_check('cron')  # superuser env

    def test_status_has_no_secret(self):
        self._enable_totp(self.ciso)
        status = self.env['res.users'].with_user(self.ciso).get_mfa_status()
        self.assertTrue(status['totp_enabled'])
        self.assertNotIn(TOTP_SECRET, str(status))
