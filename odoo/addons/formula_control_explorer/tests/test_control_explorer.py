"""ISO Control Explorer (WF-05): каталог, шүүлтүүр, холбоос, эрх, тооцсон шалгалт.

Бүх тест өөрийн бичлэгээ үүсгэнэ (seed өгөгдөлд найдахгүй) ба TransactionCase дотор
rollback хийгдэнэ. Хэрэглэгчийн эрх ``with_user()``-ээр шалгагдана.
"""
from datetime import date

from odoo.tests import TransactionCase, new_test_user, tagged

ROLE_GROUPS = {
    'reporter': 'university_isms.group_isms_reporter',
    'owner': 'university_isms.group_isms_asset_owner',
    'analyst': 'university_isms.group_isms_analyst',
    'auditor': 'university_isms.group_isms_auditor',
}
CATALOG_SIZE = 93


@tagged('post_install', '-at_install', 'formula_control_explorer')
class TestControlExplorer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.explorer = env['formula.control.explorer']
        cls.Control = env['isms.control']
        cls.Risk = env['isms.risk']
        cls.Asset = env['isms.asset']
        cls.Incident = env['isms.incident']
        cls.Policy = env['isms.policy']
        cls.admin = env.ref('base.user_admin')
        cls.users = {
            role: new_test_user(env, login='fce_%s' % role, groups=group)
            for role, group in ROLE_GROUPS.items()
        }
        cls.plain_user = new_test_user(env, login='fce_plain', groups='base.group_user')
        owner = cls.users['owner']

        cls.ctrl = cls.Control.search([('code', '=', '5.3')], limit=1)
        cls.ctrl_other = cls.Control.search([('code', '=', '8.5')], limit=1)

        # Хөрөнгө: нэг нь эзэмшигчийнх, нэг нь admin-ийнх
        asset_owned = cls.Asset.create({'name': 'FCE owned asset', 'owner_id': owner.id})
        asset_admin = cls.Asset.create({'name': 'FCE admin asset', 'owner_id': cls.admin.id})
        cls.ctrl.write({'asset_ids': [(6, 0, (asset_owned | asset_admin).ids)]})

        # Эрсдэл: нэг нь эзэмшигчид харагдана, нөгөө нь харагдахгүй (эзэмшигчийн дүрмээр)
        cls.risk_visible = cls.Risk.create({
            'name': 'FCE visible risk', 'owner_id': owner.id,
            'asset_ids': [(6, 0, asset_owned.ids)], 'control_ids': [(6, 0, cls.ctrl.ids)],
        })
        cls.risk_hidden = cls.Risk.create({
            'name': 'FCE hidden risk', 'owner_id': cls.admin.id,
            'asset_ids': [(6, 0, asset_admin.ids)], 'control_ids': [(6, 0, cls.ctrl.ids)],
        })

        # Инцидент: control_ids талбар нь зөвхөн шинжээч/аудитор уншина
        cls.incident = cls.Incident.create({
            'name': 'FCE incident', 'control_ids': [(6, 0, cls.ctrl.ids)],
        })

        # Бодлого: батлагдсан (хугацаа хэтэрсэн) ба ноорог. Ноорог нь reporter-т харагдахгүй.
        cls.policy_approved = cls.Policy.create({
            'name': 'FCE approved policy', 'policy_type': 'issp', 'state': 'approved',
            'next_review_date': date(2020, 1, 1), 'control_ids': [(6, 0, cls.ctrl.ids)],
        })
        cls.policy_draft = cls.Policy.create({
            'name': 'FCE draft policy', 'policy_type': 'issp',
            'control_ids': [(6, 0, cls.ctrl.ids)],
        })

    # ------------------------------------------------------------------ helpers
    def _detail(self, user, control):
        return self.explorer.with_user(user).get_control_detail(control.id)

    def _catalog(self, user, filters=None):
        return self.explorer.with_user(user).get_catalog(filters or {})

    def _findings(self, detail):
        return {item['key']: item for item in detail['findings']}

    # ------------------------------------------------------------------ catalog
    def test_catalog_count_equals_orm_count(self):
        """Каталогийн тоо ORM-ийн тоотой тэнцэнэ (эрх бүрээр)."""
        for role, user in self.users.items():
            with self.subTest(role=role):
                result = self._catalog(user)
                self.assertTrue(result['available'])
                expected = self.Control.with_user(user).search_count([])
                self.assertEqual(result['total'], expected)
                self.assertEqual(result['summary']['catalog'], expected)
                self.assertEqual(len(result['items']), expected)
        self.assertEqual(self.Control.search_count([]), CATALOG_SIZE)

    def test_filters_match_equivalent_orm_domains(self):
        owner = self.users['owner']
        cases = [
            ({'theme': 'technological'}, [('theme', '=', 'technological')]),
            ({'selected': 'yes'}, [('selected', '=', True)]),
            ({'selected': 'no'}, [('selected', '=', False)]),
            ({'applicable': 'no'}, [('applicable', '=', False)]),
            ({'implementation': 'partial'}, [('implementation', '=', 'partial')]),
            ({'new_2022': True}, [('is_new_2022', '=', True)]),
            ({'owner_id': owner.id}, [('responsible_id', '=', owner.id)]),
            ({'search': '5.1'}, ['|', '|', ('code', 'ilike', '5.1'), ('name', 'ilike', '5.1'),
                                 ('name_mn', 'ilike', '5.1')]),
            ({'theme': 'people', 'selected': 'yes', 'implementation': 'no'},
             [('theme', '=', 'people'), ('selected', '=', True), ('implementation', '=', 'no')]),
        ]
        for role in ('reporter', 'analyst', 'auditor'):
            user = self.users[role]
            for filters, domain in cases:
                with self.subTest(role=role, filters=filters):
                    result = self._catalog(user, filters)
                    got = {item['id'] for item in result['items']}
                    expected = set(self.Control.with_user(user).search(domain).ids)
                    self.assertEqual(got, expected)
                    self.assertEqual(result['total'], len(expected))

    def test_summary_counts_match_orm(self):
        analyst = self.users['analyst']
        result = self._catalog(analyst)
        by_theme = {row['key']: row['count'] for row in result['summary']['by_theme']}
        for key, count in by_theme.items():
            self.assertEqual(count, self.Control.with_user(analyst).search_count([('theme', '=', key)]))
        self.assertEqual(sum(by_theme.values()), CATALOG_SIZE)
        by_impl = {row['key']: row['count'] for row in result['summary']['by_implementation']}
        for key, count in by_impl.items():
            self.assertEqual(count, self.Control.with_user(analyst).search_count(
                [('implementation', '=', key)]))

    def test_theme_chip_counts_ignore_theme_filter(self):
        analyst = self.users['analyst']
        result = self._catalog(analyst, {'theme': 'organizational', 'selected': 'yes'})
        self.assertEqual(result['summary']['theme_all'], self.Control.with_user(analyst).search_count(
            [('selected', '=', True)]))
        self.assertEqual(result['summary']['matching'], self.Control.with_user(analyst).search_count(
            [('selected', '=', True), ('theme', '=', 'organizational')]))

    def test_invalid_filters_are_sanitized(self):
        result = self._catalog(self.users['analyst'], {
            'theme': 'x; drop table', 'selected': 'maybe', 'applicable': None,
            'implementation': 'bogus', 'owner_id': 'abc', 'limit': 99999,
            'search': 'a' * 500,
        })
        self.assertTrue(result['available'])
        filters = result['filters']
        self.assertEqual(filters['theme'], '')
        self.assertEqual(filters['selected'], 'all')
        self.assertEqual(filters['applicable'], 'all')
        self.assertEqual(filters['implementation'], 'all')
        self.assertEqual(filters['owner_id'], 0)
        self.assertEqual(filters['limit'], 200)
        self.assertEqual(len(filters['search']), 100)

    def test_plain_user_without_isms_role_is_denied(self):
        result = self._catalog(self.plain_user)
        self.assertFalse(result['available'])
        detail = self._detail(self.plain_user, self.ctrl)
        self.assertFalse(detail['available'])

    def test_unknown_or_malformed_control_id(self):
        analyst = self.users['analyst']
        for bad in ('abc', 987654321):
            with self.subTest(control_id=bad):
                result = self.explorer.with_user(analyst).get_control_detail(bad)
                self.assertFalse(result['available'])
                self.assertTrue(result['not_found'])

    # ------------------------------------------------------------------ linked records
    def test_linked_records_omit_unreadable_records(self):
        """Эзэмшигч admin-ийн эрсдэлийг харахгүй; тоонд ч оруулахгүй."""
        owner = self.users['owner']
        detail = self._detail(owner, self.ctrl)
        risks = detail['links']['risks']
        self.assertTrue(risks['available'])
        self.assertEqual(risks['ids'], [self.risk_visible.id])
        self.assertEqual(risks['count'], 1)
        self.assertNotIn(self.risk_hidden.id, risks['ids'])
        self.assertNotIn('FCE hidden risk', [r['name'] for r in risks['records']])

    def test_restricted_fields_are_not_returned_to_reporter(self):
        detail = self._detail(self.users['reporter'], self.ctrl)
        self.assertFalse(detail['justification']['readable'])
        self.assertIsNone(detail['justification']['value'])
        self.assertFalse(detail['evidence']['readable'])
        self.assertIsNone(detail['evidence']['value'])
        self.assertFalse(detail['odoo_implementation']['readable'])

    def test_reporter_sections_are_unavailable_where_orm_denies(self):
        detail = self._detail(self.users['reporter'], self.ctrl)
        links = detail['links']
        self.assertFalse(links['risks']['available'])
        self.assertFalse(links['assets']['available'])
        self.assertFalse(links['incidents']['available'])
        self.assertEqual(links['risks']['records'], [])
        self.assertEqual(links['incidents']['records'], [])
        self.assertTrue(links['policies']['available'])

    def test_parity_with_orm_per_role(self):
        """Холбоосын ID жагсаалт нь хэрэглэгчийн ORM-ийн уншиж чадах бичлэгтэй яг тэнцэнэ."""
        expected_visibility = {
            'reporter': {'risks': False, 'assets': False, 'incidents': False},
            'owner': {'risks': True, 'assets': True, 'incidents': False},
            'analyst': {'risks': True, 'assets': True, 'incidents': True},
            'auditor': {'risks': True, 'assets': True, 'incidents': True},
        }
        for role, user in self.users.items():
            with self.subTest(role=role):
                detail = self._detail(user, self.ctrl)
                links = detail['links']
                for key in ('risks', 'assets', 'incidents'):
                    self.assertEqual(links[key]['available'], expected_visibility[role][key], key)

                expected_policies = self.Policy.with_user(user).search(
                    [('control_ids', 'in', self.ctrl.ids)]).ids
                self.assertEqual(sorted(links['policies']['ids']), sorted(expected_policies))

                if links['risks']['available']:
                    expected_risks = self.Risk.with_user(user).search(
                        [('id', 'in', self.ctrl.sudo().risk_ids.ids)]).ids
                    self.assertEqual(sorted(links['risks']['ids']), sorted(expected_risks))
                if links['assets']['available']:
                    expected_assets = self.Asset.with_user(user).search(
                        [('id', 'in', self.ctrl.sudo().asset_ids.ids)]).ids
                    self.assertEqual(sorted(links['assets']['ids']), sorted(expected_assets))
                if links['incidents']['available']:
                    expected_incidents = self.Incident.with_user(user).search(
                        [('control_ids', 'in', self.ctrl.ids)]).ids
                    self.assertEqual(sorted(links['incidents']['ids']), sorted(expected_incidents))

    def test_policy_draft_hidden_from_reporter(self):
        reporter_ids = self._detail(self.users['reporter'], self.ctrl)['links']['policies']['ids']
        analyst_ids = self._detail(self.users['analyst'], self.ctrl)['links']['policies']['ids']
        self.assertEqual(reporter_ids, [self.policy_approved.id])
        self.assertEqual(set(analyst_ids), {self.policy_approved.id, self.policy_draft.id})

    def test_next_review_is_read_from_policy_not_invented(self):
        analyst = self.users['analyst']
        detail = self._detail(analyst, self.ctrl)
        self.assertFalse(detail['next_review']['control_field'])
        self.assertEqual(detail['next_review']['earliest'], '2020-01-01')
        other = self._detail(analyst, self.ctrl_other)
        self.assertFalse(other['next_review']['earliest'])

    # ------------------------------------------------------------------ findings
    def test_computed_findings_match_data(self):
        ctrl = self.ctrl_other
        ctrl.write({
            'selected': True, 'applicable': True, 'implementation': 'no',
            'justification': False, 'evidence': False, 'responsible_id': False,
        })
        ctrl.write({'risk_ids': [(5, 0, 0)]})
        findings = self._findings(self.explorer.get_control_detail(ctrl.id))

        self.assertEqual(findings['selected_implementation']['status'], 'gap')
        self.assertEqual(findings['selected_implementation']['severity'], 'danger')
        self.assertEqual(findings['selected_justification']['status'], 'gap')
        self.assertEqual(findings['selected_evidence']['status'], 'gap')
        self.assertEqual(findings['selected_risk']['status'], 'gap')
        self.assertEqual(findings['owner']['status'], 'gap')
        self.assertEqual(findings['applicability_consistent']['status'], 'ok')
        self.assertEqual(findings['not_applicable_justification']['status'], 'na')
        self.assertEqual(findings['implemented_not_selected']['status'], 'na')
        self.assertEqual(findings['policy_review']['status'], 'na')
        summary = self.explorer.get_control_detail(ctrl.id)['findings_summary']
        self.assertEqual(summary, {'gap': 5, 'ok': 1, 'na': 3, 'not_evaluated': 0})

        # Бүх зүйл бөглөгдсөн: саад байхгүй
        risk = self.Risk.create({'name': 'FCE other risk', 'control_ids': [(6, 0, ctrl.ids)]})
        ctrl.write({
            'implementation': 'yes', 'justification': 'Үндэслэл', 'evidence': 'Нотолгоо',
            'responsible_id': self.admin.id,
        })
        detail = self.explorer.get_control_detail(ctrl.id)
        self.assertEqual(detail['findings_summary']['gap'], 0)
        self.assertEqual(self._findings(detail)['selected_risk']['status'], 'ok')
        self.assertTrue(risk.exists())

        # Хамааралгүй гэж тэмдэглэсэн боловч сонгосон: зөрчил
        ctrl.write({'applicable': False})
        findings = self._findings(self.explorer.get_control_detail(ctrl.id))
        self.assertEqual(findings['applicability_consistent']['status'], 'gap')
        self.assertEqual(findings['not_applicable_justification']['status'], 'ok')

        # Хэрэгжсэн боловч сонгоогүй: мэдээллийн түвшний саад
        ctrl.write({'selected': False, 'applicable': True, 'implementation': 'yes'})
        findings = self._findings(self.explorer.get_control_detail(ctrl.id))
        self.assertEqual(findings['implemented_not_selected']['status'], 'gap')
        self.assertEqual(findings['implemented_not_selected']['severity'], 'info')
        self.assertEqual(findings['selected_implementation']['status'], 'na')

    def test_findings_marked_not_evaluated_for_restricted_user(self):
        ctrl = self.ctrl_other
        ctrl.write({'selected': True, 'applicable': True, 'implementation': 'yes',
                    'justification': 'Үндэслэл', 'evidence': 'Нотолгоо',
                    'responsible_id': self.admin.id})
        detail = self.explorer.with_user(self.users['reporter']).get_control_detail(ctrl.id)
        findings = self._findings(detail)
        self.assertEqual(findings['selected_justification']['status'], 'not_evaluated')
        self.assertEqual(findings['selected_evidence']['status'], 'not_evaluated')
        self.assertEqual(findings['selected_risk']['status'], 'not_evaluated')
        self.assertEqual(findings['selected_implementation']['status'], 'ok')
        self.assertEqual(findings['owner']['status'], 'ok')

    def test_findings_do_not_call_hidden_risk_a_gap(self):
        """Эзэмшигч уншиж чадахгүй эрсдэлтэй үед «эрсдэлгүй» гэж буруу дүгнэхгүй."""
        owner = self.users['owner']
        self.ctrl.write({'selected': True})
        self.assertEqual(self._findings(self._detail(owner, self.ctrl))['selected_risk']['status'],
                         'ok')

        # Зөвхөн admin-ий эрсдэл холбогдсон хяналт: owner-д gap биш, шалгах боломжгүй
        self.Risk.create({'name': 'FCE hidden only', 'owner_id': self.admin.id,
                          'control_ids': [(6, 0, self.ctrl_other.ids)]})
        self.ctrl_other.write({'selected': True, 'implementation': 'yes'})
        findings = self._findings(self._detail(owner, self.ctrl_other))
        self.assertEqual(findings['selected_risk']['status'], 'not_evaluated')
        self.assertNotIn('admin', findings['selected_risk']['detail'].lower())

    def test_disclaimer_is_present(self):
        detail = self._detail(self.users['analyst'], self.ctrl)
        self.assertIn('аудитын дүгнэлт биш', detail['disclaimer'])
