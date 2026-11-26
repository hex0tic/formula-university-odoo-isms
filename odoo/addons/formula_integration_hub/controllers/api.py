"""INT-05 JSON API: /api/formula/v1/... Bearer API key. CSRF хамааралгүй (cookie session ашиглахгүй)."""
import json

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request

from ..models.api_service import ApiAuthError, RateLimited

API_PREFIX = '/api/formula/v1'


def _json(payload, status=200, headers=None):
    return request.make_json_response(payload, status=status, headers=headers or [])


def _error(status, code, message, headers=None):
    return _json({'error': {'code': code, 'message': message}}, status=status, headers=headers)


class FormulaIntegrationApiController(http.Controller):

    def _handle(self, operation):
        service = request.env['formula.integration.api']
        if not service.api_endpoint():
            return _error(404, 'not_found', 'Ресурс олдсонгүй.')
        try:
            uid, key_id = service.authenticate(request.httprequest.headers.get('Authorization', ''))
            service.check_rate_limit(key_id)
            user_env = request.env(user=uid)
            data = operation(user_env['formula.integration.api'])
            return _json(data)
        except ApiAuthError:
            return _error(401, 'unauthorized', 'Хүчингүй эсвэл байхгүй API түлхүүр.',
                          [('WWW-Authenticate', 'Bearer')])
        except RateLimited as exc:
            return _error(429, 'rate_limited', 'Хүсэлтийн хязгаар хэтэрлээ.',
                          [('Retry-After', str(max(exc.retry_after, 1)))])
        except AccessError:
            return _error(403, 'forbidden', 'Энэ нөөцийг харах эрх байхгүй.')
        except (TypeError, ValueError, json.JSONDecodeError):
            return _error(400, 'bad_request', 'Буруу хүсэлт.')

    @http.route(API_PREFIX + '/ism/incidents/summary', type='http', auth='public',
                methods=['GET'], csrf=False)
    def incidents_summary(self, **kwargs):
        return self._handle(lambda svc: svc.incidents_summary())

    @http.route(API_PREFIX + '/campus/offerings', type='http', auth='public',
                methods=['GET'], csrf=False)
    def offerings(self, limit=100, **kwargs):
        return self._handle(lambda svc: svc.offerings(limit=limit))
