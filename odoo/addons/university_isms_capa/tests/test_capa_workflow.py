from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install', 'university_isms_capa')
class TestCapaWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analyst = new_test_user(cls.env, 't_capa_analyst', groups='university_isms.group_isms_analyst')
        cls.analyst2 = new_test_user(cls.env, 't_capa_analyst2', groups='university_isms.group_isms_analyst')
        cls.auditor = new_test_user(cls.env, 't_capa_auditor', groups='university_isms.group_isms_auditor')
        cls.dual = new_test_user(cls.env, 't_capa_dual',
                                 groups='university_isms.group_isms_analyst,university_isms.group_isms_auditor')
        cls.ciso = new_test_user(cls.env, 't_capa_ciso', groups='university_isms.group_isms_manager')
        cls.reporter = new_test_user(cls.env, 't_capa_reporter', groups='university_isms.group_isms_reporter')
        cls.risk = cls.env['isms.risk'].sudo().create({'name': 'Тест эрсдэл', 'owner_id': cls.analyst.id})
        cls.today = fields.Date.context_today(cls.env['isms.capa'])

    def _finding(self, severity='medium', risk=False):
        vals = {'name': 'Тест олдвор', 'severity': severity}
        if risk:
            vals['risk_id'] = self.risk.id
        return self.env['isms.finding'].with_user(self.analyst).create(vals)

    def _capa(self, finding, owner, **extra):
        vals = {'name': 'Засвар', 'finding_id': finding.id, 'owner_id': owner.id,
                'root_cause': 'Тохиргооны алдаа', 'corrective_action': 'Тохиргоог засах',
                'deadline': self.today + timedelta(days=7)}
        vals.update(extra)
        return self.env['isms.capa'].with_user(self.analyst).create(vals)

    def test_happy_path_capa_to_closed(self):
        finding = self._finding(severity='high', risk=True)
        capa = self._capa(finding, self.analyst2)
        self.assertEqual(capa.state, 'draft')
        self.assertTrue(capa.code.startswith('CAPA-'))
        capa.with_user(self.analyst).action_start()
        self.assertEqual(capa.state, 'in_progress')
        self.assertEqual(finding.state, 'capa')
        capa.with_user(self.analyst2).write({'implementation_notes': 'Тохиргоо шинэчлэв'})
        capa.with_user(self.analyst2).action_mark_implemented()
        self.assertEqual(capa.state, 'implemented')
        self.assertEqual(capa.implemented_by_id, self.analyst2)
        capa.with_user(self.auditor).write({'verification_notes': 'Нотолгоог шалгасан'})
        capa.with_user(self.auditor).action_verify()
        self.assertEqual(capa.state, 'verified')
        self.assertEqual(capa.verifier_id, self.auditor)
        self.assertEqual(finding.state, 'verified')
        capa.with_user(self.ciso).action_close()
        self.assertEqual(capa.state, 'closed')
        finding.with_user(self.ciso).action_close()
        self.assertEqual(finding.state, 'closed')
        self.assertTrue(finding.closed_at)

    def test_self_verification_rejected(self):
        finding = self._finding()
        capa = self._capa(finding, self.dual)
        capa.with_user(self.dual).action_start()
        capa.with_user(self.dual).write({'evidence_ref': 'EV-004'})
        capa.with_user(self.dual).action_mark_implemented()
        capa.with_user(self.dual).write({'verification_notes': 'Өөрөө шалгав'})
        with self.assertRaises(AccessError):
            capa.with_user(self.dual).action_verify()
        self.assertEqual(capa.state, 'implemented')

    def test_implementer_cannot_verify_others_work(self):
        finding = self._finding()
        capa = self._capa(finding, self.analyst2)
        capa.with_user(self.analyst2).action_start()
        capa.with_user(self.analyst2).write({'evidence_ref': 'EV-001'})
        capa.with_user(self.ciso).action_mark_implemented()
        self.assertEqual(capa.implemented_by_id, self.ciso)
        capa.with_user(self.ciso).write({'verification_notes': 'Шалгав'})
        with self.assertRaises(AccessError):
            capa.with_user(self.ciso).action_verify()

    def test_only_auditor_or_ciso_verifies(self):
        finding = self._finding()
        capa = self._capa(finding, self.analyst2)
        capa.with_user(self.analyst2).action_start()
        capa.with_user(self.analyst2).write({'evidence_ref': 'EV-002'})
        capa.with_user(self.analyst2).action_mark_implemented()
        with self.assertRaises(AccessError):
            capa.with_user(self.analyst).action_verify()
        self.assertEqual(capa.state, 'implemented')

    def test_analyst_cannot_close_and_cannot_set_state(self):
        finding = self._finding()
        capa = self._capa(finding, self.analyst2)
        capa.with_user(self.analyst2).action_start()
        capa.with_user(self.analyst2).write({'evidence_ref': 'EV-003'})
        capa.with_user(self.analyst2).action_mark_implemented()
        capa.with_user(self.auditor).write({'verification_notes': 'OK'})
        capa.with_user(self.auditor).action_verify()
        with self.assertRaises(AccessError):
            capa.with_user(self.analyst).action_close()
        with self.assertRaises(AccessError):
            capa.with_user(self.analyst).write({'state': 'closed'})
        with self.assertRaises(AccessError):
            finding.with_user(self.analyst).action_close()
        with self.assertRaises(AccessError):
            finding.with_user(self.analyst).write({'state': 'closed'})

    def test_finding_cannot_close_before_verification(self):
        finding = self._finding()
        with self.assertRaises(UserError):
            finding.with_user(self.ciso).action_close()
        with self.assertRaises(UserError):
            finding.with_user(self.ciso).action_accept_risk()
        capa = self._capa(finding, self.analyst2)
        capa.with_user(self.analyst2).action_start()
        finding.with_user(self.ciso).write({'acceptance_reason': 'Шалтгаан'})
        with self.assertRaises(UserError):
            finding.with_user(self.ciso).action_accept_risk()
        self.assertEqual(finding.state, 'capa')

    def test_accept_without_action_requires_ciso_and_reason(self):
        finding = self._finding(severity='low')
        with self.assertRaises(AccessError):
            finding.with_user(self.analyst).action_accept_risk()
        with self.assertRaises(UserError):
            finding.with_user(self.ciso).action_accept_risk()
        finding.with_user(self.ciso).write({'acceptance_reason': 'Эрсдэл бага, хүлээн зөвшөөрнө'})
        finding.with_user(self.ciso).action_accept_risk()
        self.assertEqual(finding.state, 'closed')
        self.assertEqual(finding.accepted_by_id, self.ciso)

    def test_capa_close_requires_verified_state(self):
        finding = self._finding()
        capa = self._capa(finding, self.analyst2)
        with self.assertRaises(UserError):
            capa.with_user(self.ciso).action_close()

    def test_overdue_flag(self):
        finding = self._finding()
        capa = self._capa(finding, self.analyst2, deadline=self.today - timedelta(days=1))
        self.assertTrue(capa.is_overdue)
        found = self.env['isms.capa'].sudo().search([('is_overdue', '=', True), ('id', '=', capa.id)])
        self.assertEqual(found, capa)

    def test_reporter_and_owner_access(self):
        finding = self._finding()
        capa = self._capa(finding, self.analyst2)
        with self.assertRaises(AccessError):
            self.env['isms.capa'].with_user(self.reporter).search([])
        owner_user = new_test_user(self.env, 't_capa_owner', groups='university_isms.group_isms_asset_owner')
        self.assertFalse(self.env['isms.capa'].with_user(owner_user).search([('id', '=', capa.id)]))
