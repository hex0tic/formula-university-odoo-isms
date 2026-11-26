"""Аудит гинжийн багцлан дамжуулалт (ISO/IEC 27001:2022 A.8.15, A.5.28).

Дамжуулах зорилт (ir.config_parameter, prefix `university_isms_audit_chain.`):
* file_path   - JSONL файлын абсолют зам (жишээ: /var/log/odoo/audit-chain.jsonl). Хоосон бол идэвхгүй.
* http_url    - https:// endpoint. Хоосон бол идэвхгүй. http:// зөвхөн allow_insecure_http=True үед.
* http_token  - нэмэлт Bearer токен (нууц; хэзээ ч лог, UI-д хэвлэхгүй).

Дамжуулалтын зарчим:
* Багц (batch) бүр тасралтгүй seq мужийг хамарна. Багцын `head_hash` нь мужийн сүүлийн
  бичлэгийн entry_hash. Энэ нь HTTP-ийн Idempotency-Key ба JSONL файлын давхардлын түлхүүр.
* Багцын payload нь canonical JSON-ийн SHA-256 (`payload_digest`)-тэй. Илгээхээс өмнө дахин тооцоолж
  харьцуулна: бичлэг өөрчлөгдсөн эсвэл алга болсон бол илгээхгүй, алдаа гэж бүртгэнэ.
* Нэг зорилтод багцууд дарааллаар (seq_from өсөхөөр) илгээгдэнэ. Өмнөх багц илгээгдээгүй бол дараагийнх эхлэхгүй.
* Зөвхөн илгээсэн багцын сүүлийн seq курсорт бичигдэнэ (isms.audit.chain.head).
* IP хаяг гадагш илгээгдэхгүй: HMAC-SHA256(түлхүүр, IP) хэлбэрээр явна. Түлхүүр нь DB дотор
  байдаг тул DB администратор үүнийг тооцоолж чадна (хязгаарлалт).
* Гадаад систем гинжийг бүрэн дахин тооцоолохгүй (IP-ийн түүхий утга хэрэгтэй). Тэр системд
  seq, prev_hash, entry_hash-ээр холбоос, гэрчлэгдсэн толгойн хэш хадгалагдана.
"""
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import timedelta

import requests

from odoo import api, fields, models, tools
from odoo.exceptions import AccessError

from .audit_chain import canonical_char, canonical_int, canonical_text, canonical_ts

_logger = logging.getLogger(__name__)

PARAM_PREFIX = 'university_isms_audit_chain.'
GROUP_MANAGER = 'university_isms.group_isms_manager'
GROUP_SYSTEM = 'base.group_system'
CURSOR_FIELD = {'file': 'forward_file_seq', 'http': 'forward_http_seq'}
STATE_PENDING, STATE_SENT, STATE_FAILED = 'pending', 'sent', 'failed'
DEFAULTS = {
    'http_timeout': 10,
    'http_max_retries': 3,
    'http_backoff_seconds': 2,
    'batch_size': 500,
    'max_batches_per_run': 10,
    'max_attempts': 50,
    'retention_days': 365,
}


class ForwardError(Exception):
    """Багц илгээх алдаа. `attempts` нь энэ удаагийн оролдлогын тоо."""

    def __init__(self, message, attempts=1):
        super().__init__(message)
        self.attempts = attempts


def get_setting(env, key, default=''):
    value = env['ir.config_parameter'].sudo().get_param(PARAM_PREFIX + key, False)
    return value if value not in (False, None, '') else default


def get_int_setting(env, key):
    default = DEFAULTS[key]
    try:
        return int(get_setting(env, key, default))
    except (TypeError, ValueError):
        return default


def _short(text, limit=500):
    return (text or '')[:limit]


def _commit(env):
    # Тест (test_enable) дээр гүйлгээг хэзээ ч commit хийхгүй; production cron дээр багц бүр commit.
    if not tools.config['test_enable']:
        env.cr.commit()


def ip_digest(ip, key):
    if not ip:
        return ''
    return hmac.new(key.encode('utf-8'), ip.encode('utf-8'), hashlib.sha256).hexdigest()


def batch_digest(entries):
    blob = json.dumps(entries, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def batch_line(seq_from, seq_to, entries, digest):
    body = {
        'type': 'audit_chain_batch',
        'source': 'university_isms_audit_chain',
        'seq_from': seq_from,
        'seq_to': seq_to,
        'entry_count': len(entries),
        'head_hash': entries[-1]['entry_hash'],
        'payload_digest': digest,
        'entries': entries,
    }
    return json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class IsmsAuditForward(models.Model):
    _name = 'isms.audit.forward'
    _description = 'ISMS аудит гинжийн дамжуулах дараалал'
    _order = 'target, seq_from'
    _sql_constraints = [
        ('isms_audit_forward_target_seq_uniq', 'UNIQUE(target, seq_to)',
         'Нэг зорилтод нэг багц л давхардахгүй байна.'),
    ]

    name = fields.Char('Багц', compute='_compute_name', store=True)
    target = fields.Selection([('file', 'Локал JSONL файл'), ('http', 'HTTP(S) endpoint')],
                              string='Зорилт', required=True, readonly=True, index=True)
    seq_from = fields.Integer('Эхлэх seq', readonly=True)
    seq_to = fields.Integer('Дуусах seq', readonly=True)
    entry_count = fields.Integer('Бичлэгийн тоо', readonly=True)
    head_hash = fields.Char('Толгойн хэш (идемпотент түлхүүр)', readonly=True)
    payload_digest = fields.Char('Payload хэш (SHA-256)', readonly=True)
    state = fields.Selection([(STATE_PENDING, 'Хүлээгдэж буй'), (STATE_SENT, 'Илгээсэн'),
                              (STATE_FAILED, 'Амжилтгүй')],
                             string='Төлөв', default=STATE_PENDING, readonly=True, index=True)
    attempts = fields.Integer('Оролдлогын тоо', default=0, readonly=True)
    last_error = fields.Text('Сүүлийн алдаа', readonly=True)
    sent_at = fields.Datetime('Илгээсэн огноо', readonly=True)
    created_at = fields.Datetime('Үүсгэсэн огноо', default=fields.Datetime.now, readonly=True)

    @api.depends('target', 'seq_from', 'seq_to')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s %s-%s' % (rec.target or '', rec.seq_from or 0, rec.seq_to or 0)

    # ------------------------------------------------------------ access
    def _check_forward_access(self):
        user = self.env.user
        if not (user.has_group(GROUP_MANAGER) or user.has_group(GROUP_SYSTEM)):
            raise AccessError(('Дамжуулалтыг удирдах эрх зөвхөн CISO эсвэл системийн админд байна.'))

    # ------------------------------------------------------------ settings helpers
    def _ip_key(self):
        icp = self.env['ir.config_parameter'].sudo()
        key = icp.get_param(PARAM_PREFIX + 'ip_hmac_key')
        if not key:
            key = secrets.token_hex(32)
            icp.set_param(PARAM_PREFIX + 'ip_hmac_key', key)
        return key

    @api.model
    def _configured_targets(self):
        targets = []
        if get_setting(self.env, 'file_path'):
            targets.append('file')
        if get_setting(self.env, 'http_url'):
            targets.append('http')
        return targets

    # ------------------------------------------------------------ batching
    def _load_entries(self, seq_from, seq_to):
        """Гинжийн мужийг IP-гүй (HMAC-тай) бичлэгүүд болгон уншина."""
        key = self._ip_key()  # before the query: it runs its own SQL and would reset the cursor result
        cr = self.env.cr
        cr.execute("""
            SELECT seq, timestamp, user_id, login, action, model, res_id, res_name,
                   changes, ip_address, prev_hash, entry_hash
              FROM isms_audit_log
             WHERE seq BETWEEN %s AND %s
             ORDER BY seq
        """, (seq_from, seq_to))
        columns = [col[0] for col in cr.description]
        entries = []
        for values in cr.fetchall():
            row = dict(zip(columns, values))
            entries.append({
                'seq': canonical_int(row['seq']),
                'timestamp': canonical_ts(row['timestamp']),
                'user_id': canonical_int(row['user_id']),
                'login': canonical_char(row['login']),
                'action': canonical_char(row['action']),
                'model': canonical_char(row['model']),
                'res_id': canonical_int(row['res_id']),
                'res_name': canonical_char(row['res_name']),
                'changes': canonical_text(row['changes']),
                'ip_hmac': ip_digest(canonical_char(row['ip_address']), key),
                'prev_hash': canonical_char(row['prev_hash']),
                'entry_hash': canonical_char(row['entry_hash']),
            })
        return entries

    @api.model
    def _next_open_batch(self, target):
        return self.sudo().search([('target', '=', target), ('state', '!=', STATE_SENT)],
                                  order='seq_from', limit=1)

    @api.model
    def _enqueue_next(self, target):
        """Курсороос хойш дараагийн багцыг үүсгэнэ. Нэмэгдэх зүйл байхгүй бол False."""
        head = self.env['isms.audit.chain.head'].sudo().search([], order='id', limit=1)
        if not head:
            return False
        cursor = head.forward_seq(target)
        if head.last_seq <= cursor:
            return False
        size = max(1, get_int_setting(self.env, 'batch_size'))
        upper = min(head.last_seq, cursor + size)
        entries = self._load_entries(cursor + 1, upper)
        found = [entry['seq'] for entry in entries]
        if found != list(range(cursor + 1, upper + 1)):
            self.sudo().create({
                'target': target, 'seq_from': cursor + 1, 'seq_to': upper,
                'entry_count': len(entries), 'state': STATE_FAILED, 'attempts': 0,
                'last_error': _short('Гинжийн завсарлага: курсор=%s, хүрэх=%s, олдсон=%s (хамгаалалтын асуудал магадгүй).'
                                     % (cursor, upper, found[:5] + (['...'] if len(found) > 5 else []))),
            })
            return True
        self.sudo().create({
            'target': target, 'seq_from': cursor + 1, 'seq_to': upper,
            'entry_count': len(entries), 'head_hash': entries[-1]['entry_hash'],
            'payload_digest': batch_digest(entries), 'state': STATE_PENDING,
        })
        return True

    # ------------------------------------------------------------ delivery
    def _deliver(self):
        """Нэг багцыг илгээнэ. Амжилтгүй бол ForwardError (attempts-тай) шидэнэ."""
        self.ensure_one()
        if not self.payload_digest or not self.head_hash:
            raise ForwardError(self.last_error or 'Багцын хэш тооцоолоогүй байна.')
        entries = self._load_entries(self.seq_from, self.seq_to)
        if (not entries or len(entries) != self.entry_count
                or batch_digest(entries) != self.payload_digest
                or entries[-1]['entry_hash'] != self.head_hash):
            raise ForwardError(('Аудит бичлэг өөрчлөгдсөн эсвэл алга болсон: багцын хэш таарахгүй байна.'))
        line = batch_line(self.seq_from, self.seq_to, entries, self.payload_digest)
        if self.target == 'file':
            attempts = 1
            self._write_file(get_setting(self.env, 'file_path'), line, self.head_hash)
        else:
            attempts = self._post_http(get_setting(self.env, 'http_url'), line, self.head_hash)
        self.write({'state': STATE_SENT, 'sent_at': fields.Datetime.now(),
                    'attempts': self.attempts + attempts, 'last_error': False})
        head = self.env['isms.audit.chain.head'].sudo().search([], order='id', limit=1)
        head.write({CURSOR_FIELD[self.target]: self.seq_to})

    def _write_file(self, path, line, head_hash):
        """JSONL-д нэг мөр нэмнэ. Аль хэдийн байгаа head_hash-тай бол дахин бичихгүй (идемпотент).

        Буцаах: шинээр бичсэн эсэх.
        """
        if not path or not os.path.isabs(path):
            raise ForwardError(('Файлын зам абсолют байх ёстой.'))
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        marker = '"head_hash":"%s"' % head_hash
        if os.path.exists(path):
            with open(path, encoding='utf-8') as handle:
                if marker in handle.read():
                    return False
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(line + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        return True

    def _http_post(self, url, body, headers, timeout):
        """HTTP POST. Тестэд mock хийгдэх цэг. Буцаах: HTTP статус код."""
        response = requests.post(url, data=body, headers=headers, timeout=timeout)
        return response.status_code

    def _post_http(self, url, line, head_hash):
        """Retry + backoff. Буцаах: оролдлогын тоо. Бүх оролдлого бүтэлгүйтвэл ForwardError."""
        if not url:
            raise ForwardError(('HTTP endpoint тохируулаагүй.'), attempts=0)
        insecure = get_setting(self.env, 'allow_insecure_http') in ('1', 'True', 'true')
        if not url.startswith('https://') and not (insecure and url.startswith('http://')):
            raise ForwardError(('Зөвхөн https endpoint зөвшөөрнө.'))
        headers = {
            'Content-Type': 'application/json',
            'Idempotency-Key': head_hash,
            'User-Agent': 'university-isms-audit-chain',
        }
        token = get_setting(self.env, 'http_token')
        if token:
            headers['Authorization'] = 'Bearer %s' % token
        timeout = get_int_setting(self.env, 'http_timeout')
        retries = max(0, get_int_setting(self.env, 'http_max_retries'))
        backoff = max(0, get_int_setting(self.env, 'http_backoff_seconds'))
        body = line.encode('utf-8')
        last_error, attempts = '', 0
        for index in range(retries + 1):
            attempts += 1
            try:
                status = self._http_post(url, body, headers, timeout)
                if 200 <= status < 300 or status == 409:  # 409: аль хэдийн хүлээж авсан (идемпотент)
                    return attempts
                last_error = 'HTTP %s' % status
            except Exception as exc:  # noqa: BLE001 - алдааг багцад бүртгэнэ
                last_error = '%s: %s' % (type(exc).__name__, exc)
            last_error = last_error.replace(url, '<endpoint>')
            if index < retries and backoff:
                time.sleep(backoff * 2 ** index)
        raise ForwardError(_short(('HTTP илгээх амжилтгүй: %s') % last_error), attempts=attempts)

    def _record_failure(self, batch_id, exc):
        batch = self.browse(batch_id).sudo()
        attempts = getattr(exc, 'attempts', 1)
        batch.write({'state': STATE_FAILED, 'attempts': batch.attempts + attempts,
                     'last_error': _short('%s' % exc)})

    def _deliver_safely(self, batch_id):
        """Нэг багцыг savepoint дотор илгээнэ. Буцаах: амжилттай эсэх. Ямар ч алдаа дахин шидэхгүй."""
        try:
            with self.env.cr.savepoint():
                self.browse(batch_id).sudo()._deliver()
            return True
        except ForwardError as exc:
            _logger.warning('Audit chain batch %s not delivered: %s', batch_id, exc)
            self._record_failure(batch_id, exc)
        except Exception as exc:  # noqa: BLE001
            _logger.exception('Audit chain batch %s failed', batch_id)
            self._record_failure(batch_id, ForwardError(_short('%s: %s' % (type(exc).__name__, exc))))
        return False

    def _forward_target(self, target):
        max_batches = max(1, get_int_setting(self.env, 'max_batches_per_run'))
        max_attempts = max(1, get_int_setting(self.env, 'max_attempts'))
        for _index in range(max_batches):
            batch = self._next_open_batch(target)
            if not batch:
                try:
                    with self.env.cr.savepoint():
                        created = self._enqueue_next(target)
                except Exception:  # noqa: BLE001
                    _logger.exception('Audit chain batch could not be queued (%s)', target)
                    return
                if not created:
                    return
                _commit(self.env)
                continue
            if batch.attempts >= max_attempts:
                _logger.error('Audit chain batch %s reached max attempts; manual retry required', batch.id)
                return
            sent = self._deliver_safely(batch.id)
            _commit(self.env)
            if not sent:
                return

    @api.model
    def _forward_all(self):
        for target in self._configured_targets():
            self._forward_target(target)
        return True

    @api.model
    def _purge_sent(self):
        """Хадгалалтын бодлого: илгээсэн багцын дарааллын мөрийг retention_days-ээс хойш устгана.

        Аудит бичлэг (isms_audit_log) хэзээ ч энэ аргаар устахгүй. days <= 0 бол хадгална.
        """
        days = get_int_setting(self.env, 'retention_days')
        if days <= 0:
            return 0
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.sudo().search([('state', '=', STATE_SENT), ('sent_at', '<', cutoff)])
        count = len(old)
        old.unlink()
        return count

    @api.model
    def _cron_forward_chain(self):
        """Cron (15 минут): хэзээ ч exception шидэхгүй."""
        try:
            self._forward_all()
        except Exception:  # noqa: BLE001
            _logger.exception('Audit chain forwarding cron failed')
        try:
            self._purge_sent()
        except Exception:  # noqa: BLE001
            _logger.exception('Audit chain retention cron failed')
        return True

    @api.model
    def action_run_forward(self):
        self._check_forward_access()
        self._forward_all()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': ('Аудит гинжийн дамжуулалт'),
                       'message': ('Дамжуулалтын дараалал боловсрууллаа.'),
                       'type': 'info', 'sticky': False},
        }

    def action_retry(self):
        self._check_forward_access()
        self.sudo().filtered(lambda rec: rec.state != STATE_SENT).write(
            {'state': STATE_PENDING, 'attempts': 0, 'last_error': False})
        return True
