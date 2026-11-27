from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import IntegrationCase

DOMAIN = 'univ.unit-test.invalid'


@tagged('formula_integration_hub')
class TestSso(IntegrationCase):

    def _sso(self):
        endpoint = self.env['formula.integration.endpoint'].create({
            'name': 'sso-unit', 'kind': 'sso', 'issuer': 'https://idp.unit-test.invalid',
            'client_id': 'erp-unit-client', 'allowed_domains': DOMAIN, 'secret_key': '',
            'auth_method': 'none'})
        endpoint.enabled = True
        self.env['formula.sso.group.rule'].create({
            'endpoint_id': endpoint.id, 'idp_group': 'idp-analyst',
            'group_id': self.env.ref('university_isms.group_isms_analyst').id})
        self.env['formula.sso.group.rule'].create({
            'endpoint_id': endpoint.id, 'idp_group': 'idp-student',
            'group_id': self.env.ref('campus_university.group_campus_student').id})
        return endpoint

    def _claims(self, **kw):
        data = {'sub': 'idp-sub-001', 'email': 'person@%s' % DOMAIN, 'email_verified': True,
                'name': 'Person One', 'groups': []}
        data.update(kw)
        return data

    def test_privileged_groups_cannot_be_mapped(self):
        endpoint = self._sso()
        Rule = self.env['formula.sso.group.rule']
        for xmlid in ('base.group_system', 'base.group_erp_manager',
                      'university_isms.group_isms_manager', 'campus_university.group_campus_registrar'):
            with self.assertRaises(ValidationError):
                Rule.create({'endpoint_id': endpoint.id, 'idp_group': 'evil-' + xmlid,
                             'group_id': self.env.ref(xmlid).id})

    def test_mapped_group_granted_and_privileged_not_granted(self):
        endpoint = self._sso()
        user = self.env['formula.sso.adapter'].provision_user(
            endpoint, self._claims(groups=['idp-analyst', 'cn=domain-admins']))
        self.assertTrue(user.has_group('university_isms.group_isms_analyst'))
        self.assertFalse(user.has_group('base.group_system'))
        self.assertFalse(user.has_group('base.group_erp_manager'))
        self.assertFalse(user.has_group('university_isms.group_isms_manager'))

    def test_provisioning_is_deterministic_and_revokes_only_rule_groups(self):
        endpoint = self._sso()
        Adapter = self.env['formula.sso.adapter']
        first = Adapter.provision_user(endpoint, self._claims(groups=['idp-analyst']))
        manual = self.env.ref('campus_university.group_campus_auditor')
        first.write({'groups_id': [(4, manual.id)]})
        again = Adapter.provision_user(endpoint, self._claims(groups=['idp-analyst']))
        self.assertEqual(first.id, again.id)
        self.assertTrue(again.has_group('university_isms.group_isms_analyst'))
        revoked = Adapter.provision_user(endpoint, self._claims(groups=[]))
        self.assertFalse(revoked.has_group('university_isms.group_isms_analyst'))
        self.assertTrue(revoked.has_group('base.group_user'))
        self.assertTrue(revoked.has_group('campus_university.group_campus_auditor'))

    def test_unverified_email_and_foreign_domain_rejected(self):
        endpoint = self._sso()
        Adapter = self.env['formula.sso.adapter']
        with self.assertRaises(AccessError):
            Adapter.provision_user(endpoint, self._claims(email_verified=False))
        with self.assertRaises(AccessError):
            Adapter.provision_user(endpoint, self._claims(email='x@other.invalid'))

    def test_existing_unlinked_account_is_not_adopted(self):
        endpoint = self._sso()
        self.env['res.users'].create({'name': 'Pre-existing', 'login': 'adopt@' + DOMAIN,
                                      'email': 'adopt@' + DOMAIN})
        with self.assertRaises(ValidationError):
            self.env['formula.sso.adapter'].provision_user(
                endpoint, self._claims(email='adopt@' + DOMAIN, sub='sub-x'))

    def test_discovery_document_validated(self):
        Adapter = self.env['formula.sso.adapter']
        good = {'issuer': 'https://idp.unit-test.invalid', 'authorization_endpoint': 'https://idp.unit-test.invalid/a',
                'token_endpoint': 'https://idp.unit-test.invalid/t', 'jwks_uri': 'https://idp.unit-test.invalid/k'}
        parsed = Adapter.parse_discovery(good, 'https://idp.unit-test.invalid')
        self.assertEqual(parsed['token_endpoint'], good['token_endpoint'])
        with self.assertRaises(ValidationError):
            Adapter.parse_discovery(good, 'https://other.unit-test.invalid')
        bad = dict(good, jwks_uri='http://idp.unit-test.invalid/k')
        with self.assertRaises(ValidationError):
            Adapter.parse_discovery(bad, 'https://idp.unit-test.invalid')

    def test_sso_enable_requires_domains(self):
        endpoint = self.env['formula.integration.endpoint'].create({
            'name': 'sso-incomplete', 'kind': 'sso', 'auth_method': 'none'})
        with self.assertRaises(ValidationError):
            endpoint.enabled = True

    def test_student_sso_first_and_repeat_sign_in_keep_portal_type(self):
        endpoint = self._sso()
        adapter = self.env["formula.sso.adapter"]
        claims = self._claims(groups=["idp-student"])
        student = adapter.provision_user(endpoint, claims)
        self.assertEqual(student, adapter.provision_user(endpoint, claims))
        self.assertTrue(student.has_group("base.group_portal"))
        self.assertFalse(student.has_group("base.group_user"))
        self.assertFalse(student.has_group("university_isms.group_isms_reporter"))

    def test_sso_rejects_conflicting_user_types(self):
        endpoint = self._sso()
        adapter = self.env["formula.sso.adapter"]
        with self.assertRaises(AccessError):
            adapter.provision_user(endpoint, self._claims(groups=["idp-student", "idp-analyst"]))
        student = adapter.provision_user(endpoint, self._claims(groups=["idp-student"]))
        with self.assertRaises(AccessError):
            adapter.provision_user(endpoint, self._claims(groups=["idp-analyst"]))
        self.assertTrue(student.has_group("base.group_portal"))
        self.assertFalse(student.has_group("university_isms.group_isms_analyst"))
