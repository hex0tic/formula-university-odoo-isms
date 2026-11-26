"""university_isms_monitoring_plus: хяналтын тест, автомат шалгалт, cron, эрхийн шалгалт."""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from ..models import check_registry as reg

PASSWORD = 'Isms-Test-Pass-2026'


@tagged('post_install', '-at_install', 'university_isms_monitoring_plus')
class TestControlTests(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.reporter = new_test_user(env, 'mp_reporter', password=PASSWORD,
                                     groups='university_isms.group_isms_reporter')
        cls.analyst = new_test_user(env, 'mp_analyst', password=PASSWORD,
                                    groups='university_isms.group_isms_analyst')
        cls.auditor = new_test_user(env, 'mp_auditor', password=PASSWORD,
                                    groups='university_isms.group_isms_auditor')
        cls.manager = new_test_user(env, 'mp_manager', password=PASSWORD,
                                    groups='university_isms.group_isms_manager')
        cls.sysadmin = new_test_user(env, 'mp_sysadmin', password=PASSWORD, groups='base.group_system')
        cls.control = env.ref('university_isms.control_8_5')

    # ------------------------------------------------------------ helpers
    def _plan(self, check_key=None, method='automated', **kw):
        vals = {'name': 'Тест', 'control_id': self.control.id, 'method': method,
                'check_key': check_key, 'frequency': 'monthly'}
        vals.update(kw)
        return self.env['isms.control.test.plan'].sudo().create(vals)

    def _assert_refused(self, func):
        try:
            func()
        except (AccessError, UserError):
            return
        self.fail('Операция татгалзагдах ёстой байсан')

    def _set_param(self, key, value):
        self.env['ir.config_parameter'].sudo().set_param(key, str(value))

    def _findings(self, source_key):
        return self.env['isms.finding'].sudo().search([
            ('source', '=', 'control_test'), ('source_key', '=', source_key)])

    # ------------------------------------------------------------ registry
    def test_01_registry_contract_and_no_secret_exposure(self):
        self.assertGreaterEqual(len(reg.CHECKS), 7)
        self.assertEqual(sorted(k for k, _l in reg.check_selection()), sorted(reg.CHECKS))
        for key, spec in reg.CHECKS.items():
            self.assertTrue(spec.scope, key)
            outcome = spec.func(self.env)
            self.assertEqual(len(outcome), 3, key)
            self.assertIn(outcome[0], ('pass', 'fail', 'not_applicable'), key)
            details = outcome[1] or ''
            for forbidden in ('Isms-Test-Pass', '$pbkdf2', '$2b$', 'totp_secret', 'password'):
                self.assertNotIn(forbidden, details, '%s exposes %s' % (key, forbidden))

    def test_02_totp_check_fail_pass_and_not_applicable(self):
        with patch.object(reg, '_totp_state', return_value=False):
            result, details, metrics = reg.check_privileged_no_totp(self.env)
        self.assertEqual(result, 'fail')
        self.assertIn('mp_sysadmin', details)
        self.assertGreaterEqual(metrics['without_totp'], 1)
        with patch.object(reg, '_totp_state', return_value=True):
            result, _details, metrics = reg.check_privileged_no_totp(self.env)
        self.assertEqual(result, 'pass')
        self.assertEqual(metrics['without_totp'], 0)
        with patch.object(reg, '_totp_state', return_value=None):
            result, _details, _metrics = reg.check_privileged_no_totp(self.env)
        self.assertEqual(result, 'not_applicable')

    def test_03_group_size_threshold(self):
        self._set_param(reg.PARAM_MAX_ADMINS, 1)
        result, _details, metrics = reg.check_privileged_group_size(self.env)
        self.assertEqual(result, 'fail')
        self.assertGreaterEqual(metrics['system_users'], 2)
        self._set_param(reg.PARAM_MAX_ADMINS, 50)
        result, _details, _metrics = reg.check_privileged_group_size(self.env)
        self.assertEqual(result, 'pass')

    def test_04_audit_tamper_guard_refuses_write_and_unlink(self):
        self.env['isms.audit.log'].sudo()._log('create', model='isms.test.probe', res_name='probe')
        result, details, metrics = reg.check_audit_log_tamper_guard(self.env)
        self.assertEqual(result, 'pass', details)
        self.assertTrue(metrics['write_refused'])
        self.assertTrue(metrics['unlink_refused'])
        self.assertTrue(self.env['isms.audit.log'].sudo().search_count([]) >= 1)

    def test_05_incident_sla_unassigned_fail_then_pass(self):
        Incident = self.env['isms.incident'].sudo()
        inc = Incident.create({'name': 'SLA тест', 'severity': 'critical',
                               'detected_at': fields.Datetime.now() - timedelta(days=10)})
        result, details, _metrics = reg.check_incidents_past_sla_unassigned(self.env)
        self.assertEqual(result, 'fail', details)
        inc.write({'assignee_id': self.analyst.id})
        result, _details, _metrics = reg.check_incidents_past_sla_unassigned(self.env)
        self.assertEqual(result, 'pass')

    def test_06_policy_review_overdue(self):
        policy = self.env['isms.policy'].sudo().create({'name': 'Тест бодлого'})
        self.env.cr.execute(
            "UPDATE isms_policy SET state='approved', next_review_date=%s WHERE id=%s",
            (fields.Date.today() - timedelta(days=30), policy.id))
        policy.invalidate_recordset()
        result, details, _metrics = reg.check_policies_past_review(self.env)
        self.assertEqual(result, 'fail', details)

    def test_07_inactive_privileged_threshold(self):
        self._set_param(reg.PARAM_MAX_INACTIVE_DAYS, 0)
        result, _details, metrics = reg.check_inactive_privileged_users(self.env)
        self.assertEqual(result, 'fail')
        self.assertGreaterEqual(metrics['inactive_privileged'], 1)
        self._set_param(reg.PARAM_MAX_INACTIVE_DAYS, 100000)
        result, _details, _metrics = reg.check_inactive_privileged_users(self.env)
        self.assertEqual(result, 'pass')

    def test_08_evidence_check_not_applicable_without_model(self):
        if 'isms.evidence' in self.env.registry:
            self.skipTest('isms.evidence суугдсан тул энэ тест хамаарахгүй')
        result, _details, _metrics = reg.check_evidence_freshness(self.env)
        self.assertEqual(result, 'not_applicable')

    # ------------------------------------------------------------ findings and runs
    def test_09_failing_check_creates_exactly_one_finding(self):
        self._set_param(reg.PARAM_MAX_ADMINS, 1)
        plan = self._plan('privileged_group_size')
        first = plan.sudo()._execute(trigger='run_now')
        second = plan.sudo()._execute(trigger='run_now')
        self.assertEqual(first.result, 'fail')
        self.assertEqual(second.result, 'fail')
        findings = self._findings('privileged_group_size:%s' % plan.id)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings.occurrence_count, 2)
        self.assertEqual(first.finding_id, findings)
        self.assertEqual(second.finding_id, findings)
        self.assertEqual(findings.control_id, self.control)
        self.assertEqual(findings.severity, 'medium')

    def test_10_pass_run_does_not_close_finding(self):
        self._set_param(reg.PARAM_MAX_ADMINS, 1)
        plan = self._plan('privileged_group_size')
        plan.sudo()._execute(trigger='run_now')
        finding = self._findings('privileged_group_size:%s' % plan.id)
        self._set_param(reg.PARAM_MAX_ADMINS, 50)
        run = plan.sudo()._execute(trigger='run_now')
        self.assertEqual(run.result, 'pass')
        self.assertFalse(run.finding_id)
        self.assertNotEqual(finding.state, 'closed')

    def test_11_cron_stores_error_for_broken_check(self):
        plan = self._plan('privileged_no_totp')
        def boom(env):
            raise RuntimeError('boom-test')
        spec = reg.CHECKS['privileged_no_totp']
        with patch.dict(reg.CHECKS, {'privileged_no_totp': spec._replace(func=boom)}):
            summary = self.env['isms.control.test.plan']._run_due_plans()
        self.assertGreaterEqual(summary['errors'] + summary['processed'], 1)
        run = self.env['isms.control.test.run'].sudo().search([('plan_id', '=', plan.id)], limit=1)
        self.assertEqual(run.result, 'error')
        self.assertIn('boom-test', run.error_message)
        self.assertEqual(run.trigger, 'cron')

    def test_12_cron_is_idempotent_per_window(self):
        self._set_param(reg.PARAM_MAX_ADMINS, 50)
        plan = self._plan('privileged_group_size')
        Plan = self.env['isms.control.test.plan']
        Plan._run_due_plans()
        Runs = self.env['isms.control.test.run'].sudo()
        self.assertEqual(Runs.search_count([('plan_id', '=', plan.id)]), 1)
        plan.sudo().write({'next_run_at': fields.Datetime.now() - timedelta(minutes=5)})
        summary = Plan._run_due_plans()
        self.assertEqual(Runs.search_count([('plan_id', '=', plan.id)]), 1)
        self.assertGreaterEqual(summary['skipped'], 1)

    def test_13_manual_plan_records_run_and_fail_creates_finding(self):
        plan = self._plan(method='manual', check_key=False, severity='high')
        run = self.env['isms.control.test.run'].with_user(self.auditor).create({
            'plan_id': plan.id, 'result': 'fail', 'details': 'Нөөц сэргээлт амжилтгүй',
            'evidence_text': 'Тест тэмдэглэл'})
        self.assertEqual(run.trigger, 'manual')
        self.assertEqual(run.executed_by_id, self.auditor)
        self.assertTrue(run.finding_id)
        self.assertEqual(run.finding_id.severity, 'high')
        self.assertEqual(run.finding_id.source, 'control_test')

    def test_14_automated_plan_cannot_be_recorded_by_hand(self):
        plan = self._plan('privileged_group_size')
        self._assert_refused(lambda: self.env['isms.control.test.run'].with_user(self.auditor).create(
            {'plan_id': plan.id, 'result': 'pass'}))

    def test_15_runs_are_append_only(self):
        plan = self._plan(method='manual', check_key=False)
        run = self.env['isms.control.test.run'].with_user(self.auditor).create(
            {'plan_id': plan.id, 'result': 'pass'})
        for user in (self.auditor, self.manager, self.analyst):
            self._assert_refused(lambda u=user: run.with_user(u).write({'result': 'fail'}))
            self._assert_refused(lambda u=user: run.with_user(u).unlink())
        self._assert_refused(lambda: run.write({'result': 'fail'}))
        run.sudo().write({'evidence_text': 'system correction'})
        self.assertEqual(run.sudo().evidence_text, 'system correction')

    def test_16_reporter_has_no_access(self):
        plan = self._plan('privileged_group_size')
        self._assert_refused(lambda: self.env['isms.control.test.plan'].with_user(self.reporter).search([]))
        self._assert_refused(lambda: self.env['isms.control.test.run'].with_user(self.reporter).search([]))
        self._assert_refused(lambda: self.env['isms.control.test.run'].with_user(self.reporter).create(
            {'plan_id': plan.id, 'result': 'pass'}))

    def test_17_run_now_permission(self):
        self._set_param(reg.PARAM_MAX_ADMINS, 50)
        plan = self._plan('privileged_group_size')
        Runs = self.env['isms.control.test.run'].sudo()
        self._assert_refused(lambda: plan.with_user(self.auditor).action_run_now())
        self.assertEqual(Runs.search_count([('plan_id', '=', plan.id)]), 0)
        plan.with_user(self.analyst).action_run_now()
        self.assertEqual(Runs.search_count([('plan_id', '=', plan.id), ('trigger', '=', 'run_now')]), 1)
        plan.with_user(self.manager).action_run_now()
        self.assertEqual(Runs.search_count([('plan_id', '=', plan.id), ('trigger', '=', 'run_now')]), 2)

    def test_18_seed_plans_and_cron_present(self):
        plan = self.env.ref('university_isms_monitoring_plus.plan_mfa_privileged')
        self.assertEqual(plan.method, 'automated')
        self.assertEqual(plan.check_key, 'privileged_no_totp')
        self.assertEqual(plan.control_id, self.env.ref('university_isms.control_8_5'))
        self.assertTrue(self.env.ref('university_isms_monitoring_plus.plan_manual_backup_restore').method == 'manual')
        self.assertTrue(self.env.ref('university_isms_monitoring_plus.ir_cron_control_tests').active)
