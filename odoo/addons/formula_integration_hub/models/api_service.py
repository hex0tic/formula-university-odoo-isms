"""INT-05 API service. Контроллер нимгүй логикийг энд хийж тестлэнэ.

* Аутентификаци: Authorization: Bearer <Odoo API key>. Түлхүүрийн хайлт л sudo; бусад бүх унших
  үйлдэл дуудагчийн env (request.env(user=uid)) дээр, record rule/ACL-ээр явна.
* Rate limit: процесс доторх token bucket (key бүрт). Түлхүүрийн raw утгыг санах ойд хадгалахгүй
  (sha256 prefix ашиглана). Олон worker бол хязгаар worker тус бүрт тусдаа (документд тэмдэглэсэн).
* Идэвхгүй (feature flag унтраалттай, эсвэл api endpoint байхгүй) бол контроллер 404 буцаана.
"""
import hashlib
import logging
import math
import threading
import time

from odoo import api, models

_logger = logging.getLogger(__name__)

DEFAULT_CAPACITY = 60
DEFAULT_REFILL_PER_MINUTE = 60
MAX_BUCKETS = 10000
_LOCK = threading.Lock()
_BUCKETS = {}


class ApiAuthError(Exception):
    pass


class RateLimited(Exception):
    def __init__(self, retry_after):
        super().__init__('rate limited')
        self.retry_after = retry_after


def take_token(key_id, capacity, refill_per_minute, now=None):
    """Token bucket. Буцаах утга: (зөвшөөрсөн эсэх, дахин оролдох хүртэлх секунд)."""
    now = time.monotonic() if now is None else now
    rate = max(refill_per_minute, 1) / 60.0
    capacity = max(int(capacity), 1)
    with _LOCK:
        if len(_BUCKETS) > MAX_BUCKETS:
            _BUCKETS.clear()
        tokens, last = _BUCKETS.get(key_id, (float(capacity), now))
        tokens = min(float(capacity), tokens + max(now - last, 0.0) * rate)
        if tokens >= 1.0:
            _BUCKETS[key_id] = (tokens - 1.0, now)
            return True, 0
        _BUCKETS[key_id] = (tokens, now)
        return False, int(math.ceil((1.0 - tokens) / rate))


class FormulaIntegrationApi(models.AbstractModel):
    _name = 'formula.integration.api'
    _description = 'Интеграцийн API үйлчилгээ'

    @api.model
    def api_endpoint(self):
        """Идэвхтэй API endpoint (feature flag). Байхгүй бол хоосон."""
        return self.env['formula.integration.endpoint'].sudo().search(
            [('kind', '=', 'api'), ('enabled', '=', True)], limit=1)

    @api.model
    def authenticate(self, authorization_header):
        """Bearer API key → (uid, key_id). Буруу бол ApiAuthError."""
        header = authorization_header or ''
        if not header.startswith('Bearer '):
            raise ApiAuthError('missing bearer token')
        token = header[len('Bearer '):].strip()
        if not token or len(token) > 256:
            raise ApiAuthError('invalid token')
        uid = self.env['res.users.apikeys'].sudo()._check_credentials(scope='rpc', key=token)
        if not uid:
            raise ApiAuthError('invalid token')
        key_id = hashlib.sha256(token.encode('utf-8')).hexdigest()[:24]
        return uid, key_id

    def _rate_settings(self):
        icp = self.env['ir.config_parameter'].sudo()
        try:
            capacity = int(icp.get_param('formula_integration_hub.api_rate_capacity', DEFAULT_CAPACITY))
        except (TypeError, ValueError):
            capacity = DEFAULT_CAPACITY
        try:
            refill = int(icp.get_param('formula_integration_hub.api_rate_per_minute', DEFAULT_REFILL_PER_MINUTE))
        except (TypeError, ValueError):
            refill = DEFAULT_REFILL_PER_MINUTE
        return capacity, refill

    @api.model
    def check_rate_limit(self, key_id):
        capacity, refill = self._rate_settings()
        allowed, retry_after = take_token(key_id, capacity, refill)
        if not allowed:
            raise RateLimited(retry_after)

    @api.model
    def incidents_summary(self):
        """Тоо, дүгнэлт. Дуудагчийн эрхээр (record rule-тай). Эрхгүй бол AccessError."""
        Incident = self.env['isms.incident']
        Incident.check_access('read')
        states = [code for code, _label in Incident._fields['state'].selection]
        severities = [code for code, _label in Incident._fields['severity'].selection]
        return {
            'total': Incident.search_count([]),
            'by_state': {code: Incident.search_count([('state', '=', code)]) for code in states},
            'by_severity': {code: Incident.search_count([('severity', '=', code)]) for code in severities},
        }

    @api.model
    def offerings(self, limit=100):
        """Хичээлийн бүлгийн жагсаалт. Багшийн нэр/имэйл гаргахгүй."""
        Offering = self.env['campus.offering']
        Offering.check_access('read')
        try:
            limit = min(max(int(limit), 1), 200)
        except (TypeError, ValueError):
            limit = 100
        rows = Offering.search([], limit=limit, order='id')
        return [{
            'id': row.id,
            'code': row.course_id.code,
            'name': row.name,
            'semester': row.semester,
            'state': row.state,
        } for row in rows]
