"""university_isms: эрсдэлийн арга зүй, RBAC, workflow, аудит логийн бодит шалгалт."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from ..models.risk import matrix_level

# decisions.md D04 / Лекц 8–9 слайд 19
EXPECTED = {
    1: ['low', 'low', 'low', 'low', 'medium'],
    2: ['low', 'low', 'medium', 'medium', 'medium'],
    3: ['low', 'medium', 'medium', 'medium', 'high'],
    4: ['low', 'medium', 'medium', 'high', 'high'],
    5: ['medium', 'medium', 'high', 'high', 'high'],
}


@tagged('post_install', '-at_install', 'university_isms')
class TestUniversityIsms(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.reporter = new_test_user(env, 't_reporter', password='Isms-Test-Pass-2026', groups='university_isms.group_isms_reporter')
        cls.owner = new_test_user(env, 't_owner', password='Isms-Test-Pass-2026', groups='university_isms.group_isms_asset_owner')
        cls.owner2 = new_test_user(env, 't_owner2', password='Isms-Test-Pass-2026', groups='university_isms.group_isms_asset_owner')
        cls.auditor = new_test_user(env, 't_auditor', password='Isms-Test-Pass-2026', groups='university_isms.group_isms_auditor')
        cls.analyst = new_test_user(env, 't_analyst', password='Isms-Test-Pass-2026', groups='university_isms.group_isms_analyst')
        cls.manager = new_test_user(env, 't_manager', password='Isms-Test-Pass-2026', groups='university_isms.group_isms_manager')
        cls.asset = env['isms.asset'].create({
            'name': 'Тест SIS', 'owner_id': cls.owner.id, 'classification': 'restricted',
            'confidentiality': '3', 'integrity': '3', 'availability': '2'})
        cls.asset2 = env['isms.asset'].create({'name': 'Өөр нэгжийн хөрөнгө', 'owner_id': cls.owner2.id})
        cls.threat = env.ref('university_isms.threat_t_01')
        cls.vuln = env.ref('university_isms.vuln_v_01')

    def _risk(self, asset, likelihood='4', impact='5', **kw):
        vals = {'name': 'Тест эрсдэл', 'asset_ids': [(6, 0, asset.ids)], 'threat_id': self.threat.id,
                'vulnerability_id': self.vuln.id, 'likelihood': likelihood, 'impact': impact}
        vals.update(kw)
        return self.env['isms.risk'].create(vals)

    # ------------------------------------------------------------ methodology
    def test_01_risk_matrix_25_cells(self):
        for likelihood, row in EXPECTED.items():
            for impact, level in enumerate(row, start=1):
                self.assertEqual(matrix_level(likelihood, impact), level, (likelihood, impact))
        risk = self._risk(self.asset, '5', '1')
        self.assertEqual((risk.score, risk.level), (5, 'medium'))

    def test_02_asset_value_and_risk_rollup(self):
        self.assertEqual(self.asset.asset_value, 3)  # max(C,I,A)
        self.assertEqual(self.asset.criticality, 'high')
        self.assertEqual(self.asset.risk_level, 'none')
        risk = self._risk(self.asset)
        self.assertEqual((risk.score, risk.level), (20, 'high'))
        self.assertEqual(self.asset.risk_level, 'high')
        risk.write({'residual_likelihood': '2', 'residual_impact': '3', 'state': 'residual'})
        self.assertEqual(risk.residual_level, 'medium')
        self.assertEqual(self.asset.risk_level, 'medium', 'Үлдэгдэл үнэлгээ хийгдсэн бол одоогийн түвшин буурна')

    def test_03_annex_a_catalog(self):
        controls = self.env['isms.control'].search([])
        self.assertEqual(len(controls), 93)
        self.assertEqual(len(controls.filtered('is_new_2022')), 11)
        counts = {t: len(controls.filtered(lambda c: c.theme == t))
                  for t in ('organizational', 'people', 'physical', 'technological')}
        self.assertEqual(counts, {'organizational': 37, 'people': 8, 'physical': 14, 'technological': 34})

    # ------------------------------------------------------------------ RBAC
    def test_04_reporter_cannot_read_risk_register(self):
        self._risk(self.asset)
        with self.assertRaises(AccessError):
            self.env['isms.risk'].with_user(self.reporter).search([])

    def test_05_asset_owner_sees_only_own_asset_risks(self):
        own = self._risk(self.asset)
        other = self._risk(self.asset2)
        visible = self.env['isms.risk'].with_user(self.owner).search([])
        self.assertIn(own, visible)
        self.assertNotIn(other, visible)

    def test_06_asset_write_rules(self):
        self.asset.with_user(self.owner).write({'location': 'Серверийн өрөө 1-104'})
        with self.assertRaises(AccessError):
            self.asset2.with_user(self.owner).write({'location': 'хууль бус өөрчлөлт'})
        with self.assertRaises(AccessError):
            self.asset.with_user(self.auditor).write({'location': 'аудитор засах ёсгүй'})
        with self.assertRaises(AccessError):
            self.env['isms.asset'].with_user(self.owner).create({'name': 'эзэмшигч үүсгэх ёсгүй'})
        self.env['isms.asset'].with_user(self.analyst).create({'name': 'Шинжээч үүсгэв'})

    # -------------------------------------------------------- incident workflow
    def test_07_incident_workflow_and_separation(self):
        Incident = self.env['isms.incident']
        inc = Incident.with_user(self.reporter).create({
            'name': 'Сэжигтэй «дүн засах» и-мэйл', 'category': 'phishing', 'severity': 'high'})
        # Хөрөнгийн холбоосыг МАБ-ын баг хийнэ (мэдээлэгч хөрөнгийн бүртгэл харахгүй)
        inc.with_user(self.analyst).write({'asset_ids': [(6, 0, self.asset.ids)]})
        other = Incident.with_user(self.owner2).create({'name': 'Өөр хүний мэдээлэл'})
        self.assertEqual(Incident.with_user(self.reporter).search([]), inc, 'Мэдээлэгч зөвхөн өөрийнхөө')
        self.assertIn(inc, Incident.with_user(self.owner).search([]), 'Эзэмшигч өөрийн хөрөнгийн инцидентийг харна')
        self.assertNotIn(other, Incident.with_user(self.owner).search([]))

        inc.with_user(self.reporter).action_report()
        self.assertEqual(inc.state, 'report')
        self.assertTrue(inc.reported_at and inc.sla_deadline)
        with self.assertRaises(AccessError):
            inc.with_user(self.reporter).action_investigate()
        with self.assertRaises(UserError):  # report → close алгасах хориотой (AccessError ⊂ UserError)
            inc.with_user(self.reporter).write({'state': 'close'})

        inc.with_user(self.analyst).action_investigate()
        self.assertEqual((inc.state, inc.assignee_id), ('investigate', self.analyst))
        with self.assertRaises(UserError):
            inc.with_user(self.analyst).action_resolve()
        inc.with_user(self.analyst).write({'root_cause': 'MFA байхгүй', 'resolution': 'Данс түгжиж, MFA идэвхжүүлэв'})
        inc.with_user(self.analyst).action_resolve()
        with self.assertRaises(AccessError):
            inc.with_user(self.analyst).action_close()
        with self.assertRaises(UserError):
            inc.with_user(self.manager).action_close()
        inc.with_user(self.manager).write({'lessons_learned': 'Бүх ажилтанд MFA заавал'})
        inc.with_user(self.manager).action_close()
        self.assertEqual(inc.state, 'close')
        self.assertEqual(inc.sla_status, 'met')

    # ---------------------------------------------------------- risk treatment
    def test_08_risk_acceptance_requires_ciso(self):
        risk = self._risk(self.asset, '2', '2', treatment='accept', state='respond')
        with self.assertRaises(UserError):
            risk.with_user(self.analyst).action_next_stage()
        with self.assertRaises(AccessError):
            risk.with_user(self.analyst).action_accept_risk()
        risk.with_user(self.manager).action_accept_risk()
        self.assertEqual(risk.accepted_by_id, self.manager)
        risk.with_user(self.analyst).action_next_stage()
        self.assertEqual(risk.state, 'implement')

    def test_09_risk_treatment_task(self):
        risk = self._risk(self.asset, treatment='mitigate', state='respond', owner_id=self.analyst.id)
        risk.with_user(self.analyst).action_create_task()
        self.assertEqual(len(risk.task_ids), 1)
        self.assertEqual(risk.task_ids.project_id, self.env.ref('university_isms.project_risk_treatment'))

    # ---------------------------------------------------------------- policy
    def test_10_policy_approval_and_acknowledgement(self):
        policy = self.env['isms.policy'].with_user(self.analyst).create({'name': 'Хандалтын хяналтын бодлого'})
        self.assertNotIn(policy, self.env['isms.policy'].with_user(self.reporter).search([]))
        with self.assertRaises(AccessError):
            policy.with_user(self.analyst).action_approve()
        policy.with_user(self.manager).action_approve()
        self.assertEqual(policy.state, 'approved')
        reporter_policy = policy.with_user(self.reporter)
        self.assertIn(policy, self.env['isms.policy'].with_user(self.reporter).search([]))
        reporter_policy.action_acknowledge()
        self.assertTrue(reporter_policy.user_has_ack)
        self.assertEqual(policy.ack_count, 1)

    # ------------------------------------------------------------- audit log
    def test_11_audit_log_records_changes_and_is_immutable(self):
        Log = self.env['isms.audit.log']
        self.asset.with_user(self.owner).write({'classification': 'confidential'})
        log = Log.search([('model', '=', 'isms.asset'), ('res_id', '=', self.asset.id),
                          ('action', '=', 'write')], limit=1)
        self.assertEqual(log.user_id, self.owner)
        self.assertIn('Хязгаарлагдмал → Нууц', log.changes)
        with self.assertRaises(UserError):
            log.sudo().write({'changes': 'нотолгоо устгах оролдлого'})
        with self.assertRaises(UserError):
            log.sudo().unlink()
        with self.assertRaises(AccessError):
            Log.with_user(self.analyst).search([])
        self.assertTrue(Log.with_user(self.auditor).search_count([]))

    def test_12_audit_log_privilege_change(self):
        self.reporter.write({'groups_id': [(4, self.env.ref('university_isms.group_isms_analyst').id)]})
        log = self.env['isms.audit.log'].search([('model', '=', 'res.users'), ('res_id', '=', self.reporter.id),
                                                 ('action', '=', 'access_change')], limit=1)
        self.assertIn('Нэмэгдсэн эрх', log.changes)
        self.assertIn('МАБ шинжээч', log.changes)

    def test_13_state_change_and_unlink_logged(self):
        risk = self._risk(self.asset)
        risk.with_user(self.analyst).action_next_stage()
        Log = self.env['isms.audit.log']
        self.assertTrue(Log.search_count([('model', '=', 'isms.risk'), ('res_id', '=', risk.id), ('action', '=', 'state')]))
        risk_id = risk.id
        risk.with_user(self.manager).unlink()
        self.assertTrue(Log.search_count([('model', '=', 'isms.risk'), ('res_id', '=', risk_id), ('action', '=', 'unlink')]))

    # --------------------------------------------- bypass attempts (Codex review)
    def test_14_audit_cannot_be_skipped_by_context(self):
        Log = self.env['isms.audit.log']
        before = Log.search_count([('model', '=', 'isms.asset'), ('res_id', '=', self.asset.id)])
        self.asset.with_user(self.owner).with_context(isms_audit_skip=True).write({'location': 'B-201'})
        after = Log.search_count([('model', '=', 'isms.asset'), ('res_id', '=', self.asset.id)])
        self.assertEqual(after, before + 1, 'Context flag-аар аудит логийг алгасах боломжгүй')

    def test_15_incident_direct_state_write_is_validated(self):
        inc = self.env['isms.incident'].with_user(self.reporter).create({'name': 'Kanban/RPC тест'})
        inc.with_user(self.reporter).write({'state': 'report'})  # kanban drag = action_report
        self.assertEqual(inc.state, 'report')
        with self.assertRaises(AccessError):  # шинжээч биш
            inc.with_user(self.reporter).write({'state': 'investigate'})
        inc.with_user(self.analyst).write({'state': 'investigate'})
        with self.assertRaises(UserError):  # investigate → close алгасах
            inc.with_user(self.analyst).write({'state': 'close'})
        inc.with_user(self.analyst).write({'root_cause': 'x', 'resolution': 'y', 'state': 'resolve'})
        self.assertEqual(inc.state, 'resolve')
        with self.assertRaises(AccessError):  # CISO биш хаах
            inc.with_user(self.analyst).write({'state': 'close'})
        with self.assertRaises(AccessError):
            inc.with_user(self.analyst).write({'closed_at': '2026-01-01 00:00:00'})
        with self.assertRaises(AccessError):
            inc.with_user(self.analyst).write({'code': 'INC-FAKE'})
        with self.assertRaises(AccessError):
            inc.with_user(self.reporter).write({'assignee_id': self.reporter.id})
        inc.with_user(self.manager).write({'lessons_learned': 'z', 'state': 'close'})
        self.assertEqual(inc.state, 'close')
        with self.assertRaises(UserError):
            inc.with_user(self.manager).write({'description': 'хаагдсаны дараа засах'})

    def test_16_incident_create_cannot_forge_state_or_reporter(self):
        Incident = self.env['isms.incident']
        with self.assertRaises(AccessError):
            Incident.with_user(self.analyst).create({'name': 'шууд хаасан', 'state': 'close'})
        with self.assertRaises(AccessError):
            Incident.with_user(self.reporter).create({'name': 'бусдын нэрээр', 'reporter_id': self.owner.id})
        phone = Incident.with_user(self.analyst).create({'name': 'Утсаар ирсэн', 'reporter_id': self.owner.id})
        self.assertEqual(phone.reporter_id, self.owner)

    def test_17_risk_acceptance_and_stage_cannot_be_forged(self):
        risk = self.env['isms.risk'].with_user(self.analyst).create({
            'name': 'RPC хуурамч батлалт', 'asset_ids': [(6, 0, self.asset.ids)], 'threat_id': self.threat.id,
            'likelihood': '2', 'impact': '2', 'treatment': 'accept'})
        with self.assertRaises(AccessError):
            risk.with_user(self.analyst).write({'accepted_by_id': self.manager.id})
        with self.assertRaises(UserError):  # 1 → 5 алгасах
            risk.with_user(self.analyst).write({'state': 'implement'})
        with self.assertRaises(AccessError):
            self.env['isms.risk'].with_user(self.analyst).create({'name': 'x', 'state': 'residual'})
        risk.with_user(self.analyst).write({'state': 'analyze'})
        risk.with_user(self.analyst).write({'state': 'evaluate'})
        risk.with_user(self.manager).action_accept_risk()
        self.assertTrue(risk.accepted_by_id)
        risk.with_user(self.analyst).write({'impact': '5'})
        self.assertFalse(risk.accepted_by_id, 'Үнэлгээ өөрчлөгдвөл хүлээн зөвшөөрөлт хүчингүй болно')
        with self.assertRaises(AccessError):
            risk.with_user(self.owner).action_next_stage()

    def test_18_policy_approval_cannot_be_forged(self):
        Policy = self.env['isms.policy']
        with self.assertRaises(AccessError):
            Policy.with_user(self.analyst).create({'name': 'шууд батлагдсан', 'state': 'approved'})
        policy = Policy.with_user(self.analyst).create({'name': 'EISP'})
        with self.assertRaises(AccessError):
            policy.with_user(self.analyst).write({'state': 'approved'})
        with self.assertRaises(AccessError):
            policy.with_user(self.analyst).write({'approver_id': self.manager.id})
        policy.with_user(self.manager).write({'state': 'approved'})
        self.assertEqual(policy.approver_id, self.manager)
        with self.assertRaises(UserError):
            policy.with_user(self.manager).write({'content': '<p>батлагдсаны дараа нууцаар засах</p>'})
        Ack = self.env['isms.policy.ack']
        with self.assertRaises(AccessError):
            Ack.with_user(self.reporter).create({'policy_id': policy.id, 'user_id': self.owner.id, 'version': '9'})
        ack = Ack.with_user(self.reporter).create({'policy_id': policy.id, 'version': '9'})
        self.assertEqual((ack.user_id, ack.version), (self.reporter, policy.version))
        with self.assertRaises(AccessError):
            ack.with_user(self.reporter).write({'version': '0.1'})

    # ------------------------------------------- 2026-11-18 нэмэлт (аудитын олдвор)
    def test_19_reporter_cannot_read_restricted_registers(self):
        with self.assertRaises(AccessError):
            self.env['isms.asset'].with_user(self.reporter).search([])
        control = self.env['isms.control'].search([('code', '=', '8.5')])
        self.assertTrue(control.with_user(self.reporter).read(['code', 'name_mn']))
        with self.assertRaises(AccessError):
            control.with_user(self.reporter).read(['odoo_implementation'])
        with self.assertRaises(AccessError):
            self.env['isms.incident'].with_user(self.reporter).create({
                'name': 'хөрөнгө холбох оролдлого', 'asset_ids': [(6, 0, self.asset.ids)]})
        self.assertTrue(self.env['isms.asset'].with_user(self.owner).search_count([]))
        self.assertTrue(self.env['isms.asset'].with_user(self.auditor).search_count([]), 'Аудитор хөрөнгийн бүртгэлийг уншина')
        with self.assertRaises(AccessError):
            self.asset.with_user(self.auditor).write({'location': 'аудитор засахгүй'})

    def test_20_residual_risk_accepted_by_risk_owner(self):
        risk = self._risk(self.asset, '4', '5', treatment='mitigate', state='implement', owner_id=self.owner.id,
                          control_ids=[(6, 0, self.env['isms.control'].search([('code', '=', '8.5')]).ids)])
        task = risk._ensure_treatment_tasks()
        self.assertEqual(len(task), 1)
        with self.assertRaises(UserError):  # үлдэгдэл үнэлгээгүй
            risk.with_user(self.owner).action_accept_residual()
        risk.with_user(self.analyst).write({'residual_likelihood': '2', 'residual_impact': '3'})
        with self.assertRaises(UserError):  # Project даалгавар дуусаагүй
            risk.with_user(self.owner).action_accept_residual()
        task.stage_id = self.env.ref('university_isms.task_stage_done')
        with self.assertRaises(AccessError):  # шинжээч эрсдэл хариуцагч биш
            risk.with_user(self.analyst).action_accept_residual()
        with self.assertRaises(AccessError):  # kanban drag ч мөн адил
            risk.with_user(self.analyst).write({'state': 'residual'})
        risk.with_user(self.owner).action_accept_residual()
        self.assertEqual((risk.state, risk.residual_accepted_by_id), ('residual', self.owner))
        self.assertEqual(self.asset.risk_level, 'medium')
        with self.assertRaises(AccessError):
            risk.with_user(self.analyst).write({'residual_accepted_by_id': self.analyst.id})
        risk.with_user(self.analyst).write({'residual_impact': '5'})
        self.assertEqual(risk.state, 'implement', 'Дахин үнэлбэл хариуцагч дахин батална')
        self.assertFalse(risk.residual_accepted_by_id)

    def test_21_treatment_task_created_on_implement(self):
        risk = self._risk(self.asset, '3', '4', treatment='mitigate', state='respond', owner_id=self.analyst.id,
                          treatment_plan='<p>MFA нэвтрүүлэх</p>')
        risk.with_user(self.analyst).action_next_stage()
        self.assertEqual(risk.state, 'implement')
        self.assertEqual(len(risk.task_ids), 1)
        self.assertEqual(risk.task_ids.stage_id, self.env.ref('university_isms.task_stage_doing'))
        risk._ensure_treatment_tasks()
        self.assertEqual(len(risk.task_ids), 1, 'Давхар даалгавар үүсгэхгүй')

    def test_22_bruteforce_login_creates_incident(self):
        Log = self.env['isms.audit.log'].sudo()
        Incident = self.env['isms.incident']
        login = 'victim@formula.example'
        for _i in range(4):
            Log.create({'action': 'login_failed', 'login': login, 'ip_address': '10.0.0.66'})
        self.assertFalse(Incident._isms_detect_bruteforce(login))
        Log.create({'action': 'login_failed', 'login': login, 'ip_address': '10.0.0.66'})
        incident = Incident._isms_detect_bruteforce(login)
        self.assertEqual((incident.state, incident.category, incident.reporter_type),
                         ('report', 'unauthorized_access', 'system'))
        self.assertIn('10.0.0.66', incident.description)
        self.assertEqual(Incident._isms_detect_bruteforce(login), incident, 'Нээлттэй бол давхардуулахгүй')
        self.assertIn(incident, Incident.with_user(self.analyst).search([('detection_key', '!=', False)]))
        with self.assertRaises(AccessError):
            incident.with_user(self.analyst).write({'detection_key': False})

    def test_23_monitoring_reminders_kpis_and_report(self):
        today = fields.Date.context_today(self.env['isms.risk'])
        policy = self.env['isms.policy'].with_user(self.analyst).create({'name': 'Хянах хугацаа ойртсон бодлого'})
        policy.with_user(self.manager).action_approve()
        policy.sudo().write({'next_review_date': today + timedelta(days=5)})
        risk = self._risk(self.asset, '3', '3', treatment='mitigate', state='respond', owner_id=self.analyst.id,
                          due_date=today - timedelta(days=3))
        incident = self.env['isms.incident'].sudo().create({
            'name': 'SLA хэтэрсэн', 'severity': 'critical', 'assignee_id': self.analyst.id,
            'detected_at': fields.Datetime.now() - timedelta(days=2)})
        self.assertIn(incident, self.env['isms.incident'].search([('sla_status', '=', 'breached')]))
        self.assertIn(risk, self.env['isms.risk'].search([('is_overdue', '=', True)]))
        Monitoring = self.env['isms.monitoring']
        first = Monitoring._cron_daily_monitoring()
        self.assertTrue(first['policy_review'] >= 1 and first['risk_overdue'] >= 1 and first['incident_sla'] >= 1)
        for record in (policy, risk, incident):
            self.assertTrue(record.activity_ids, record._name)
        second = Monitoring._cron_daily_monitoring()
        self.assertEqual(second, {'policy_review': 0, 'risk_overdue': 0, 'incident_sla': 0}, 'Давхар сануулгагүй')
        kpi = Monitoring._isms_kpis()
        self.assertEqual(kpi['soa_total'], 93)
        self.assertGreaterEqual(kpi['risks_overdue'], 1)
        report = self.env['ir.actions.report']
        html = report.with_user(self.auditor)._render_qweb_html(
            'university_isms.report_management_review', self.env.company.ids)[0]
        self.assertIn(b'Clause 9.3', html)
        with self.assertRaises(AccessError):
            report.with_user(self.reporter)._render_qweb_html(
                'university_isms.report_management_review', self.env.company.ids)

    def test_24_admin_account_has_no_ciso_rights(self):
        admin = self.env.ref('base.user_admin')
        self.assertFalse(admin.has_group('university_isms.group_isms_manager'))
        self.assertTrue(admin.has_group('university_isms.group_isms_reporter'))
        self.assertTrue(admin.has_group('base.group_system'))

    def test_25_report_menus_work_for_read_only_auditor(self):
        for xmlid in ('action_server_print_soa', 'action_server_print_risks', 'action_server_print_assets',
                      'action_server_print_management_review'):
            action = self.env.ref('university_isms.' + xmlid)
            result = action.with_user(self.auditor).run()
            self.assertEqual(result.get('type'), 'ir.actions.report', xmlid)
            with self.assertRaises(AccessError):
                action.with_user(self.reporter).run()
        monitoring = self.env.ref('university_isms.action_server_run_monitoring')
        self.assertEqual(monitoring.with_user(self.manager).run().get('tag'), 'display_notification')
        with self.assertRaises(AccessError):
            monitoring.with_user(self.analyst).run()
