from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.exceptions import UserError

from ..models.event import backoff_seconds
from ..models.transport import HttpTransport
from .common import IntegrationCase, TEST_SECRET_VALUE


@tagged('formula_integration_hub')
class TestOutbox(IntegrationCase):

    def test_disabled_flag_enqueues_and_sends_nothing(self):
        endpoint = self._endpoint('notify', enabled=False)
        event = self.env['formula.integration.event'].enqueue(endpoint, 'x.y', {'a': 1}, 'key-off')
        self.assertFalse(event)
        self.assertEqual(self.env['formula.integration.event'].search_count([('endpoint_id', '=', endpoint.id)]), 0)
        with self._post_patch() as post:
            self.env['formula.integration.event']._cron_dispatch()
            post.assert_not_called()

    def test_idempotency_key_prevents_duplicates(self):
        endpoint = self._endpoint('notify')
        Event = self.env['formula.integration.event']
        first = Event.enqueue(endpoint, 'x.created', {'a': 1}, 'same-key')
        second = Event.enqueue(endpoint, 'x.created', {'a': 1}, 'same-key')
        other = Event.enqueue(endpoint, 'x.created', {'a': 2}, 'other-key')
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(Event.search_count([('endpoint_id', '=', endpoint.id)]), 2)

    def test_idempotency_key_sent_as_header_and_secret_not_in_payload(self):
        endpoint = self._endpoint('notify', auth_method='bearer')
        event = self.env['formula.integration.event'].enqueue(endpoint, 'x.created', {'a': 1}, 'hdr-key')
        request = HttpTransport.prepare(endpoint, event)
        self.assertEqual(request['headers']['Idempotency-Key'], 'hdr-key')
        self.assertEqual(request['headers']['Authorization'], 'Bearer %s' % TEST_SECRET_VALUE)
        self.assertNotIn(TEST_SECRET_VALUE, event.payload_json)

    def test_retry_backoff_then_dead_letter(self):
        endpoint = self._endpoint('notify', max_attempts=3)
        event = self.env['formula.integration.event'].enqueue(endpoint, 'x.created', {'a': 1}, 'retry-key')
        self.assertEqual(event.max_attempts, 3)
        with self._post_patch(side_effect=[ConnectionError('net down'), (500, ''), (503, '')]):
            before = fields.Datetime.now()
            event._dispatch_one()
            self.assertEqual(event.state, 'failed')
            self.assertEqual(event.attempts, 1)
            self.assertAlmostEqual((event.next_attempt_at - before).total_seconds(), backoff_seconds(1), delta=5)
            self.past(event)
            before = fields.Datetime.now()
            event._dispatch_one()
            self.assertEqual(event.state, 'failed')
            self.assertAlmostEqual((event.next_attempt_at - before).total_seconds(), backoff_seconds(2), delta=5)
            self.past(event)
            event._dispatch_one()
        self.assertEqual(event.state, 'dead')
        self.assertEqual(event.attempts, 3)
        self.assertIn('HTTP 503', event.last_error)
        # Dead-letter дахин оролдогдохгүй
        with self._post_patch() as post:
            self.env['formula.integration.event']._cron_dispatch()
            post.assert_not_called()
        event.action_requeue()
        self.assertEqual((event.state, event.attempts), ('pending', 0))

    def test_success_marks_sent(self):
        endpoint = self._endpoint('notify')
        event = self.env['formula.integration.event'].enqueue(endpoint, 'x.created', {'a': 1}, 'ok-key')
        with self._post_patch(return_value=(204, '')):
            self.assertTrue(event._dispatch_one())
        self.assertEqual(event.state, 'sent')
        self.assertEqual(event.http_status, 204)
        self.assertTrue(event.sent_at)

    def test_cron_dispatch_sends_due_events_and_never_raises(self):
        endpoint = self._endpoint('notify')
        Event = self.env['formula.integration.event']
        event = Event.enqueue(endpoint, 'x.created', {'a': 1}, 'cron-key')
        with self._post_patch(side_effect=RuntimeError('boom ' + TEST_SECRET_VALUE)) as post:
            processed = Event._cron_dispatch()
            self.assertEqual(processed, 1)
            post.assert_called_once()
        self.assertEqual(event.state, 'failed')
        self.assertNotIn(TEST_SECRET_VALUE, event.last_error)
        self.assertIn('***', event.last_error)

    def test_requeue_requires_failed_state(self):
        endpoint = self._endpoint('notify')
        event = self.env['formula.integration.event'].enqueue(endpoint, 'x.created', {'a': 1}, 'rq-key')
        with self._post_patch(return_value=(200, '{}')):
            event._dispatch_one()
        self.assertEqual(event.state, 'sent')
        event.action_requeue()
        self.assertEqual(event.state, 'sent')
        with self.assertRaises(UserError):
            self.env['formula.integration.endpoint'].create({
                'name': 'bad-lms-no-token', 'kind': 'lms', 'base_url': 'https://x.invalid/ws',
                'auth_method': 'none', 'secret_key': ''})._ensure_enabled()
