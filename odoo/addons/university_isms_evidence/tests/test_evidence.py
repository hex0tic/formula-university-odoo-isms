"""university_isms_evidence: нотлох баримт (ISMS-01), бодлогын баталгаажуулалт (ISMS-06),
аудитын экспорт (ISMS-08) ба тэдгээрийн эрхийн шалгалт."""
import base64
import csv
import hashlib
import io
import zipfile
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install', 'university_isms_evidence')
class TestEvidenceVault(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.reporter = new_test_user(env, 'ev_reporter', groups='university_isms.group_isms_reporter')
        cls.owner = new_test_user(env, 'ev_owner', groups='university_isms.group_isms_asset_owner')
        cls.owner2 = new_test_user(env, 'ev_owner2', groups='university_isms.group_isms_asset_owner')
        cls.analyst = new_test_user(env, 'ev_analyst', groups='university_isms.group_isms_analyst')
        cls.auditor = new_test_user(env, 'ev_auditor', groups='university_isms.group_isms_auditor')
        cls.auditor2 = new_test_user(env, 'ev_auditor2', groups='university_isms.group_isms_auditor')
        cls.manager = new_test_user(env, 'ev_manager', groups='university_isms.group_isms_manager')
        cls.c1 = env['isms.control'].search([('code', '=', '5.1')], limit=1)
        cls.c2 = env['isms.control'].search([('code', '=', '5.15')], limit=1)
        cls.c3 = env['isms.control'].search([('code', '=', '8.2')], limit=1)

    # ------------------------------------------------------------ helpers
    def _today(self):
        return fields.Date.context_today(self.env['isms.evidence'])

    def _ev(self, user, controls, content=b'proof-content', reviewer=None, owner=None, **extra):
        vals = {
            'name': 'Нотолгоо',
            'control_ids': [(6, 0, controls.ids)],
            'attachment': base64.b64encode(content).decode(),
            'file_name': 'proof.txt',
            'valid_until': self._today() + timedelta(days=30),
            'reviewer_id': (reviewer or self.auditor).id,
            'owner_id': (owner or user).id,
        }
        vals.update(extra)
        return self.env['isms.evidence'].with_user(user).create(vals)

    def _approved(self, controls, content=b'proof-content', **extra):
        ev = self._ev(self.analyst, controls, content, **extra)
        ev.with_user(self.analyst).action_submit()
        ev.with_user(self.auditor).action_approve()
        return ev

    def _policy(self):
        policy = self.env['isms.policy'].create({'name': 'Хандалтын бодлого', 'policy_type': 'eisp'})
        policy.action_approve()
        return policy

    def _export(self, controls, user=None):
        wiz = self.env['isms.evidence.export.wizard'].with_user(user or self.auditor).create(
            {'control_ids': [(6, 0, controls.ids)]})
        action = wiz.action_generate()
        return self.env['isms.evidence.export'].browse(action['res_id'])

    def _zip(self, export):
        raw = base64.b64decode(export.sudo().zip_file)
        return zipfile.ZipFile(io.BytesIO(raw))

    @staticmethod
    def _csv(zf, name):
        return list(csv.DictReader(io.StringIO(zf.read(name).decode('utf-8-sig'))))

    def _tamper(self, evidence, new_bytes):
        att = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'isms.evidence'), ('res_id', '=', evidence.id),
            ('res_field', '=', 'attachment')])
        self.assertEqual(len(att), 1)
        att.write({'datas': base64.b64encode(new_bytes)})

    # ------------------------------------------------------------ ISMS-01 digest
    def test_01_digest_computed_server_side(self):
        content = b'Policy evidence 2026\n'
        ev = self._ev(self.analyst, self.c1, content)
        self.assertEqual(ev.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(ev.file_size, len(content))
        self.assertEqual(ev.mimetype, 'text/plain')
        self.assertEqual(ev.uploaded_by_id, self.analyst)
        self.assertEqual(ev.version, 1)
        # клиент нийлбэр илгээвэл татгалзана
        with self.assertRaises(AccessError):
            self._ev(self.analyst, self.c1, sha256='0' * 64)
        # файл солиход нийлбэр дахин серверт тооцогдоно
        ev.with_user(self.analyst).write({'attachment': base64.b64encode(b'v2').decode()})
        self.assertEqual(ev.sha256, hashlib.sha256(b'v2').hexdigest())

    # ------------------------------------------------------------ ISMS-01 tampering
    def test_02_tampering_is_detected_and_logged(self):
        ev = self._approved(self.c1, b'original bytes')
        self.assertEqual(ev._digest_check(), 'match')
        self._tamper(ev, b'tampered bytes')
        self.assertEqual(ev._digest_check(), 'mismatch')
        result = ev.with_user(self.auditor).action_verify_digest()
        self.assertEqual(result['params']['type'], 'danger')
        logged = self.env['isms.audit.log'].search([
            ('model', '=', 'isms.evidence'), ('res_id', '=', ev.id), ('changes', 'ilike', 'SHA-256 шалгалт')])
        self.assertTrue(logged)

    def test_03_reviewer_separation(self):
        with self.assertRaises(ValidationError):  # өөрөө хянана
            self._ev(self.analyst, self.c1, reviewer=self.analyst)
        with self.assertRaises(ValidationError):  # эзэмшигч өөрөө хянана
            self._ev(self.owner, self.c1, reviewer=self.owner)
        with self.assertRaises(ValidationError):  # аудитор биш хянагч
            self._ev(self.analyst, self.c1, reviewer=self.owner)

    def test_04_only_assigned_auditor_reviews(self):
        ev = self._ev(self.analyst, self.c1)
        ev.with_user(self.analyst).action_submit()
        with self.assertRaises(AccessError):
            ev.with_user(self.auditor2).action_approve()
        with self.assertRaises(AccessError):
            ev.with_user(self.analyst).action_approve()
        with self.assertRaises(UserError):
            ev.with_user(self.auditor).action_reject()  # тэмдэглэлгүй татгалзахгүй
        ev.with_user(self.auditor).write({'review_note': 'Шалгалт хийсэн'})
        ev.with_user(self.auditor).action_approve()
        self.assertEqual(ev.state, 'approved')
        self.assertTrue(ev.reviewed_at)

    def test_05_approved_is_immutable_and_versioned(self):
        ev = self._approved(self.c1, b'v1 content')
        with self.assertRaises(UserError):
            ev.with_user(self.analyst).write({'description': 'changed'})
        with self.assertRaises(UserError):
            ev.with_user(self.analyst).write({'attachment': base64.b64encode(b'swap').decode()})
        with self.assertRaises(UserError):
            ev.with_user(self.analyst).write({'control_ids': [(6, 0, self.c2.ids)]})
        ev.with_user(self.analyst).action_new_version()
        v2 = ev.next_version_ids
        self.assertEqual(len(v2), 1)
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.previous_version_id, ev)
        self.assertEqual(v2.state, 'draft')
        self.assertEqual(v2.control_ids, self.c1)
        self.assertFalse(v2.sha256)
        v2.with_user(self.analyst).write({
            'attachment': base64.b64encode(b'v2 content').decode(),
            'valid_until': self._today() + timedelta(days=60),
            'reviewer_id': self.auditor.id,
        })
        v2.with_user(self.analyst).action_submit()
        v2.with_user(self.auditor).action_approve()
        self.assertTrue(ev.is_superseded)
        self.assertEqual(ev.version, 1)
        self.assertEqual(ev.sha256, hashlib.sha256(b'v1 content').hexdigest())

    def test_06_unlink_rules(self):
        draft = self._ev(self.analyst, self.c1)
        approved = self._approved(self.c2)
        with self.assertRaises(UserError):
            approved.with_user(self.analyst).unlink()
        with self.assertRaises(AccessError):
            draft.with_user(self.manager).unlink()  # оруулсан хүн биш
        draft.with_user(self.analyst).unlink()
        self.assertFalse(draft.exists())

    def test_07_reporter_and_owner_visibility(self):
        Evidence = self.env['isms.evidence']
        ev_own = self._ev(self.analyst, self.c1, owner=self.owner)
        ev_other = self._ev(self.analyst, self.c1, owner=self.owner2)
        with self.assertRaises(AccessError):
            Evidence.with_user(self.reporter).search([])
        with self.assertRaises(AccessError):
            ev_own.with_user(self.reporter).read(['name'])
        visible = Evidence.with_user(self.owner).search([])
        self.assertIn(ev_own, visible)
        self.assertNotIn(ev_other, visible)

    # ------------------------------------------------------------ ISMS-06 attestation
    def _campaign(self, policy, scope='all', groups=None):
        vals = {'name': 'Баталгаажуулалт', 'policy_id': policy.id, 'scope': scope,
                'due_date': self._today() + timedelta(days=30)}
        if groups:
            vals['group_ids'] = [(6, 0, groups.ids)]
        return self.env['isms.policy.attestation.campaign'].with_user(self.analyst).create(vals)

    def _att(self, campaign, user):
        return self.env['isms.policy.attestation'].search([
            ('campaign_id', '=', campaign.id), ('user_id', '=', user.id)])

    def test_08_attestation_is_self_only_and_scoped(self):
        policy = self._policy()
        grp = self.env['res.groups'].create({'name': 'Тест баталгаажуулалтын бүлэг'})
        self.reporter.write({'groups_id': [(4, grp.id)]})
        campaign = self._campaign(policy, scope='groups', groups=grp)
        campaign.with_user(self.analyst).action_open()
        self.assertEqual(campaign.state, 'open')
        mine = self._att(campaign, self.reporter)
        self.assertEqual(len(self.env['isms.policy.attestation'].search([('campaign_id', '=', campaign.id)])), 1)
        att = mine.with_user(self.reporter)
        self.assertEqual(att.state, 'pending')
        self.assertTrue(att.is_mine)
        att.action_attest()
        self.assertEqual(att.state, 'attested')
        self.assertEqual(att.revision, policy.version)
        self.assertTrue(self.env['isms.policy.ack'].search_count([
            ('policy_id', '=', policy.id), ('user_id', '=', self.reporter.id), ('version', '=', policy.version)]))
        # reporter кампанит ажлыг харахгүй
        with self.assertRaises(AccessError):
            campaign.with_user(self.reporter).read(['name'])
        # бусдын баталгаажуулалт
        all_campaign = self._campaign(policy, scope='all')
        all_campaign.with_user(self.analyst).action_open()
        other = self._att(all_campaign, self.owner)
        with self.assertRaises(AccessError):
            other.with_user(self.reporter).action_attest()
        with self.assertRaises(AccessError):
            other.with_user(self.analyst).action_attest()
        with self.assertRaises(AccessError):
            self._att(all_campaign, self.reporter).with_user(self.reporter).write({'state': 'attested'})

    def test_09_new_revision_makes_attestation_stale(self):
        policy = self._policy()
        campaign = self._campaign(policy)
        campaign.with_user(self.analyst).action_open()
        att = self._att(campaign, self.reporter).with_user(self.reporter)
        att.action_attest()
        self.assertEqual(att.state, 'attested')
        policy.sudo().write({'version': '2.0'})
        self.assertEqual(att.state, 'stale')
        # хуучин кампанит ажлаар шинэ хувилбарыг баталгаажуулж болохгүй
        with self.assertRaises(UserError):
            self._att(campaign, self.analyst).with_user(self.analyst).action_attest()
        campaign2 = self._campaign(policy)
        campaign2.with_user(self.analyst).action_open()
        self.assertEqual(campaign2.policy_revision, '2.0')
        att2 = self._att(campaign2, self.reporter).with_user(self.reporter)
        att2.action_attest()
        self.assertEqual(att2.state, 'attested')
        self.assertEqual(att2.revision, '2.0')
        self.assertEqual(att.state, 'stale')

    def test_10_expiry_cron_marks_expired(self):
        policy = self._policy()
        campaign = self._campaign(policy)
        campaign.with_user(self.analyst).action_open()
        att = self._att(campaign, self.reporter).with_user(self.reporter)
        att.action_attest()
        self.assertEqual(att.state, 'attested')
        # хугацаа өнгөрсөнийг дуурайлгана (өдөр солигдсон, төлөв дахин тооцоогүй)
        yesterday = self._today() - timedelta(days=1)
        self.env.flush_all()  # ORM-д хүлээгдэж буй бичилтийг эхлээд DB-д бичнэ
        self.env.cr.execute('UPDATE isms_policy_attestation SET expires_on = %s WHERE id = %s',
                            (yesterday, att.id))
        self.env.invalidate_all()
        self.assertEqual(att.state, 'attested')
        self.assertEqual(self.env['isms.policy.attestation']._cron_expire_attestations(), 1)
        self.env.invalidate_all()
        self.assertEqual(att.state, 'expired')

    # ------------------------------------------------------------ ISMS-08 export
    def test_11_low_privilege_cannot_export(self):
        for user in (self.owner, self.reporter, self.analyst):
            wiz = self.env['isms.evidence.export.wizard'].with_user(user).create(
                {'control_ids': [(6, 0, self.c1.ids)]})
            with self.assertRaises(AccessError):
                wiz.action_generate()

    def test_12_export_index_files_and_missing(self):
        controls = self.c1 | self.c2 | self.c3
        content = b'POLICY-PDF-BYTES'
        ev1 = self._approved(self.c1, content)
        ev2 = self._ev(self.analyst, self.c2)  # зөвхөн ноорог
        ev3 = self._approved(self.c3, b'expiring proof')
        ev3.sudo().write({'valid_until': self._today() - timedelta(days=1)})

        export = self._export(controls)
        self.assertEqual(export.requested_by_id, self.auditor)
        self.assertEqual(export.control_count, 3)
        self.assertEqual(export.covered_count, 1)
        self.assertEqual(export.missing_count, 2)
        self.assertFalse(export.is_complete)
        raw = base64.b64decode(export.sudo().zip_file)
        self.assertEqual(export.zip_sha256, hashlib.sha256(raw).hexdigest())

        zf = self._zip(export)
        names = zf.namelist()
        for required in ('index.csv', 'missing.csv', 'manifest.txt'):
            self.assertIn(required, names)
        file_names = [n for n in names if n.startswith('files/')]
        self.assertEqual(len(file_names), 1)
        self.assertIn('EV-%05d' % ev1.id, file_names[0])
        self.assertEqual(zf.read(file_names[0]), content)

        index = {r['evidence_ref']: r for r in self._csv(zf, 'index.csv') if r['evidence_ref']}
        self.assertEqual(index['EV-%05d' % ev1.id]['package_status'], 'INCLUDED')
        self.assertEqual(index['EV-%05d' % ev1.id]['evidence_sha256'], hashlib.sha256(content).hexdigest())
        self.assertEqual(index['EV-%05d' % ev2.id]['package_status'], 'NOT_APPROVED')
        self.assertEqual(index['EV-%05d' % ev3.id]['package_status'], 'EXPIRED')

        missing = {r['control_code']: r['reason_code'] for r in self._csv(zf, 'missing.csv')}
        self.assertEqual(missing, {self.c2.code: 'NO_APPROVED_EVIDENCE', self.c3.code: 'APPROVED_EXPIRED'})

        manifest = zf.read('manifest.txt').decode('utf-8')
        self.assertIn(self.auditor.login, manifest)
        self.assertIn('MISSING:', manifest)
        # экспорт бүртгэл өөрчлөгдөхгүй
        with self.assertRaises(AccessError):
            export.with_user(self.auditor).write({'name': 'өөрчлөлт'})

    def test_13_export_excludes_records_requester_cannot_read(self):
        self._approved(self.c1, b'SECRET-CONTENT', description='SECRET-HIDDEN')
        rule = self.env.ref('university_isms_evidence.rule_isms_evidence_all')
        rule.sudo().write({'domain_force': "[('description', '!=', 'SECRET-HIDDEN')]"})
        export = self._export(self.c1)
        zf = self._zip(export)
        self.assertFalse([n for n in zf.namelist() if n.startswith('files/')])
        for name in zf.namelist():
            self.assertNotIn(b'SECRET-CONTENT', zf.read(name))
        self.assertNotIn('SECRET-HIDDEN', zf.read('index.csv').decode('utf-8-sig'))
        self.assertEqual(export.missing_count, 1)
        self.assertEqual(self._csv(zf, 'missing.csv')[0]['control_code'], self.c1.code)

    def test_14_tampered_evidence_is_excluded_from_package(self):
        ev = self._approved(self.c1, b'original bytes')
        self._tamper(ev, b'tampered bytes')
        export = self._export(self.c1)
        zf = self._zip(export)
        self.assertFalse([n for n in zf.namelist() if n.startswith('files/')])
        missing = self._csv(zf, 'missing.csv')
        self.assertEqual(missing[0]['reason_code'], 'DIGEST_MISMATCH')
        self.assertEqual(export.covered_count, 0)
