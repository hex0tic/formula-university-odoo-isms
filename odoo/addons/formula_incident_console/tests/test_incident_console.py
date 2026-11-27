"""Formula Incident Console: серверийн эрх, SLA, шилжилт, idempotency, asset bundle.

Бүх бичлэгийг superuser-ээр үүсгэж, үйлдлийг ``with_user()``-ээр бодит хэрэглэгчээр хийнэ.
Консолын хариу нь ORM-ийн тоологтой тэнцэх ёстой (parity).
"""
from datetime import timedelta
from secrets import token_urlsafe
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

ISMS_ASSET_VALS = {'classification': 'confidential', 'confidentiality': '3',
                   'integrity': '3', 'availability': '3'}
STATES = ('incident', 'report', 'investigate', 'resolve', 'close')


@tagged('post_install', '-at_install', 'formula_incident_console')
class TestIncidentConsole(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        def test_user(**values):
            return new_test_user(env, password=token_urlsafe(24), **values)

        cls.reporter = test_user(login='fic_reporter',
                                     groups='base.group_user,university_isms.group_isms_reporter')
        cls.reporter_other = test_user(login='fic_reporter_other',
                                           groups='base.group_user,university_isms.group_isms_reporter')
        cls.analyst = test_user(login='fic_analyst',
                                    groups='base.group_user,university_isms.group_isms_analyst')
        cls.auditor = test_user(login='fic_auditor',
                                    groups='base.group_user,university_isms.group_isms_auditor')
        cls.manager = test_user(login='fic_manager',
                                    groups='base.group_user,university_isms.group_isms_manager')
        cls.plain = test_user(login='fic_plain', groups='base.group_user')
        cls.console = env['formula.incident.console']
        cls.Incident = env['isms.incident']

        cls.asset = env['isms.asset'].create(dict(ISMS_ASSET_VALS, name='FIC test asset',
                                                  owner_id=cls.analyst.id))

    # ------------------------------------------------------------ helpers
    def _incident(self, state='incident', reporter=None, severity='medium', detected_days=0, **vals):
        """Бичлэг үүсгээд шаардлагатай үе шат хүртэл зөв эрхтэй хэрэглэгчээр урагшлуулна."""
        reporter = reporter or self.reporter
        rec = self.Incident.create(dict({
            'name': 'FIC %s %s' % (state, severity),
            'category': 'phishing',
            'severity': severity,
            'reporter_id': reporter.id,
            'detected_at': fields.Datetime.now() - timedelta(days=detected_days),
        }, **vals))
        self._commit()
        if state == 'incident':
            return rec
        rec.with_user(reporter).action_report()
        if state == 'report':
            return rec
        rec.with_user(self.analyst).action_investigate()
        if state == 'investigate':
            return rec
        rec.with_user(self.analyst).write({'root_cause': 'Тест шалтгаан', 'resolution': 'Тест шийдэл'})
        if state == 'resolve' or state == 'close':
            rec.with_user(self.analyst).action_resolve()
        if state == 'close':
            rec.with_user(self.manager).write({'lessons_learned': 'Тест сургамж'})
            rec.with_user(self.manager).action_close()
        return rec

    def _commit(self):
        """Транзакцийн commit-ийг дуурайна: ORM flush + mail tracking precommit (Odoo mail тестийн загвар).
        Шинээр үүсгэсэн бичлэгийн дараах өөрчлөлтийг commit-оос өмнө tracking хийдэггүй тул үүнийг заавал хийнэ."""
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _visible_ids(self, user):
        """ORM-ийн харагдах бичлэгүүд (эталон)."""
        return set(self.Incident.with_user(user).search([]).ids)

    def _row_ids(self, user, filters=None):
        data = self.console.with_user(user).get_incident_rows(filters or {})
        return {row['id'] for row in data['rows']}

    def _attempt(self, user, rec, action):
        """Метод бодитоор гүйцэтгэх; DB-г rollback хийж үр дүнг буцаана (ok / access / user)."""
        savepoint = self.env.cr.savepoint()
        try:
            getattr(rec.with_user(user), action)()
            outcome = 'ok'
        except AccessError:
            outcome = 'access'
        except UserError:
            outcome = 'user'
        finally:
            savepoint.close(rollback=True)
            self.env.invalidate_all()
        return outcome

    # ------------------------------------------------------------ visibility parity
    def test_reporter_list_matches_orm_and_excludes_others(self):
        own = self._incident(reporter=self.reporter)
        other = self._incident(reporter=self.reporter_other)
        ids = self._row_ids(self.reporter)
        self.assertEqual(ids, self._visible_ids(self.reporter))
        self.assertIn(own.id, ids)
        self.assertNotIn(other.id, ids)

    def test_analyst_manager_auditor_list_matches_orm(self):
        self._incident(reporter=self.reporter)
        self._incident(reporter=self.reporter_other, state='investigate')
        self._incident(reporter=self.reporter_other, state='close')
        for user in (self.analyst, self.manager, self.auditor):
            with self.subTest(user=user.login):
                self.assertEqual(self._row_ids(user), self._visible_ids(user))
        self.assertEqual(self._row_ids(self.analyst), self._row_ids(self.manager))

    def test_reporter_cannot_read_other_incident_through_service(self):
        other = self._incident(reporter=self.reporter_other)
        with self.assertRaises(AccessError):
            self.console.with_user(self.reporter).get_incident_detail(other.id)
        own = self._incident(reporter=self.reporter)
        self.assertEqual(self.console.with_user(self.reporter).get_incident_detail(own.id)['row']['id'], own.id)

    def test_plain_user_without_isms_access_is_denied(self):
        self._incident()
        with self.assertRaises(AccessError):
            self.console.with_user(self.plain).get_incident_rows({})

    def test_investigation_and_assets_hidden_from_reporter(self):
        rec = self._incident(reporter=self.reporter, state='investigate', asset_ids=[(6, 0, self.asset.ids)])
        rec.with_user(self.analyst).write({'asset_ids': [(6, 0, self.asset.ids)]})
        reporter_detail = self.console.with_user(self.reporter).get_incident_detail(rec.id)
        self.assertFalse(reporter_detail['investigation_visible'])
        self.assertIsNone(reporter_detail['investigation'])
        self.assertFalse(reporter_detail['assets']['available'])
        self.assertFalse(reporter_detail['can_edit_investigation'])
        analyst_detail = self.console.with_user(self.analyst).get_incident_detail(rec.id)
        self.assertTrue(analyst_detail['investigation_visible'])
        self.assertTrue(analyst_detail['can_edit_investigation'])
        self.assertTrue(analyst_detail['assets']['available'])
        self.assertEqual([a['id'] for a in analyst_detail['assets']['items']], self.asset.ids)

    # ------------------------------------------------------------ transitions
    def test_allowed_transitions_match_server_behaviour(self):
        users = {'reporter': self.reporter, 'analyst': self.analyst,
                 'manager': self.manager, 'auditor': self.auditor}
        for state in STATES:
            for login, user in users.items():
                with self.subTest(state=state, user=login):
                    rec = self._incident(state=state, reporter=self.reporter)
                    detail = self.console.with_user(user).get_incident_detail(rec.id)
                    for spec in detail['transitions']:
                        outcome = self._attempt(user, rec, spec['action'])
                        if spec['allowed']:
                            self.assertEqual(outcome, 'ok', spec)
                        else:
                            self.assertIn(outcome, ('access', 'user'), spec)
                            self.assertTrue(spec['reason'], spec)

    def test_analyst_cannot_close_manager_can(self):
        rec = self._incident(state='resolve')
        rec.with_user(self.analyst).write({'lessons_learned': 'Тест сургамж'})
        with self.assertRaises(AccessError):
            rec.with_user(self.analyst).action_close()
        self.assertEqual(rec.state, 'resolve')
        analyst_actions = {t['action']: t for t in
                           self.console.with_user(self.analyst).get_incident_detail(rec.id)['transitions']}
        self.assertFalse(analyst_actions['action_close']['allowed'])
        self.assertTrue(analyst_actions['action_close']['reason'])
        manager_actions = {t['action']: t for t in
                           self.console.with_user(self.manager).get_incident_detail(rec.id)['transitions']}
        self.assertTrue(manager_actions['action_close']['allowed'])
        rec.with_user(self.manager).action_close()
        self.assertEqual(rec.state, 'close')

    def test_reporter_cannot_investigate_or_close(self):
        rec = self._incident(reporter=self.reporter, state='report')
        with self.assertRaises(AccessError):
            rec.with_user(self.reporter).action_investigate()
        self.assertEqual(rec.state, 'report')

    def test_invalid_transition_rejected_by_server(self):
        rec = self._incident(state='incident')
        with self.assertRaises(UserError):
            rec.with_user(self.manager).write({'state': 'close'})
        self.assertEqual(rec.state, 'incident')
        rec_report = self._incident(state='report')
        with self.assertRaises(UserError):
            rec_report.with_user(self.analyst).write({'state': 'resolve'})
        self.assertEqual(rec_report.state, 'report')

    def test_resolve_requires_content_and_console_reports_it(self):
        rec = self._incident(state='investigate')
        detail = self.console.with_user(self.analyst).get_incident_detail(rec.id)
        resolve = next(t for t in detail['transitions'] if t['action'] == 'action_resolve')
        self.assertFalse(resolve['allowed'])
        self.assertIn('Үндсэн шалтгаан', resolve['reason'])
        self.assertEqual(self._attempt(self.analyst, rec, 'action_resolve'), 'user')

    def test_double_transition_is_idempotent(self):
        rec = self._incident(state='report')
        rec.with_user(self.analyst).action_investigate()
        first_stamp = rec.investigation_at
        self.assertTrue(first_stamp)
        rec.with_user(self.analyst).action_investigate()
        self.assertEqual(rec.state, 'investigate')
        self.assertEqual(rec.investigation_at, first_stamp)
        self.assertEqual(self._attempt(self.analyst, rec, 'action_investigate'), 'ok')
        self.assertEqual(rec.state, 'investigate')

    def test_save_investigation_only_accepts_note_fields(self):
        rec = self._incident(state='investigate')
        with self.assertRaises(UserError):
            self.console.with_user(self.analyst).save_investigation(rec.id, {'state': 'close'})
        self.assertEqual(rec.state, 'investigate')
        detail = self.console.with_user(self.analyst).save_investigation(rec.id, {'containment': 'Тусгаарласан'})
        self.assertEqual(detail['investigation']['containment'], 'Тусгаарласан')

    def test_reporter_cannot_save_investigation(self):
        rec = self._incident(reporter=self.reporter)
        with self.assertRaises(AccessError):
            self.console.with_user(self.reporter).save_investigation(rec.id, {'root_cause': 'x'})

    def test_timeline_records_state_tracking_for_reporter_and_analyst(self):
        rec = self._incident(reporter=self.reporter, state='investigate')
        self._commit()
        for user in (self.reporter, self.analyst):
            with self.subTest(user=user.login):
                timeline = self.console.with_user(user).get_incident_detail(rec.id)['timeline']
                self.assertTrue(timeline, 'timeline empty for %s' % user.login)
                changed = [tr for entry in timeline for tr in entry['tracking']]
                self.assertTrue(any(tr['new'] for tr in changed), timeline)

    def test_audit_only_for_auditor(self):
        rec = self._incident(state='report')
        self.assertFalse(self.console.with_user(self.analyst).get_incident_detail(rec.id)['audit']['available'])
        self.assertTrue(self.console.with_user(self.auditor).get_incident_detail(rec.id)['audit']['available'])

    # ------------------------------------------------------------ SLA and list
    def test_sla_overdue_flags_and_urgency_order(self):
        overdue = self._incident(severity='high', detected_days=10, reporter=self.reporter_other)
        on_track = self._incident(severity='low', reporter=self.reporter_other)
        closed = self._incident(state='close', severity='critical', detected_days=200,
                                reporter=self.reporter_other)
        data = self.console.with_user(self.analyst).get_incident_rows({})
        rows = {row['id']: row for row in data['rows']}
        self.assertTrue(rows[overdue.id]['sla_overdue'])
        self.assertLess(rows[overdue.id]['sla_remaining_seconds'], 0)
        self.assertFalse(rows[on_track.id]['sla_overdue'])
        self.assertGreater(rows[on_track.id]['sla_remaining_seconds'], 0)
        self.assertIsNone(rows[closed.id]['sla_remaining_seconds'])
        self.assertFalse(rows[closed.id]['sla_overdue'])
        ordered = [row['id'] for row in data['rows']]
        self.assertLess(ordered.index(overdue.id), ordered.index(on_track.id))
        self.assertLess(ordered.index(on_track.id), ordered.index(closed.id))

    def test_overdue_and_state_filters(self):
        overdue = self._incident(severity='high', detected_days=10, reporter=self.reporter_other)
        on_track = self._incident(severity='low', reporter=self.reporter_other)
        reported = self._incident(state='report', reporter=self.reporter_other)
        fixtures = {overdue.id, on_track.id, reported.id}
        ids = self._row_ids(self.analyst, {'overdue': True})
        self.assertEqual(ids & fixtures, {overdue.id})
        self.assertEqual(self._row_ids(self.analyst, {'state': 'report'}) & fixtures, {reported.id})

    def test_mine_filter_uses_reporter_and_assignee(self):
        own = self._incident(reporter=self.reporter)
        self._incident(reporter=self.reporter_other)
        self.assertEqual(self._row_ids(self.reporter, {'mine': True}), {own.id})

    def test_invalid_filter_values_are_ignored(self):
        self._incident()
        self._incident(reporter=self.reporter_other)
        everything = self._row_ids(self.analyst)
        self.assertEqual(self._row_ids(self.analyst, {'state': 'bogus', 'severity': '<script>'}), everything)

    def test_search_and_queue_totals_follow_visibility(self):
        own = self._incident(name='Сүлжээ 50% доголдол', detected_days=10)
        self._incident(reporter=self.reporter_other, name='Сүлжээ 50% бусад', detected_days=10)
        self._incident(name='Сүлжээ 500 хэвийн', assignee_id=self.analyst.id)
        self.assertEqual(self._row_ids(self.reporter, {'query': '50%'}), {own.id})
        self.assertEqual(self._row_ids(self.reporter, {'query': own.code, 'unassigned': True}), {own.id})
        data = self.console.with_user(self.reporter).get_incident_rows({'query': own.code})
        self.assertEqual(data['total'], 1)
        Incident = self.Incident.with_user(self.reporter)
        active = [('state', 'in', ['incident', 'report', 'investigate'])]
        self.assertEqual(data['summary']['all'], Incident.search_count([]))
        self.assertEqual(data['summary']['open'], Incident.search_count(active))
        self.assertEqual(data['summary']['overdue'], Incident.search_count(active + [
            ('sla_deadline', '<', fields.Datetime.now())]))
        self.assertEqual(data['summary']['unassigned'], Incident.search_count(active + [
            ('assignee_id', '=', False)]))

    def test_older_closed_incidents_cannot_crowd_out_the_active_queue(self):
        self._incident(state='close', detected_days=200, name='Queue priority closed')
        active = self._incident(name='Queue priority active')
        with patch('odoo.addons.formula_incident_console.models.incident_console.LIST_LIMIT', 1):
            data = self.console.with_user(self.analyst).get_incident_rows({'query': 'Queue priority'})
        self.assertEqual([r['id'] for r in data['rows']], [active.id])
        self.assertEqual(data['total'], 2)
        self.assertTrue(data['truncated'])

    def test_helpdesk_ticket_absent_is_none(self):
        rec = self._incident(reporter=self.reporter)
        detail = self.console.with_user(self.reporter).get_incident_detail(rec.id)
        if 'helpdesk.ticket' in self.env.registry:
            self.skipTest('helpdesk addon present: ticket visibility parity covered by university_isms_helpdesk tests')
        self.assertIsNone(detail['ticket'])

    # ------------------------------------------------------------ frontend bundle
    def test_backend_asset_bundle_compiles_without_css_errors(self):
        """SCSS ошгүй эсэхийг үнэхээр компайлдаж шалгана (css_errors хоосон байх ёстой)."""
        bundle = self.env['ir.qweb']._get_asset_bundle(
            'web.assets_backend', css=True, js=False,
            assets_params=self.env['ir.asset']._get_asset_params())
        css = bundle.preprocess_css()
        self.assertFalse(bundle.css_errors, bundle.css_errors)
        self.assertNotIn('A css error occured', css)
        self.assertIn('o_formula_incident_console', css)
