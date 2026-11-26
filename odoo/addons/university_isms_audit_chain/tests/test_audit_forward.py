import json
import os
import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch

import requests

from odoo import fields
from odoo.exceptions import AccessError
from odoo.addons.university_isms_audit_chain.models.audit_forward import IsmsAuditForward
from odoo.tests import TransactionCase, tagged

PARAM = 'university_isms_audit_chain.'


@tagged('post_install', '-at_install', 'university_isms_audit_chain')
class TestAuditForward(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Log = self.env['isms.audit.log']
        self.Head = self.env['isms.audit.chain.head']
        self.Forward = self.env['isms.audit.forward']
        self.icp = self.env['ir.config_parameter'].sudo()
        self.tmpdir = tempfile.mkdtemp(prefix='isms-audit-chain-test-')
        self.addCleanup(shutil.rmtree, self.tmpdir, True)
        self.icp.set_param(PARAM + 'file_path', '')
        self.icp.set_param(PARAM + 'http_url', '')
        self.icp.set_param(PARAM + 'http_backoff_seconds', '0')
        self.icp.set_param(PARAM + 'http_max_retries', '3')
        self.icp.set_param(PARAM + 'retention_days', '365')
        head = self.Head.search([], limit=1)
        # Тест бүр өөрийн бичлэгээс эхэлнэ: өмнөх суулгалтын бичлэгүүдийг дамжуулалтад оруулахгүй.
        head.sudo().write({'forward_file_seq': head.last_seq, 'forward_http_seq': head.last_seq})

    def _log(self, count=1, prefix='Дамжуулах'):
        return [self.Log._log('write', model='chain.test', res_name='%s %d' % (prefix, index),
                              changes='change %d' % index) for index in range(count)]

    def _queue(self, target='file'):
        return self.Forward.sudo().search([('target', '=', target)], order='seq_from')

    def _read_lines(self, path):
        with open(path, encoding='utf-8') as handle:
            return [line for line in handle.read().splitlines() if line.strip()]

    def _tamper(self, sql, params):
        self.env.cr.execute('ALTER TABLE isms_audit_log DISABLE TRIGGER isms_audit_log_guard_row')
        try:
            self.env.cr.execute(sql, params)
        finally:
            self.env.cr.execute('ALTER TABLE isms_audit_log ENABLE TRIGGER isms_audit_log_guard_row')

    # ------------------------------------------------------------ JSONL file target
    def test_file_forwarding_writes_head_hash_and_is_idempotent(self):
        path = os.path.join(self.tmpdir, 'audit-chain.jsonl')
        self.icp.set_param(PARAM + 'file_path', path)
        rows = self._log(3)
        head_before = self.Head.search([], limit=1).last_seq
        self.assertTrue(self.Forward._cron_forward_chain())

        lines = self._read_lines(path)
        self.assertEqual(len(lines), 1)
        body = json.loads(lines[0])
        self.assertEqual(body['type'], 'audit_chain_batch')
        self.assertEqual(body['seq_to'], head_before)
        self.assertEqual(body['entry_count'], 3)
        last_entry_hash = self.Log.sudo().search([('seq', '=', head_before)]).entry_hash
        self.assertEqual(body['head_hash'], last_entry_hash)
        self.assertEqual(self.Head.search([], limit=1).forward_file_seq, head_before)
        self.assertEqual(self._queue().mapped('state'), ['sent'])
        self.assertEqual(len(rows), 3)

        # Дахин ажиллуулахад шинэ мөр нэмэгдэхгүй
        self.Forward._cron_forward_chain()
        self.assertEqual(len(self._read_lines(path)), 1)

        # Багцыг дахин илгээх (курсор буцаагдсан гэж үзвэл) head_hash таарсан тул давхардахгүй
        batch = self._queue()
        batch.write({'state': 'pending'})
        self.Head.search([], limit=1).sudo().write({'forward_file_seq': batch.seq_from - 1})
        self.Forward._cron_forward_chain()
        self.assertEqual(len(self._read_lines(path)), 1)
        self.assertEqual(self._queue().mapped('state'), ['sent'])

    def test_ip_is_not_forwarded_in_clear(self):
        path = os.path.join(self.tmpdir, 'audit-chain.jsonl')
        self.icp.set_param(PARAM + 'file_path', path)
        self.env['isms.audit.log'].sudo().create({
            'action': 'login', 'model': 'res.users', 'res_name': 'IP test', 'changes': '',
            'ip_address': '203.0.113.77'})
        self.Forward._cron_forward_chain()
        content = open(path, encoding='utf-8').read()
        self.assertNotIn('203.0.113.77', content)
        body = json.loads(content.splitlines()[-1])
        self.assertTrue(any(entry['ip_hmac'] for entry in body['entries']))

    def test_file_write_failure_is_recorded_not_raised(self):
        blocker = os.path.join(self.tmpdir, 'blocker')
        with open(blocker, 'w', encoding='utf-8') as handle:
            handle.write('not a directory')
        self.icp.set_param(PARAM + 'file_path', os.path.join(blocker, 'audit.jsonl'))
        self._log(1)
        self.assertTrue(self.Forward._cron_forward_chain())
        batch = self._queue()
        self.assertEqual(batch.state, 'failed')
        self.assertEqual(batch.attempts, 1)
        self.assertTrue(batch.last_error)

    def test_digest_mismatch_blocks_delivery_and_is_recorded(self):
        path = os.path.join(self.tmpdir, 'audit-chain.jsonl')
        self.icp.set_param(PARAM + 'file_path', path)
        rows = self._log(2)
        self.Forward._enqueue_next('file')
        target = self.Log.sudo().search([('id', '=', rows[0].id)])
        self._tamper("UPDATE isms_audit_log SET changes = 'forged' WHERE id = %s", (target.id,))
        self.Forward._cron_forward_chain()
        batch = self._queue()
        self.assertEqual(batch.state, 'failed')
        self.assertIn('таарахгүй', batch.last_error)
        self.assertFalse(os.path.exists(path))

    # ------------------------------------------------------------ HTTP target
    def test_http_retries_with_mocked_failing_transport_and_records_attempts(self):
        self.icp.set_param(PARAM + 'http_url', 'https://siem.example.test/ingest')
        self._log(2)
        transport = [requests.exceptions.ConnectionError('boom'), 503, 200]
        with patch.object(IsmsAuditForward, '_http_post', side_effect=transport) as post:
            self.Forward._cron_forward_chain()
        self.assertEqual(post.call_count, 3)
        headers = post.call_args.args[2]
        head_hash = self._queue('http').head_hash
        self.assertEqual(headers['Idempotency-Key'], head_hash)
        batch = self._queue('http')
        self.assertEqual(batch.state, 'sent')
        self.assertEqual(batch.attempts, 3)
        self.assertEqual(self.Head.search([], limit=1).forward_http_seq, batch.seq_to)

    def test_http_permanent_failure_keeps_cursor_and_counts_attempts(self):
        self.icp.set_param(PARAM + 'http_url', 'https://siem.example.test/ingest')
        self._log(1)
        with patch.object(IsmsAuditForward, '_http_post',
                          side_effect=requests.exceptions.Timeout('timed out')) as post:
            self.Forward._cron_forward_chain()
        self.assertEqual(post.call_count, 4)  # 1 + http_max_retries(3)
        batch = self._queue('http')
        self.assertEqual(batch.state, 'failed')
        self.assertEqual(batch.attempts, 4)
        self.assertIn('Timeout', batch.last_error)
        self.assertNotIn('siem.example.test', batch.last_error)
        cursor_before = self.Head.search([], limit=1).forward_http_seq
        self.assertLess(cursor_before, batch.seq_to)
        with patch.object(IsmsAuditForward, '_http_post',
                          side_effect=requests.exceptions.Timeout('timed out')):
            self.Forward._cron_forward_chain()
        self.assertEqual(self._queue('http').attempts, 8)
        self.assertEqual(self.Head.search([], limit=1).forward_http_seq, cursor_before)

    def test_http_refuses_insecure_url_without_calling_transport(self):
        self.icp.set_param(PARAM + 'http_url', 'http://siem.example.test/ingest')
        self._log(1)
        with patch.object(IsmsAuditForward, '_http_post') as post:
            self.Forward._cron_forward_chain()
        post.assert_not_called()
        self.assertEqual(self._queue('http').state, 'failed')
        self.assertIn('https', self._queue('http').last_error)

    # ------------------------------------------------------------ retention and cron safety
    def test_retention_purges_only_old_sent_queue_rows(self):
        audit_before = self.Log.sudo().search_count([])
        now = fields.Datetime.now()
        old_sent = self.Forward.sudo().create({'target': 'file', 'seq_from': 900001, 'seq_to': 900002,
                                               'state': 'sent', 'sent_at': now - timedelta(days=400)})
        recent_sent = self.Forward.sudo().create({'target': 'file', 'seq_from': 900003, 'seq_to': 900004,
                                                  'state': 'sent', 'sent_at': now})
        old_failed = self.Forward.sudo().create({'target': 'file', 'seq_from': 900005, 'seq_to': 900006,
                                                 'state': 'failed', 'sent_at': False})
        self.assertEqual(self.Forward._purge_sent(), 1)
        self.assertFalse(old_sent.exists())
        self.assertTrue(recent_sent.exists())
        self.assertTrue(old_failed.exists())
        self.assertEqual(self.Log.sudo().search_count([]), audit_before)

    def test_retention_zero_keeps_everything(self):
        self.icp.set_param(PARAM + 'retention_days', '0')
        self.Forward.sudo().create({'target': 'file', 'seq_from': 900011, 'seq_to': 900012,
                                    'state': 'sent', 'sent_at': fields.Datetime.now() - timedelta(days=4000)})
        self.assertEqual(self.Forward._purge_sent(), 0)

    def test_cron_never_raises(self):
        with patch.object(IsmsAuditForward, '_forward_all', side_effect=RuntimeError('boom')), \
                patch.object(IsmsAuditForward, '_purge_sent', side_effect=RuntimeError('boom again')):
            self.assertTrue(self.Forward._cron_forward_chain())

    def test_only_auditor_or_ciso_or_system_can_run_or_retry(self):
        group_user = self.env.ref('base.group_user')
        plain = self.env['res.users'].create({
            'name': 'Forward plain', 'login': 'forward_plain_user',
            'groups_id': [(6, 0, [group_user.id])]})
        batch = self.Forward.sudo().create({'target': 'file', 'seq_from': 900021, 'seq_to': 900022,
                                            'state': 'failed'})
        with self.assertRaises(AccessError):
            self.Forward.with_user(plain).action_run_forward()
        with self.assertRaises(AccessError):
            batch.with_user(plain).action_retry()
