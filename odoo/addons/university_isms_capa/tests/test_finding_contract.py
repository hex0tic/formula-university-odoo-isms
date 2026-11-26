from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install', 'university_isms_capa')
class TestFindingContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analyst = new_test_user(cls.env, 't_fnd_analyst', groups='university_isms.group_isms_analyst')
        cls.reporter = new_test_user(cls.env, 't_fnd_reporter', groups='university_isms.group_isms_reporter')

    def test_upsert_deduplicates_open_findings(self):
        Finding = self.env['isms.finding'].with_user(self.analyst)
        first, created = Finding._upsert_from_source('monitoring', 'check:x', {'name': 'X', 'severity': 'high'})
        self.assertTrue(created)
        self.assertTrue(first.code.startswith('FND-'))
        again, created = Finding._upsert_from_source('monitoring', 'check:x', {'name': 'X'})
        self.assertFalse(created)
        self.assertEqual(again, first)
        self.assertEqual(first.occurrence_count, 2)

    def test_closed_finding_allows_new_one(self):
        Finding = self.env['isms.finding']
        first, _ = Finding._upsert_from_source('monitoring', 'check:y', {'name': 'Y'})
        first.sudo().state = 'closed'
        second, created = Finding._upsert_from_source('monitoring', 'check:y', {'name': 'Y'})
        self.assertTrue(created)
        self.assertNotEqual(first, second)

    def test_reporter_cannot_read_findings(self):
        with self.assertRaises(AccessError):
            self.env['isms.finding'].with_user(self.reporter).search([])
