"""Formula Command Center: KPI ба heatmap нь хэрэглэгчийн ORM эрхтэй тэнцэх эсэх (DASH-08).

Бүх тест өөрийн бичлэгээ үүсгэнэ (seed өгөгдөлд найдахгүй). Тоо бүр тухайн хэрэглэгчийн
``with_user()``-ээр бодсон ``search_count``-тай харьцуулагдана.
"""
import json
from datetime import timedelta

from odoo import fields
from odoo.addons.university_isms.models.risk import matrix_level
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

ROLE_GROUPS = {
    'analyst': 'university_isms.group_isms_analyst',
    'auditor': 'university_isms.group_isms_auditor',
    'reporter': 'university_isms.group_isms_reporter',
    'manager': 'university_isms.group_isms_manager',
    'owner': 'university_isms.group_isms_asset_owner',
}
AUDIT_ITEM_KEYS = {'id', 'timestamp', 'action', 'action_label', 'model', 'model_name'}


@tagged('post_install', '-at_install', 'formula_command_center')
class TestCommandCenter(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.users = {
            role: new_test_user(env, login='fcc_%s' % role, groups=group)
            for role, group in ROLE_GROUPS.items()
        }
        cls.plain_user = new_test_user(env, login='fcc_plain', groups='base.group_user')
        # Энэ мэдээлэгч ямар ч инцидент мэдээлээгүй: шүүлтүүрийн дараа хоосон өгөгдөл
        cls.fresh_reporter = new_test_user(env, login='fcc_fresh_reporter',
                                           groups=ROLE_GROUPS['reporter'])
        cls.center = env['formula.command.center']

        Asset = env['isms.asset']
        Risk = env['isms.risk']
        Incident = env['isms.incident']
        Policy = env['isms.policy']
        Task = env['project.task']
        now = fields.Datetime.now()

        owner = cls.users['owner']
        cls.asset_owned = Asset.create({'name': 'FCC owned asset', 'owner_id': owner.id,
                                        'classification': 'confidential', 'confidentiality': '3',
                                        'integrity': '3', 'availability': '3'})
        cls.asset_other = Asset.create({'name': 'FCC other asset', 'owner_id': env.ref('base.user_admin').id,
                                        'classification': 'public', 'confidentiality': '1',
                                        'integrity': '1', 'availability': '1'})

        # Эрсдэл: өөр өөр магадлал/нөлөөлөл, нэг нь батлагдсан хүлээн зөвшөөрөлттэй, нэг нь үлдэгдэлтэй
        cls.risk_high = Risk.create({'name': 'FCC high risk', 'likelihood': '5', 'impact': '5',
                                     'asset_ids': [(6, 0, cls.asset_owned.ids)],
                                     'residual_likelihood': '4', 'residual_impact': '4'})
        cls.risk_low = Risk.create({'name': 'FCC low risk', 'likelihood': '1', 'impact': '1',
                                    'treatment': 'accept', 'accepted_by_id': owner.id,
                                    'asset_ids': [(6, 0, cls.asset_other.ids)]})
        cls.risk_mid = Risk.create({'name': 'FCC mid risk', 'likelihood': '3', 'impact': '4',
                                    'asset_ids': [(6, 0, cls.asset_other.ids)],
                                    'residual_likelihood': '2', 'residual_impact': '2'})
        cls.risk_mid2 = Risk.create({'name': 'FCC mid risk 2', 'likelihood': '3', 'impact': '4',
                                     'asset_ids': [(6, 0, cls.asset_other.ids)]})

        # Хяналт: сонгосон хэдэн хяналтын хэрэгжилт
        controls = env['isms.control'].search([], limit=3)
        cls.selected_controls = controls
        if controls:
            controls[0].write({'selected': True, 'implementation': 'yes'})
        if len(controls) > 1:
            controls[1].write({'selected': True, 'implementation': 'partial'})

        # Инцидент: SLA хэтэрсэн (өндөр, 10 хоногийн өмнөх), SLA-д буй (бага), хаагдсан
        cls.incident_overdue = Incident.create({
            'name': 'FCC overdue incident', 'severity': 'high', 'category': 'phishing',
            'detected_at': now - timedelta(days=10), 'reporter_id': cls.users['analyst'].id,
            'asset_ids': [(6, 0, cls.asset_owned.ids)]})
        cls.incident_on_track = Incident.create({
            'name': 'FCC on track incident', 'severity': 'low', 'category': 'phishing',
            'detected_at': now, 'reporter_id': cls.users['reporter'].id})
        cls.incident_closed = Incident.create({
            'name': 'FCC closed incident', 'severity': 'medium', 'category': 'phishing',
            'detected_at': now - timedelta(days=200), 'state': 'close', 'closed_at': now,
            'reporter_id': cls.users['reporter'].id})

        # Бодлого: батлагдсан (хугацаа хэтэрсэн), батлагдсан (хугацаандаа), ноорог
        cls.policy_overdue = Policy.create({'name': 'FCC overdue policy', 'state': 'approved',
                                            'next_review_date': fields.Date.today() - timedelta(days=5)})
        cls.policy_current = Policy.create({'name': 'FCC current policy', 'state': 'approved',
                                            'next_review_date': fields.Date.today() + timedelta(days=300)})
        cls.policy_draft = Policy.create({'name': 'FCC draft policy', 'state': 'draft'})

        # Эрсдэлийн хариу арга хэмжээний даалгавар (хугацаа хэтэрсэн нэг)
        project = env.ref('university_isms.project_risk_treatment')
        cls.task_overdue = Task.create({'name': 'FCC overdue treatment', 'project_id': project.id,
                                        'isms_risk_id': cls.risk_high.id,
                                        'date_deadline': fields.Date.today() - timedelta(days=3)})
        cls.task_open = Task.create({'name': 'FCC open treatment', 'project_id': project.id,
                                     'isms_risk_id': cls.risk_mid.id})

    # ------------------------------------------------------------ helpers
    def _dash(self, user, filters=None):
        return self.center.with_user(user).get_dashboard_data(filters or {})

    def _count(self, user, model, domain):
        """Тоо; хэрэглэгч уншиж чадахгүй бол None (KPI нь «хандах эрхгүй» байх ёстой)."""
        if not self.env[model].with_user(user).has_access('read'):
            return None
        return self.env[model].with_user(user).search_count(domain)

    def _kpi(self, dash, key):
        return next(card for card in dash['kpis'] if card['key'] == key)

    def _expected_kpis(self, user):
        """Тухайн хэрэглэгчийн ORM-ээр бодсон gold утгууд (үйлчилгээний код ашиглахгүй)."""
        today = fields.Date.today()
        ex = {}
        ex['assets_total'] = self._count(user, 'isms.asset', [])
        ex['assets_high_risk'] = self._count(user, 'isms.asset', [('risk_level', '=', 'high')])
        ex['risks_total'] = self._count(user, 'isms.risk', [])
        ex['risks_high'] = self._count(user, 'isms.risk', [('level', '=', 'high')])
        ex['risks_open'] = self._count(user, 'isms.risk', [('accepted_by_id', '=', False)])
        ex['risks_accepted'] = self._count(user, 'isms.risk', [('treatment', '=', 'accept'),
                                                               ('accepted_by_id', '!=', False)])
        ex['controls_selected'] = self._count(user, 'isms.control', [('selected', '=', True)])
        ex['controls_implemented'] = self._count(user, 'isms.control', [('selected', '=', True),
                                                                        ('implementation', '=', 'yes')])
        ex['incidents_open'] = self._count(user, 'isms.incident', [('state', '!=', 'close')])
        ex['incidents_sla_overdue'] = self._count(user, 'isms.incident', [
            ('state', 'in', ['incident', 'report', 'investigate']), ('sla_status', '=', 'breached')])
        ex['policies_approved'] = self._count(user, 'isms.policy', [('state', '=', 'approved')])
        ex['policies_review_overdue'] = self._count(user, 'isms.policy', [
            ('state', '=', 'approved'), ('next_review_date', '<', fields.Date.to_string(today))])
        treatment_ok = self._count(user, 'isms.risk', []) is not None
        ex['treatment_open'] = self._count(user, 'project.task', [
            ('isms_risk_id', '!=', False), ('is_closed', '=', False)]) if treatment_ok else None
        ex['treatment_overdue'] = self._count(user, 'project.task', [
            ('isms_risk_id', '!=', False), ('is_closed', '=', False),
            ('date_deadline', '<', fields.Date.to_string(today))]) if treatment_ok else None
        return ex

    # ------------------------------------------------------------ tests
    def test_kpis_match_orm_counts_per_role(self):
        """Analyst, auditor, reporter, manager (+ asset owner): KPI = тухайн хэрэглэгчийн search_count."""
        for role in ('analyst', 'auditor', 'reporter', 'manager', 'owner'):
            user = self.users[role]
            with self.subTest(role=role):
                dash = self._dash(user)
                expected = self._expected_kpis(user)
                for key, value in expected.items():
                    card = self._kpi(dash, key)
                    if value is None:
                        self.assertFalse(card['available'], '%s / %s' % (role, key))
                        self.assertIsNone(card['value'], '%s / %s' % (role, key))
                    else:
                        self.assertTrue(card['available'], '%s / %s' % (role, key))
                        self.assertEqual(card['value'], value, '%s / %s' % (role, key))

    def test_reporter_is_restricted(self):
        """Мэдээлэгч: эрсдэл, heatmap, хөрөнгө, аудит лог хандахгүй; тоо гаргахгүй."""
        dash = self._dash(self.users['reporter'])
        sections = dash['sections']
        for name in ('risks', 'heatmap', 'assets', 'audit', 'treatment'):
            with self.subTest(section=name):
                self.assertFalse(sections[name]['available'])
                self.assertNotIn('total', sections[name])
                self.assertNotIn('cells', sections[name])
        for key in ('assets_total', 'risks_total', 'risks_high', 'risks_open', 'risks_accepted',
                    'assets_high_risk', 'treatment_open'):
            card = self._kpi(dash, key)
            self.assertFalse(card['available'], key)
            self.assertIsNone(card['value'], key)
            self.assertIsNone(card['drill'], key)
        # Өөрийн мэдээлсэн инцидент л тоологдоно (инцидентийн record rule)
        self.assertEqual(self._kpi(dash, 'incidents_open')['value'],
                         self._count(self.users['reporter'], 'isms.incident', [('state', '!=', 'close')]))

    def test_analyst_has_no_audit_access(self):
        dash = self._dash(self.users['analyst'])
        self.assertFalse(dash['sections']['audit']['available'])
        self.assertTrue(dash['sections']['risks']['available'])

    def test_auditor_audit_activity_is_safe(self):
        dash = self._dash(self.users['auditor'])
        audit = dash['sections']['audit']
        self.assertTrue(audit['available'])
        self.assertLessEqual(len(audit['recent']), 10)
        self.assertGreater(len(audit['recent']), 0)
        for item in audit['recent']:
            self.assertEqual(set(item.keys()), AUDIT_ITEM_KEYS)
        self.assertEqual(audit['total'], self._count(self.users['auditor'], 'isms.audit.log', []))

    def test_heatmap_cells_match_orm(self):
        """Анхдагч ба үлдэгдэл heatmap: нүд бүрийн тоо = тухайн эрхээр бодсон ORM тоо."""
        for role in ('manager', 'analyst', 'owner'):
            user = self.users[role]
            heat = self._dash(user)['sections']['heatmap']
            self.assertTrue(heat['available'], role)
            for mode, lfield, ifield in (('inherent', 'likelihood', 'impact'),
                                         ('residual', 'residual_likelihood', 'residual_impact')):
                cells = heat[mode]['cells']
                self.assertEqual(len(cells), 25)
                for cell in cells:
                    with self.subTest(role=role, mode=mode, cell=(cell['likelihood'], cell['impact'])):
                        expected = self._count(user, 'isms.risk', [
                            (lfield, '=', cell['likelihood']), (ifield, '=', cell['impact'])])
                        self.assertEqual(cell['count'], expected)
                        self.assertEqual(cell['level'], matrix_level(cell['likelihood'], cell['impact']))
                        self.assertEqual(cell['score'], int(cell['likelihood']) * int(cell['impact']))
                        self.assertEqual(cell['drill']['model'], 'isms.risk')
                        self.assertEqual(
                            self._count(user, 'isms.risk', cell['drill']['domain']), cell['count'])

    def test_drill_domains_return_kpi_counts(self):
        """KPI drill-down domain нь KPI утгатай тэнцүү тооны бичлэг буцаана."""
        for role in ('analyst', 'auditor', 'manager', 'reporter'):
            user = self.users[role]
            dash = self._dash(user)
            for card in dash['kpis']:
                if not card['available']:
                    continue
                with self.subTest(role=role, key=card['key']):
                    self.assertIsNotNone(card['drill'])
                    self.assertEqual(
                        self._count(user, card['drill']['model'], card['drill']['domain']), card['value'])

    def test_output_is_json_safe_and_filters_sanitized(self):
        user = self.users['manager']
        dash = self._dash(user, {'incident_days': 30})
        json.dumps(dash)
        self.assertEqual(dash['filters'], {'incident_days': 30})
        self.assertEqual(self._dash(user, {'incident_days': 7})['filters'], {'incident_days': 0})
        self.assertEqual(self._dash(user, {'incident_days': 'abc'})['filters'], {'incident_days': 0})
        self.assertEqual(self._dash(user, None)['filters'], {'incident_days': 0})

    def test_incident_period_filter_limits_incident_kpis(self):
        user = self.users['manager']
        dash = self._dash(user, {'incident_days': 30})
        cutoff = fields.Datetime.to_string(fields.Datetime.now() - timedelta(days=30))
        expected_open = self._count(user, 'isms.incident', [('state', '!=', 'close'),
                                                            ('detected_at', '>=', cutoff)])
        self.assertEqual(self._kpi(dash, 'incidents_open')['value'], expected_open)
        # 10 хоногийн өмнөх incident 30 хоногийн шүүлтүүрт багтана
        self.assertGreaterEqual(expected_open, 2)

    def test_empty_visibility_is_safe(self):
        """Өгөгдөл байхгүй/хоосон харагдах хэрэглэгч: алдаагүй, тэг утга, JSON-safe."""
        dash = self._dash(self.fresh_reporter)
        incidents = dash['sections']['incidents']
        self.assertTrue(incidents['available'])
        self.assertEqual(incidents['open'], 0)
        self.assertEqual(incidents['sla_overdue'], 0)
        self.assertEqual(incidents['sla_on_track'], 0)
        self.assertTrue(all(row['count'] == 0 for row in incidents['by_state']))
        self.assertTrue(all(row['count'] == 0 for row in incidents['open_by_severity']))
        self.assertEqual(len(dash['kpis']), 14)
        json.dumps(dash)

        plain = self._dash(self.plain_user)
        self.assertEqual(len(plain['kpis']), 14)
        for section in ('assets', 'risks', 'heatmap', 'audit', 'incidents', 'policies'):
            self.assertFalse(plain['sections'][section]['available'], section)
        json.dumps(plain)

    def test_dashboard_is_read_only_and_uses_user_rights(self):
        """Dashboard нь ORM-д бичихгүй; хэрэглэгчийн эрхээр унших боломжтой эсэхийг шалгана."""
        with self.assertRaises(AccessError):
            self.env['isms.risk'].with_user(self.users['reporter']).check_access('write')
        before = self.env['isms.risk'].search_count([])
        self._dash(self.users['manager'])
        self.assertEqual(self.env['isms.risk'].search_count([]), before)
