from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install', 'university_isms_capa')
class TestWaiverRisk(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analyst = new_test_user(cls.env, 't_wvr_analyst', groups='university_isms.group_isms_analyst')
        cls.auditor = new_test_user(cls.env, 't_wvr_auditor', groups='university_isms.group_isms_auditor')
        cls.ciso = new_test_user(cls.env, 't_wvr_ciso', groups='university_isms.group_isms_manager')
        cls.reporter = new_test_user(cls.env, 't_wvr_reporter', groups='university_isms.group_isms_reporter')
        cls.owner = new_test_user(cls.env, 't_wvr_owner', groups='university_isms.group_isms_asset_owner')
        cls.risk = cls.env['isms.risk'].sudo().create({'name': 'Эрсдэл A', 'owner_id': cls.owner.id})
        cls.risk_other = cls.env['isms.risk'].sudo().create({'name': 'Эрсдэл B', 'owner_id': cls.ciso.id})
        cls.today = fields.Date.context_today(cls.env['isms.risk.waiver'])

    def _waiver(self, user=None, **extra):
        vals = {'name': 'Зөвшөөрөл', 'risk_id': self.risk.id, 'justification': 'Засвар хүлээгдэж буй',
                'compensating_controls': 'Нэмэлт хяналт', 'owner_id': self.owner.id,
                'expiry_date': self.today + timedelta(days=90)}
        vals.update(extra)
        return self.env['isms.risk.waiver'].with_user(user or self.analyst).create(vals)

    def test_approval_only_by_ciso_and_not_requester(self):
        waiver = self._waiver()
        self.assertEqual(waiver.requested_by_id, self.analyst)
        self.assertEqual(waiver.state, 'draft')
        with self.assertRaises(AccessError):
            waiver.with_user(self.analyst).action_approve()
        with self.assertRaises(AccessError):
            waiver.with_user(self.auditor).action_approve()
        with self.assertRaises(AccessError):
            waiver.with_user(self.analyst).write({'state': 'approved'})
        own = self._waiver(user=self.ciso)
        with self.assertRaises(AccessError):
            own.with_user(self.ciso).action_approve()
        waiver.with_user(self.ciso).action_approve()
        self.assertEqual(waiver.state, 'approved')
        self.assertEqual(waiver.approved_by_id, self.ciso)
        with self.assertRaises(UserError):
            waiver.with_user(self.ciso).write({'justification': 'Өөрчлөлт'})

    def test_expiry_cron_creates_exactly_one_finding_even_if_run_twice(self):
        waiver = self._waiver()
        waiver.with_user(self.ciso).action_approve()
        waiver.sudo().expiry_date = self.today - timedelta(days=1)
        Waiver = self.env['isms.risk.waiver']
        first = Waiver._cron_expire_waivers()
        second = Waiver._cron_expire_waivers()
        self.assertEqual(first['expired'], 1)
        self.assertEqual(second['expired'], 0)
        self.assertEqual(waiver.sudo().state, 'expired')
        findings = self.env['isms.finding'].sudo().search([('source_key', '=', 'waiver-expired:%s' % waiver.id)])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings.source, 'monitoring')
        self.assertEqual(findings.risk_id, self.risk)
        self.assertTrue(self.risk.sudo().reeval_required)

    def test_risk_flagged_for_reevaluation_by_high_finding_only(self):
        self.assertFalse(self.risk_other.sudo().reeval_required)
        self.env['isms.finding'].sudo().create({'name': 'Бага', 'severity': 'low', 'risk_id': self.risk_other.id})
        self.assertFalse(self.risk_other.sudo().reeval_required)
        self.env['isms.finding'].sudo().create({'name': 'Өндөр', 'severity': 'high', 'risk_id': self.risk_other.id})
        self.assertTrue(self.risk_other.sudo().reeval_required)
        self.assertTrue(self.risk_other.sudo().reeval_reason)
        with self.assertRaises(AccessError):
            self.risk_other.with_user(self.ciso).write({'reeval_required': False})
        self.risk_other.with_user(self.analyst).action_complete_reeval()
        self.assertFalse(self.risk_other.sudo().reeval_required)

    def test_reporter_has_no_access(self):
        waiver = self._waiver()
        with self.assertRaises(AccessError):
            self.env['isms.risk.waiver'].with_user(self.reporter).search([])
        with self.assertRaises(AccessError):
            self.env['isms.capa'].with_user(self.reporter).search([])
        with self.assertRaises(AccessError):
            self.env['isms.finding'].with_user(self.reporter).search([])
        self.assertTrue(waiver)

    def test_asset_owner_sees_only_own_risk_findings(self):
        own = self.env['isms.finding'].sudo().create({'name': 'Өөрийн', 'severity': 'low', 'risk_id': self.risk.id})
        other = self.env['isms.finding'].sudo().create({'name': 'Бусдын', 'severity': 'low',
                                                        'risk_id': self.risk_other.id})
        visible = self.env['isms.finding'].with_user(self.owner).search([('id', 'in', [own.id, other.id])])
        self.assertEqual(visible, own)
        with self.assertRaises(AccessError):
            self.env['isms.finding'].with_user(self.owner).create({'name': 'Хориотой'})
