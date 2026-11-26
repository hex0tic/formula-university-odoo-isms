"""university_access_review: эрхийн тойм бодит эрхтэй таарч, зөвхөн эрх бүхий хүн ашиглана."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

PASS = 'Isms-Test-Pass-2026'


@tagged('post_install', '-at_install', 'university_access_review')
class TestAccessReview(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.admin_mgr = new_test_user(env, 't_rights_mgr', password=PASS,
                                      groups='base.group_user,base.group_erp_manager')
        cls.analyst = new_test_user(env, 't_rev_analyst', password=PASS,
                                    groups='university_isms.group_isms_analyst,project.group_project_user')
        cls.reporter = new_test_user(env, 't_rev_reporter', password=PASS,
                                     groups='university_isms.group_isms_reporter')
        cls.Review = env['access.review'].with_user(cls.admin_mgr)

    def _line(self, review, model):
        return review.model_line_ids.filtered(lambda l: l.model == model)

    def _action(self, review, name):
        return review.action_line_ids.filtered(lambda l: l.name == name)

    def test_review_matches_real_rights(self):
        review = self.Review.create({'user_id': self.analyst.id})
        incident = self._line(review, 'isms.incident')
        self.assertTrue(incident.can_read and incident.can_write and incident.can_create)
        self.assertFalse(incident.can_unlink, 'Шинжээч зөрчил устгахгүй')
        self.assertEqual(incident.visible_count, self.env['isms.incident'].with_user(self.analyst).search_count([]))
        self.assertFalse(self._line(review, 'isms.audit.log').can_read, 'Шинжээч аудит лог уншихгүй')
        self.assertTrue(self._action(review, 'Зөрчлийг шалгах, шийдвэрлэх').allowed)
        self.assertFalse(self._action(review, 'Зөрчил хаах, дахин нээх').allowed)
        self.assertFalse(self._action(review, 'Бодлого батлах').allowed)
        self.assertEqual(review.isms_role, '4. МАБ шинжээч')
        self.assertEqual(len(review.project_line_ids), self.env['project.project'].search_count([]))

    def test_reporter_sees_less_than_analyst(self):
        review = self.Review.create({'user_id': self.reporter.id})
        self.assertFalse(self._line(review, 'isms.risk').can_read)
        self.assertFalse(self._line(review, 'isms.asset').can_write)
        self.assertTrue(self._action(review, 'Зөрчил мэдээлэх').allowed)

    def test_employee_cannot_see_own_rights(self):
        with self.assertRaises(AccessError):
            self.env['access.review'].with_user(self.analyst).create({'user_id': self.analyst.id})
        with self.assertRaises(AccessError):
            self.env['access.review'].with_user(self.reporter).search([])
        with self.assertRaises(AccessError):
            self.analyst.with_user(self.analyst).action_open_access_review()

    def test_apply_groups_changes_user_and_is_audited(self):
        review = self.Review.create({'user_id': self.reporter.id})
        analyst_group = self.env.ref('university_isms.group_isms_analyst')
        line = review.group_line_ids.filtered(lambda l: l.group_id == analyst_group)
        self.assertFalse(line.granted)
        logs_before = self.env['isms.audit.log'].sudo().search_count([('action', '=', 'access_change')])
        line.granted = True
        review.action_apply_groups()
        self.assertTrue(self.reporter.has_group('university_isms.group_isms_analyst'))
        self.assertTrue(self._line(review, 'isms.risk').can_read, 'Хадгалсны дараа тойм шинэчлэгдэнэ')
        logs_after = self.env['isms.audit.log'].sudo().search_count([('action', '=', 'access_change')])
        self.assertGreater(logs_after, logs_before, 'Эрхийн өөрчлөлт аудит логт бичигдэнэ')
        # хасах
        review.group_line_ids.filtered(lambda l: l.group_id == analyst_group).granted = False
        review.action_apply_groups()
        self.assertFalse(self.reporter.has_group('university_isms.group_isms_analyst'))
        self.assertTrue(self.reporter.has_group('base.group_user'), 'Хэрэглэгчийн төрөл хэвээр')

    def test_cannot_change_own_rights(self):
        review = self.Review.create({'user_id': self.admin_mgr.id})
        with self.assertRaises(UserError):
            review.action_apply_groups()


@tagged('post_install', '-at_install', 'university_access_review')
class TestAccessGovernance(TransactionCase):
    """GOV-05 давуу эрх, GOV-02 үүргийн тусгаарлалт, WF-06 эрхийн эх сурвалж."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.rights_mgr = new_test_user(env, 't_gov_rights', password=PASS,
                                       groups='base.group_user,base.group_erp_manager')
        cls.sysadmin = new_test_user(env, 't_gov_sys', password=PASS,
                                     groups='base.group_user,base.group_system')
        cls.target = new_test_user(env, 't_gov_target', password=PASS,
                                   groups='university_isms.group_isms_auditor')
        cls.ciso = new_test_user(env, 't_gov_ciso', password=PASS,
                                 groups='university_isms.group_isms_manager')

    def _review(self, as_user, user):
        return self.env['access.review'].with_user(as_user).create({'user_id': user.id})

    def _grant(self, review, xmlid, value=True):
        group = self.env.ref(xmlid)
        review.group_line_ids.filtered(lambda l: l.group_id == group).granted = value

    def test_privileged_grant_requires_system_admin(self):
        review = self._review(self.rights_mgr, self.target)
        self._grant(review, 'base.group_erp_manager')
        with self.assertRaises(AccessError):
            review.action_apply_groups()
        self.assertFalse(self.target.has_group('base.group_erp_manager'))
        review = self._review(self.sysadmin, self.target)
        self._grant(review, 'base.group_erp_manager')
        review.action_apply_groups()
        self.assertTrue(self.target.has_group('base.group_erp_manager'))

    def test_sod_conflict_blocked(self):
        review = self._review(self.rights_mgr, self.target)
        self._grant(review, 'university_isms.group_isms_analyst')
        with self.assertRaises(UserError):
            review.action_apply_groups()
        self.assertFalse(self.target.has_group('university_isms.group_isms_analyst'))

    def test_ciso_is_not_flagged(self):
        review = self._review(self.rights_mgr, self.ciso)
        self.assertFalse(review.sod_warnings)

    def test_acl_source_is_explained(self):
        review = self._review(self.rights_mgr, self.target)
        line = review.model_line_ids.filtered(lambda l: l.model == 'isms.audit.log')
        self.assertTrue(line.can_read)
        self.assertIn(self.env.ref('university_isms.group_isms_auditor').name, line.granted_by)
