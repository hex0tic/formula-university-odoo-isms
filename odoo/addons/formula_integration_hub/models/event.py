"""Гаралтын дараалал (outbox): idempotency, exponential backoff, dead-letter, cron dispatcher."""
import json
import logging
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

from .transport import HttpTransport

_logger = logging.getLogger(__name__)

BACKOFF_BASE_SECONDS = 60
BACKOFF_CAP_SECONDS = 24 * 3600
DISPATCH_BATCH_SIZE = 100


def backoff_seconds(attempts):
    """Exponential backoff: 60s, 120s, 240s ... 24 цагаар хязгаарлагдана. attempts >= 1."""
    return min(BACKOFF_BASE_SECONDS * (2 ** max(attempts - 1, 0)), BACKOFF_CAP_SECONDS)


def commit_unless_test(env):
    # Unit test (TransactionCase) дотор хэзээ ч commit хийхгүй; production cron дээр алхам бүр commit.
    if not tools.config['test_enable']:
        env.cr.commit()


class FormulaIntegrationEvent(models.Model):
    _name = 'formula.integration.event'
    _description = 'Интеграцийн гаралтын дараалал (outbox)'
    _order = 'next_attempt_at, id'
    _rec_name = 'event_type'

    endpoint_id = fields.Many2one('formula.integration.endpoint', 'Endpoint', required=True,
                                  ondelete='cascade', index=True)
    kind = fields.Selection(related='endpoint_id.kind', store=True, readonly=True)
    event_type = fields.Char('Үйл явдал', required=True, index=True, readonly=True)
    idempotency_key = fields.Char('Idempotency түлхүүр', required=True, index=True, readonly=True)
    payload_json = fields.Text('Payload (JSON)', required=True, readonly=True)
    state = fields.Selection([
        ('pending', 'Хүлээгдэж буй'),
        ('sent', 'Илгээсэн'),
        ('failed', 'Дахин оролдох'),
        ('dead', 'Dead-letter (эцэслэн амжилтгүй)'),
    ], 'Төлөв', default='pending', required=True, index=True, readonly=True)
    attempts = fields.Integer('Оролдлого', default=0, readonly=True)
    max_attempts = fields.Integer('Дээд оролдлого', default=5, readonly=True)
    next_attempt_at = fields.Datetime('Дараагийн оролдлого', default=fields.Datetime.now,
                                      index=True, readonly=True)
    last_error = fields.Text('Сүүлийн алдаа', readonly=True)
    http_status = fields.Integer('HTTP статус', readonly=True)
    sent_at = fields.Datetime('Илгээсэн огноо', readonly=True)

    _sql_constraints = [
        ('endpoint_key_uniq', 'unique(endpoint_id, idempotency_key)',
         'Энэ idempotency түлхүүр аль хэдийн дараалалд байна.'),
    ]

    @api.model
    def enqueue(self, endpoint, event_type, payload, idempotency_key):
        """Дараалалд нэмнэ. Унтраалттай endpoint бол юу ч үүсгэхгүй (хоосон бичлэг буцаана).
        Ижил idempotency түлхүүр байвал шинэ мөр үүсгэхгүй, байгаа мөрийг буцаана."""
        if not endpoint.enabled:
            return self.browse()
        if not idempotency_key:
            raise UserError(_('Idempotency түлхүүр заавал.'))
        existing = self.sudo().search([('endpoint_id', '=', endpoint.id),
                                       ('idempotency_key', '=', idempotency_key)], limit=1)
        if existing:
            return existing
        body = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
        vals = {
            'endpoint_id': endpoint.id,
            'event_type': event_type,
            'idempotency_key': idempotency_key,
            'payload_json': body,
            'state': 'pending',
            'attempts': 0,
            'max_attempts': endpoint.max_attempts or 5,
            'next_attempt_at': fields.Datetime.now(),
        }
        try:
            with self.env.cr.savepoint():
                return self.sudo().create(vals)
        except IntegrityError:
            # Зэрэгцээ хүсэлтэд давхардсан үед дахин уншина
            return self.sudo().search([('endpoint_id', '=', endpoint.id),
                                       ('idempotency_key', '=', idempotency_key)], limit=1)

    def _dispatch_one(self):
        """Нэг мөрийг илгээнэ. Алдааг хэзээ ч дээш шидэхгүй; төлөв, оролдлого, алдааг бүртгэнэ."""
        self.ensure_one()
        endpoint = self.endpoint_id.sudo()
        if self.state in ('sent', 'dead') or not endpoint.enabled:
            return False
        now = fields.Datetime.now()
        status, body_text, ok, error = None, '', False, ''
        try:
            request_parts = HttpTransport.prepare(endpoint, self)
            status, body_text = HttpTransport.post(request_parts)
            ok = HttpTransport.is_success(endpoint, status, body_text)
            if not ok:
                hint = HttpTransport.error_hint(body_text)
                error = 'HTTP %s %s' % (status, hint)
        except Exception as exc:  # сүлжээ/тохиргооны алдаа: бүртгэнэ, дахин оролдоно
            error = '%s: %s' % (type(exc).__name__, exc)
        attempts = (self.attempts or 0) + 1
        vals = {'attempts': attempts, 'http_status': int(status or 0)}
        if ok:
            vals.update({'state': 'sent', 'sent_at': now, 'last_error': False})
        else:
            error = endpoint._redact(error)
            if attempts >= (self.max_attempts or 1):
                vals.update({'state': 'dead', 'last_error': error})
            else:
                vals.update({
                    'state': 'failed',
                    'last_error': error,
                    'next_attempt_at': now + timedelta(seconds=backoff_seconds(attempts)),
                })
        self.sudo().write(vals)
        if ok:
            self._after_delivery(endpoint, body_text)
        return ok

    def _after_delivery(self, endpoint, body_text):
        """Амжилттай илгээсний дараах холбоос (LMS mapping). Алдаа гарсан ч илгээлтийг буцаахгүй."""
        if endpoint.kind != 'lms':
            return
        try:
            with self.env.cr.savepoint():
                self.env['formula.moodle.adapter'].after_delivery(endpoint, self, body_text)
        except Exception:
            _logger.exception('Integration event %s: post-delivery mapping failed', self.id)

    @api.model
    def _cron_dispatch(self, batch_size=DISPATCH_BATCH_SIZE):
        """Cron entry point. Хэзээ ч exception шидэхгүй; мөр бүр тусдаа хамгаалагдана."""
        processed = 0
        try:
            candidates = self.sudo().search([
                ('state', 'in', ['pending', 'failed']),
                ('next_attempt_at', '<=', fields.Datetime.now()),
                ('endpoint_id.enabled', '=', True),
            ], limit=batch_size)
            if not candidates:
                return 0
            # Олон worker зэрэг ажиллахад нэг мөрийг хоёр удаа илгээхгүй
            self.env.cr.execute(
                'SELECT id FROM formula_integration_event WHERE id IN %s FOR UPDATE SKIP LOCKED',
                [tuple(candidates.ids)])
            locked = [row[0] for row in self.env.cr.fetchall()]
            events = self.sudo().browse(locked)
        except Exception:
            _logger.exception('Integration dispatcher: could not load outbox batch')
            return 0
        for event in events:
            try:
                with self.env.cr.savepoint():
                    event._dispatch_one()
                processed += 1
            except Exception:
                _logger.exception('Integration dispatcher: event %s failed', event.id)
            try:
                commit_unless_test(self.env)
            except Exception:
                _logger.exception('Integration dispatcher: commit failed')
        return processed

    def action_requeue(self):
        """Dead-letter эсвэл алдаатай мөрийг админ дахин дараалалд оруулна."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.state in ('failed', 'dead'):
                rec.write({'state': 'pending', 'attempts': 0, 'next_attempt_at': now, 'last_error': False})
        return True
