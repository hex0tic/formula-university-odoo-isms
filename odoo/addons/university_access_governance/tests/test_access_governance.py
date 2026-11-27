"""university_access_governance: GOV-01, GOV-03, GOV-04, GOV-05 серверийн шалгалтууд."""
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.university_access_governance.models.recert import ESCALATION_SUMMARY
from odoo.tests import TransactionCase, new_test_user, tagged

PASS = 'Gov-Test-Pass-2026'
JUSTIFICATION = 'Шалгалтын ажлын үйл ажиллагаанд шаардлагатай хандалт.'


@tagged('post_install', '-at_install', 'university_access_governance')
class TestAccessGovernance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.sys_admin = new_test_user(env, 'gov_sys', password=PASS,
                                      groups='base.group_user,base.group_system')
        cls.erp = new_test_user(env, 'gov_erp', password=PASS,
                                groups='base.group_user,base.group_erp_manager')
        cls.auditor = new_test_user(env, 'gov_auditor', password=PASS,
                                    groups='base.group_user,university_isms.group_isms_auditor')
        cls.ciso = new_test_user(env, 'gov_ciso', password=PASS,
                                 groups='base.group_user,university_isms.group_isms_manager')
        cls.manager = new_test_user(env, 'gov_manager', password=PASS, groups='base.group_user')
        cls.staff = new_test_user(env, 'gov_staff', password=PASS,
                                  groups='base.group_user,university_isms.group_isms_analyst')
        cls.orphan = new_test_user(env, 'gov_orphan', password=PASS,
                                   groups='base.group_user,university_isms.group_isms_reporter')
        cls.requester = new_test_user(env, 'gov_requester', password=PASS,
                                      groups='base.group_user,university_isms.group_isms_reporter')
        cls.plain = new_test_user(env, 'gov_plain', password=PASS, groups='base.group_user')
        Employee = env['hr.employee'].sudo()
        cls.manager_emp = Employee.create({'name': 'Менежер', 'user_id': cls.manager.id})
        Employee.create({'name': 'Ажилтан', 'user_id': cls.staff.id, 'parent_id': cls.manager_emp.id})
        cls.analyst = env.ref('university_isms.group_isms_analyst')
        cls.reporter = env.ref('university_isms.group_isms_reporter')
        cls.auditor_group = env.ref('university_isms.group_isms_auditor')
        cls.erp_group = env.ref('base.group_erp_manager')
        cls.Campaign = env['access.recert.campaign'].sudo()
        cls.Line = env['access.recert.line']
        cls.Request = env['access.request']
        cls.Report = env['access.gov.report']

    # ------------------------------------------------------------ helpers
    def _campaign(self, **kw):
        vals = {'name': 'Тойм', 'scope': 'groups', 'group_ids': [(6, 0, [self.analyst.id])],
                'start_date': fields.Date.context_today(self.env['res.users']), 'due_days': 14,
                'fallback_reviewer_id': self.ciso.id}
        vals.update(kw)
        campaign = self.Campaign.create(vals)
        campaign.action_start()
        return campaign

    def _line(self, campaign, user):
        return campaign.line_ids.filtered(lambda l: l.user_id == user)

    def _request(self, requester, target, groups, days=2, justification=JUSTIFICATION, start_offset=None):
        now = fields.Datetime.now()
        start = now + timedelta(hours=start_offset or 0)
        return self.Request.with_user(requester).create({
            'requester_id': requester.id,
            'target_user_id': target.id,
            'group_ids': [(6, 0, [g.id for g in groups])],
            'justification': justification,
            'start_date': start,
            'end_date': start + timedelta(days=days),
        })

    # ------------------------------------------------------------ GOV-01 campaign
    def test_campaign_reviewer_manager_and_fallback(self):
        campaign = self._campaign()
        staff_line = self._line(campaign, self.staff)
        self.assertEqual(staff_line.reviewer_id, self.manager, 'Шууд менежер хянагч болно')
        self.assertEqual(staff_line.campaign_id.due_date, fields.Date.context_today(self.env['res.users']) + timedelta(days=14))
        orphan_campaign = self._campaign(group_ids=[(6, 0, [self.reporter.id])], scope='groups')
        orphan_line = self._line(orphan_campaign, self.orphan)
        self.assertEqual(orphan_line.reviewer_id, self.ciso, 'Менежергүй бол нөөц CISO хянагч')

    def test_recurring_campaign_is_idempotent(self):
        root = self._campaign(name='Улирлын', recurring=True, cadence='30',
                              start_date=fields.Date.context_today(self.env['res.users']) - timedelta(days=31))
        self.Campaign._cron_create_recurring()
        self.Campaign._cron_create_recurring()
        children = self.Campaign.search([('parent_id', '=', root.id)])
        self.assertEqual(len(children), 1, 'Дараагийн кампанит нэг л удаа үүснэ')
        self.assertEqual(children.state, 'running')
        self.assertFalse(children.recurring)

    def test_self_certification_and_direct_writes_blocked(self):
        campaign = self._campaign(scope='privileged', group_ids=[(5, 0, 0)],
                                  fallback_reviewer_id=self.sys_admin.id)
        own = self._line(campaign, self.sys_admin)
        self.assertFalse(own.reviewer_id, 'Өөрийгөө хянах хүн байхгүй: fallback нь өөрөө')
        with self.assertRaises(AccessError):
            own.with_user(self.sys_admin).action_keep()
        erp_line = self._line(campaign, self.erp)
        self.assertEqual(erp_line.reviewer_id, self.sys_admin)
        with self.assertRaises(AccessError):
            erp_line.with_user(self.sys_admin).write({'decision': 'keep'})
        with self.assertRaises(AccessError):
            erp_line.with_user(self.erp).action_keep()
        staff_campaign = self._campaign()
        staff_line = self._line(staff_campaign, self.staff)
        with self.assertRaises(AccessError):
            staff_line.with_user(self.manager).write({'decision': 'keep'})
        with self.assertRaises(AccessError):
            staff_line.with_user(self.staff).action_keep()

    def test_recertification_ignores_workflow_context(self):
        campaign = self.Campaign.with_user(self.erp).with_context(default_state='done').create({
            'name': 'Тойм',
            'scope': 'groups',
            'group_ids': [Command.set(self.analyst.ids)],
        })
        self.assertEqual(campaign.state, 'draft')
        with self.assertRaises(AccessError):
            campaign.write({'state': 'running'})
        campaign.action_start()

        reviewer_line = self._line(campaign, self.staff).with_user(self.manager)
        with self.assertRaises(AccessError):
            reviewer_line.with_context(access_gov_action=True).write({'outcome': 'Unverified'})
        self.assertFalse(reviewer_line.outcome)
        reviewer_line.write({'note': 'Reviewed'})
        reviewer_line.action_keep()
        self.assertEqual(reviewer_line.decision, 'keep')
        self.assertEqual(reviewer_line.decided_by_id, self.manager)

        line = self.Line.with_user(self.erp).with_context(
            default_decision='keep', default_decided_by_id=self.erp.id, default_escalated=True,
        ).create({
            'campaign_id': campaign.id,
            'user_id': self.plain.id,
            'reviewer_id': self.manager.id,
        })
        self.assertEqual(line.decision, 'pending')
        self.assertFalse(line.decided_by_id)
        self.assertFalse(line.escalated)
        with self.assertRaises(UserError):
            campaign.action_close()

    def test_revoke_removes_group_and_is_audited(self):
        campaign = self._campaign()
        line = self._line(campaign, self.staff)
        with self.assertRaises(UserError):
            campaign.action_close()
        line.with_user(self.manager).revoke_group_ids = [(6, 0, [self.analyst.id])]
        line.with_user(self.manager).action_revoke()
        self.assertFalse(self.staff.has_group('university_isms.group_isms_analyst'))
        self.assertEqual(line.decision, 'revoke')
        audit = self.env['isms.audit.log'].sudo().search([
            ('action', '=', 'access_change'), ('res_id', '=', self.staff.id), ('user_id', '=', self.manager.id)])
        self.assertTrue(audit, 'Хянагчийн нэрээр эрхийн өөрчлөлт аудит логт бичигдэнэ')
        line_done = self.Campaign.browse(campaign.id)
        # Кампанид бусад хэрэглэгч (нэмэлт analyst) байж болно: үлдсэн мөрийг системийн админ шийдвэрлэнэ.
        for other in line_done.line_ids.filtered(lambda l: l.decision == 'pending'):
            other.with_user(self.sys_admin).action_keep()
        self.assertFalse(line_done.line_ids.filtered(lambda l: l.decision == 'pending'))
        line_done.with_user(self.sys_admin).action_close()
        self.assertEqual(line_done.state, 'done')

    def test_privileged_revoke_by_non_system_blocked(self):
        priv_user = new_test_user(self.env, 'gov_priv_staff', password=PASS,
                                  groups='base.group_user,base.group_erp_manager')
        self.env['hr.employee'].sudo().create({'name': 'Priv', 'user_id': priv_user.id,
                                               'parent_id': self.manager_emp.id})
        campaign = self._campaign(scope='privileged', group_ids=[(5, 0, 0)])
        line = self._line(campaign, priv_user)
        self.assertEqual(line.reviewer_id, self.manager)
        line.with_user(self.manager).revoke_group_ids = [(6, 0, [self.erp_group.id])]
        with self.assertRaises(AccessError):
            line.with_user(self.manager).action_revoke()
        self.assertTrue(priv_user.has_group('base.group_erp_manager'))

    def test_overdue_escalation_is_idempotent(self):
        today = fields.Date.context_today(self.env['res.users'])
        campaign = self._campaign(start_date=today - timedelta(days=10), due_days=3)
        line = self._line(campaign, self.staff)
        Activity = self.env['mail.activity'].sudo()
        self.Line._cron_escalate_overdue()
        self.Line._cron_escalate_overdue()
        line = line.sudo()
        self.assertTrue(line.escalated)
        domain = [('res_model', '=', 'access.recert.line'), ('res_id', '=', line.id),
                  ('summary', '=', ESCALATION_SUMMARY)]
        count = Activity.search_count(domain)
        self.assertEqual(count, 1, 'Нэг нөөц хянагч нэг эскалац авна')
        self.Line._cron_escalate_overdue()
        self.assertEqual(Activity.search_count(domain), count, 'Давтан ажиллахад давхардахгүй')
        if 'isms.finding' in self.env:
            findings = self.env['isms.finding'].sudo().search([('source_key', '=', 'access.recert.line:%s' % line.id)])
            self.assertEqual(len(findings), 1)

    def test_reviewer_sees_only_own_lines(self):
        campaign = self._campaign(group_ids=[(6, 0, [self.analyst.id, self.reporter.id])])
        staff_line = self._line(campaign, self.staff)
        orphan_line = self._line(campaign, self.orphan)
        self.assertEqual(staff_line.reviewer_id, self.manager)
        self.assertEqual(orphan_line.reviewer_id, self.ciso)
        visible = self.Line.with_user(self.manager).search([])
        self.assertIn(staff_line.id, visible.ids)
        self.assertNotIn(orphan_line.id, visible.ids, 'Хянагч бусдын мөрийг харахгүй')
        self.assertFalse(self.Line.with_user(self.plain).search([]).ids)
        self.assertIn(orphan_line.id, self.Line.with_user(self.ciso).search([]).ids)

    # ------------------------------------------------------------ GOV-03 requests
    def test_self_and_target_approval_blocked(self):
        own = self._request(self.erp, self.erp, [self.analyst])
        own.with_user(self.erp).action_submit()
        with self.assertRaises(AccessError):
            own.with_user(self.erp).action_approve()
        other = self._request(self.requester, self.erp, [self.analyst])
        other.with_user(self.requester).action_submit()
        with self.assertRaises(AccessError):
            other.with_user(self.erp).action_approve()

    def test_non_manager_cannot_approve(self):
        req = self._request(self.requester, self.staff, [self.analyst])
        req.with_user(self.requester).action_submit()
        with self.assertRaises(AccessError):
            req.with_user(self.auditor).action_approve()
        with self.assertRaises(AccessError):
            req.with_user(self.requester).write({'state': 'approved'})

    def test_privileged_needs_system_approver(self):
        req = self._request(self.requester, self.staff, [self.erp_group])
        self.assertTrue(req.is_privileged)
        req.with_user(self.requester).action_submit()
        with self.assertRaises(AccessError):
            req.with_user(self.erp).action_approve()
        req.with_user(self.sys_admin).action_approve()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(req.approver_id, self.sys_admin)

    def test_sod_conflict_blocks_approval(self):
        req = self._request(self.requester, self.auditor, [self.analyst])
        req.with_user(self.requester).action_submit()
        with self.assertRaises(UserError):
            req.with_user(self.erp).action_approve()
        self.assertEqual(req.state, 'submitted')

    def test_duration_and_justification_limits(self):
        with self.assertRaises(ValidationError):
            self._request(self.requester, self.staff, [self.analyst], days=31)
        with self.assertRaises(ValidationError):
            self._request(self.requester, self.staff, [self.erp_group], days=8)
        with self.assertRaises(ValidationError):
            self._request(self.requester, self.staff, [self.analyst], justification='kratko')

    def test_activation_and_cron_expiry_revoke_only_added_groups(self):
        req = self._request(self.requester, self.orphan, [self.analyst, self.reporter], days=1)
        req.with_user(self.requester).action_submit()
        req.with_user(self.erp).action_approve()
        req.with_user(self.erp).action_activate()
        self.assertEqual(req.state, 'active')
        self.assertTrue(self.orphan.has_group('university_isms.group_isms_analyst'))
        self.assertEqual(req.added_group_ids, self.analyst, 'Аль хэдийн байсан бүлэг нэмэгдэхгүй')
        with self.assertRaises(AccessError):
            req.with_user(self.erp).write({'state': 'expired'})
        now = fields.Datetime.now()
        req.sudo().write({'start_date': now - timedelta(hours=3), 'end_date': now - timedelta(hours=1)})
        self.Request._cron_process_grants()
        self.Request._cron_process_grants()
        self.assertEqual(req.sudo().state, 'expired')
        self.assertFalse(self.orphan.has_group('university_isms.group_isms_analyst'))
        self.assertTrue(self.orphan.has_group('university_isms.group_isms_reporter'), 'Өмнөх эрх хэвээр')

    def test_future_approved_request_waits_for_start(self):
        req = self._request(self.requester, self.orphan, [self.analyst], start_offset=5)
        req.with_user(self.requester).action_submit()
        req.with_user(self.erp).action_approve()
        self.Request._cron_process_grants()
        self.assertEqual(req.sudo().state, 'approved')
        self.assertFalse(self.orphan.has_group('university_isms.group_isms_analyst'))

    def _activate_for_orphan(self, *groups):
        req = self._request(self.requester, self.orphan, groups)
        req.action_submit()
        req.with_user(self.erp).action_approve()
        req.with_user(self.erp).action_activate()
        return req.sudo()

    def _expire_request(self, request):
        now = fields.Datetime.now()
        request.write({'start_date': now - timedelta(hours=3),
                       'end_date': now - timedelta(hours=1)})

    def test_overlapping_role_survives_first_expiry(self):
        first = self._activate_for_orphan(self.analyst, self.reporter)
        second = self._activate_for_orphan(self.analyst, self.reporter)
        self.assertFalse(second.added_group_ids)
        self._expire_request(first)
        self.Request._cron_process_grants()
        self.assertEqual(first.state, 'expired')
        self.assertIn(self.analyst, self.orphan.groups_id)
        self.assertFalse(second.added_group_ids, 'Activation history must stay unchanged')
        second.with_user(self.erp).action_revoke()
        self.assertNotIn(self.analyst, self.orphan.groups_id)
        self.assertIn(self.reporter, self.orphan.groups_id)

    def test_overlapping_role_survives_newer_request_revocation(self):
        first = self._activate_for_orphan(self.analyst)
        second = self._activate_for_orphan(self.analyst)
        second.with_user(self.erp).action_revoke()
        self.assertIn(self.analyst, self.orphan.groups_id)
        first.with_user(self.erp).action_revoke()
        self.assertNotIn(self.analyst, self.orphan.groups_id)

    def test_overlapping_inherited_membership_follows_surviving_request(self):
        parent = self.env['res.groups'].create({
            'name': 'Temporary role with inherited membership',
            'implied_ids': [Command.link(self.analyst.id)],
        })
        first = self._activate_for_orphan(parent)
        second = self._activate_for_orphan(self.analyst)
        first.with_user(self.erp).action_revoke()
        self.assertIn(self.analyst, self.orphan.groups_id)
        self.assertNotIn(parent, self.orphan.groups_id)
        second.with_user(self.erp).action_revoke()
        self.assertNotIn(self.analyst, self.orphan.groups_id)
        self.assertIn(self.reporter, self.orphan.groups_id)

    def test_expiring_overlapping_parent_and_child_cleans_both(self):
        parent = self.env['res.groups'].create({
            'name': 'Temporary parent',
            'implied_ids': [Command.link(self.analyst.id)],
        })
        for group in (parent, self.analyst):
            with self.subTest(first_group=group.id):
                first = self._activate_for_orphan(group)
                second = self._activate_for_orphan(parent if group == self.analyst else self.analyst)
                self._expire_request(first)
                self._expire_request(second)
                self.Request._cron_process_grants()
                self.assertEqual((first.state, second.state), ('expired', 'expired'))
                self.assertFalse((self.analyst | parent) & self.orphan.groups_id)

    def test_legacy_active_request_transfers_its_explicit_grant(self):
        first = self._activate_for_orphan(self.analyst)
        first.write({'managed_group_ids': [Command.clear()]})
        second = self._activate_for_orphan(self.analyst)
        first.with_user(self.erp).action_revoke()
        self.assertIn(self.analyst, self.orphan.groups_id)
        second.with_user(self.erp).action_revoke()
        self.assertNotIn(self.analyst, self.orphan.groups_id)

    def test_requester_sees_only_own_requests(self):
        mine = self._request(self.requester, self.requester, [self.analyst])
        self.assertIn(mine.id, self.Request.with_user(self.requester).search([]).ids)
        self.assertFalse(self.Request.with_user(self.plain).search([]).ids)
        self.assertNotIn(mine.id, self.Request.with_user(self.orphan).search([]).ids)

    def test_request_workflow_fields_remain_protected_with_context(self):
        req = self._request(self.plain, self.plain, [self.analyst]).with_context(access_gov_action=True)
        with self.assertRaises(AccessError):
            req.write({'outcome': 'Unverified'})
        req.action_submit()
        with self.assertRaises(AccessError):
            req.write({'justification': 'New justification after submission.'})
        self.assertEqual(req.state, 'submitted')
        self.assertFalse(req.outcome)

    def test_request_privilege_and_creation_metadata_are_server_derived(self):
        delegated_group = self.env['res.groups'].sudo().create({
            'name': 'Governance test role',
            'implied_ids': [Command.link(self.erp_group.id)],
        })
        start = fields.Datetime.now()
        Request = self.Request.with_user(self.requester).with_context(
            default_requester_id=self.plain.id, default_state='approved',
            default_approver_id=self.erp.id, default_is_privileged=False,
        )
        req = Request.create({
            'target_user_id': self.staff.id,
            'group_ids': [Command.set(delegated_group.ids)],
            'justification': JUSTIFICATION,
            'start_date': start,
            'end_date': start + timedelta(days=2),
        })
        self.assertEqual(req.requester_id, self.requester)
        self.assertEqual(req.state, 'draft')
        self.assertFalse(req.approver_id)
        self.assertTrue(req.is_privileged)
        with self.assertRaises(AccessError):
            req.write({'is_privileged': False})
        req.action_submit()
        with self.assertRaises(AccessError):
            req.with_user(self.erp).action_approve()
        req.with_user(self.sys_admin).action_approve()
        self.assertEqual(req.approver_id, self.sys_admin)

    # ------------------------------------------------------------ GOV-04 report
    def test_report_visibility_and_no_secrets(self):
        rows = self.Report.with_user(self.auditor).search([('login', '=', self.erp.login)])
        self.assertTrue(rows)
        self.assertEqual(rows[0].group_id, self.erp_group)
        self.assertIn(rows[0].id, self.Report.with_user(self.sys_admin).search([]).ids)
        with self.assertRaises(AccessError):
            self.Report.with_user(self.plain).search([])
        with self.assertRaises(AccessError):
            self.Report.with_user(self.staff).search([])
        with self.assertRaises(AccessError):
            self.Report.with_user(self.erp).create({'login': 'x'})
        for secret in ('password', 'totp_secret', 'api_key_ids', 'password_crypt'):
            self.assertNotIn(secret, self.Report._fields)
        self.assertIsInstance(rows[0].totp_enabled, bool)
        report_row = self.Report.with_user(self.auditor).search([('login', '=', self.erp.login)]).read(
            ['login', 'totp_enabled'])[0]
        self.assertNotIn('totp_secret', report_row)
