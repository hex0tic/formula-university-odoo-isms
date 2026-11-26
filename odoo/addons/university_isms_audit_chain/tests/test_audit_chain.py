from types import SimpleNamespace
from unittest.mock import patch

import psycopg2.errors

from odoo.addons.university_isms_audit_chain.hooks import backfill_chain
from odoo.addons.university_isms_audit_chain.models.audit_chain import (
    GENESIS_HASH, canonical_payload, entry_hash_of)
from odoo.addons.university_isms_monitoring_plus.models import check_registry as reg
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'university_isms_audit_chain')
class TestAuditChain(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Log = self.env['isms.audit.log']
        self.Head = self.env['isms.audit.chain.head']

    # ------------------------------------------------------------ helpers
    def _log(self, count=1, prefix='Бичлэг'):
        return [self.Log._log('write', model='chain.test', res_name='%s %d' % (prefix, index),
                              changes='old -> new %d' % index) for index in range(count)]

    def _chained_rows(self):
        return self.Log.sudo().search([('seq', '!=', False)], order='seq')

    def _hash_at(self, seq):
        if not seq:
            return GENESIS_HASH
        self.env.cr.execute('SELECT entry_hash FROM isms_audit_log WHERE seq = %s', (seq,))
        return self.env.cr.fetchone()[0]

    def _tamper(self, sql, params):
        """Trigger-ийг түр унтраагаад raw SQL хийнэ (superuser-ийн боломжийг дуурайна)."""
        self.env.cr.execute('ALTER TABLE isms_audit_log DISABLE TRIGGER isms_audit_log_guard_row')
        try:
            self.env.cr.execute(sql, params)
        finally:
            self.env.cr.execute('ALTER TABLE isms_audit_log ENABLE TRIGGER isms_audit_log_guard_row')

    # ------------------------------------------------------------ chain correctness
    def test_new_entries_chain_correctly(self):
        start = self.Head.search([], limit=1).last_seq
        self._log(3)
        rows = self._chained_rows().filtered(lambda rec: rec.seq > start)
        self.assertEqual(rows.mapped('seq'), list(range(start + 1, start + 4)))
        self.assertEqual(rows[0].prev_hash, self._hash_at(start))
        self.assertEqual(rows[1].prev_hash, rows[0].entry_hash)
        self.assertEqual(rows[2].prev_hash, rows[1].entry_hash)
        for rec in rows:
            payload = canonical_payload(
                seq=rec.seq, timestamp=rec.timestamp, user_id=rec.user_id.id, action=rec.action,
                model=rec.model, res_id=rec.res_id, res_name=rec.res_name, changes=rec.changes,
                ip=rec.ip_address, prev_hash=rec.prev_hash)
            self.assertEqual(entry_hash_of(payload), rec.entry_hash)
        self.assertTrue(self.Log._verify_chain()['ok'])

    def test_server_side_fields_override_client_values(self):
        rec = self.Log.sudo().create({'action': 'write', 'model': 'chain.test', 'res_name': 'forged seq',
                                      'changes': 'x', 'seq': 999999, 'prev_hash': 'bogus',
                                      'entry_hash': 'bogus'})
        self.assertNotEqual(rec.seq, 999999)
        self.assertNotEqual(rec.entry_hash, 'bogus')
        self.assertNotEqual(rec.prev_hash, 'bogus')
        self.assertTrue(self.Log._verify_chain()['ok'])

    def test_seq_assignment_takes_chain_head_lock(self):
        head_cls = type(self.Head)
        original = head_cls._lock_head
        with patch.object(head_cls, '_lock_head', autospec=True, side_effect=original) as locked:
            self._log(2)
        self.assertEqual(locked.call_count, 2)
        head = self.Head.search([], limit=1)
        self.assertEqual(head.last_seq, max(self._chained_rows().mapped('seq')))

    def test_rolled_back_insert_leaves_no_gap(self):
        head = self.Head.search([], limit=1)
        before = head.last_seq
        with self.assertRaises(RuntimeError), self.env.cr.savepoint():
            self._log(1, prefix='rolled back')
            raise RuntimeError('force rollback')
        head.invalidate_recordset()
        self.assertEqual(head.last_seq, before)
        self._log(1, prefix='after rollback')
        self.assertTrue(self.Log._verify_chain()['ok'])

    # ------------------------------------------------------------ DB trigger
    def test_trigger_blocks_sql_update(self):
        rec = self._log(1)[0]
        with self.assertRaises(psycopg2.errors.InsufficientPrivilege), self.env.cr.savepoint():
            self.env.cr.execute("UPDATE isms_audit_log SET changes = 'forged' WHERE id = %s", (rec.id,))

    def test_trigger_blocks_sql_delete(self):
        rec = self._log(1)[0]
        with self.assertRaises(psycopg2.errors.InsufficientPrivilege), self.env.cr.savepoint():
            self.env.cr.execute('DELETE FROM isms_audit_log WHERE id = %s', (rec.id,))

    def test_trigger_blocks_truncate(self):
        self._log(1)
        with self.assertRaises(psycopg2.errors.InsufficientPrivilege), self.env.cr.savepoint():
            self.env.cr.execute('TRUNCATE isms_audit_log')

    def test_orm_write_and_unlink_still_refused(self):
        rec = self._log(1)[0]
        with self.assertRaises(UserError):
            rec.write({'changes': 'orm'})
        with self.assertRaises(UserError):
            rec.unlink()

    # ------------------------------------------------------------ tamper detection
    def test_tampering_detected_at_correct_seq(self):
        self._log(5)
        self.assertTrue(self.Log._verify_chain()['ok'])
        target = self._chained_rows()[-3]
        self._tamper("UPDATE isms_audit_log SET changes = 'forged' WHERE id = %s", (target.id,))
        result = self.Log._verify_chain()
        self.assertFalse(result['ok'])
        self.assertEqual(result['broken_seq'], target.seq)
        self.assertIn('хэш', result['reason'])

    def test_prev_link_tampering_detected(self):
        self._log(3)
        target = self._chained_rows()[-1]
        self._tamper('UPDATE isms_audit_log SET prev_hash = %s WHERE id = %s', ('f' * 64, target.id))
        result = self.Log._verify_chain()
        self.assertEqual(result['broken_seq'], target.seq)
        self.assertIn('холбоос', result['reason'])

    def test_deleted_middle_row_detected_as_gap(self):
        self._log(4)
        middle = self._chained_rows()[-2]
        self._tamper('DELETE FROM isms_audit_log WHERE id = %s', (middle.id,))
        result = self.Log._verify_chain()
        self.assertFalse(result['ok'])
        self.assertEqual(result['broken_seq'], middle.seq)
        self.assertIn('тасарсан', result['reason'])

    def test_tail_truncation_detected_by_head(self):
        self._log(3)
        last = self._chained_rows()[-1]
        self._tamper('DELETE FROM isms_audit_log WHERE id = %s', (last.id,))
        result = self.Log._verify_chain()
        self.assertFalse(result['ok'])
        self.assertEqual(result['broken_seq'], last.seq)
        self.assertIn('устсан', result['reason'])

    def test_limit_verifies_prefix_only(self):
        self._log(3)
        result = self.Log._verify_chain(limit=2)
        self.assertTrue(result['ok'])
        self.assertEqual(result['checked'], 2)

    # ------------------------------------------------------------ migration of existing rows
    def test_backfill_chains_preexisting_rows_once(self):
        self._log(1)
        for index in range(3):
            self.env.cr.execute(
                """INSERT INTO isms_audit_log (timestamp, action, model, res_id, res_name, changes,
                       ip_address, create_uid, create_date, write_uid, write_date)
                   VALUES ((now() at time zone 'utc'), 'write', 'legacy.model', %s, %s, 'legacy',
                           '', 1, now(), 1, now())""",
                (index + 1, 'Legacy %d' % index))
        self.env.cr.execute('SELECT COUNT(*) FROM isms_audit_log WHERE seq IS NULL')
        self.assertEqual(self.env.cr.fetchone()[0], 3)
        self.assertEqual(backfill_chain(self.env), 3)
        self.assertEqual(backfill_chain(self.env), 0)
        self.assertTrue(self.Log._verify_chain()['ok'])
        legacy = self.Log.sudo().search([('res_name', '=like', 'Legacy%')], order='id')
        self.assertEqual(len(legacy), 3)
        with self.assertRaises(psycopg2.errors.InsufficientPrivilege), self.env.cr.savepoint():
            self.env.cr.execute("UPDATE isms_audit_log SET changes = 'x' WHERE id = %s", (legacy[0].id,))

    # ------------------------------------------------------------ access
    def test_only_auditor_or_ciso_can_verify(self):
        group_user = self.env.ref('base.group_user')
        plain = self.env['res.users'].create({
            'name': 'Chain plain user', 'login': 'chain_plain_user',
            'groups_id': [(6, 0, [group_user.id])]})
        auditor = self.env['res.users'].create({
            'name': 'Chain auditor', 'login': 'chain_auditor_user',
            'groups_id': [(6, 0, [group_user.id, self.env.ref('university_isms.group_isms_auditor').id])]})
        ciso = self.env['res.users'].create({
            'name': 'Chain CISO', 'login': 'chain_ciso_user',
            'groups_id': [(6, 0, [group_user.id, self.env.ref('university_isms.group_isms_manager').id])]})
        with self.assertRaises(AccessError):
            self.Head.with_user(plain).action_verify_chain()
        self.assertEqual(self.Head.with_user(auditor).action_verify_chain()['tag'], 'display_notification')
        self.assertEqual(self.Head.with_user(ciso).action_verify_chain()['tag'], 'display_notification')
        self.assertTrue(self.Head.search([], limit=1).last_verified_at)

    # ------------------------------------------------------------ monitoring check
    def test_monitoring_check_pass_fail_and_not_applicable(self):
        spec = reg.CHECKS['audit_chain_integrity']
        self._log(3)
        result, _details, metrics = spec.func(self.env)
        self.assertEqual(result, reg.PASS)
        self.assertGreaterEqual(metrics['checked'], 3)
        target = self._chained_rows()[-2]
        self._tamper("UPDATE isms_audit_log SET changes = 'forged' WHERE id = %s", (target.id,))
        result, details, _metrics = spec.func(self.env)
        self.assertEqual(result, reg.FAIL)
        self.assertIn('seq=%s' % target.seq, details)
        self.assertEqual(spec.func(SimpleNamespace(registry={}))[0], reg.NOT_APPLICABLE)
