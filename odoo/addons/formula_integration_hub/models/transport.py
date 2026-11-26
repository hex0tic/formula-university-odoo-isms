"""Залгах транспорт. Тестүүд `HttpTransport.post`-ыг mock хийнэ; тестэд сүлжээний дуудлага байхгүй."""
import json
import logging

import requests

from odoo import _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
ERP_META_KEY = 'erp_refs'  # дотоод холбоосын мэдээлэл; гадагш хэзээ ч илгээхгүй
USER_AGENT = 'formula-integration-hub/18.0'
MAX_RESPONSE_CHARS = 20000


def flatten_moodle_params(value, prefix, out):
    """Moodle REST форматад тохирох: {'courses': [{'a': 1}]} -> courses[0][a]=1."""
    if isinstance(value, dict):
        for key, item in value.items():
            flatten_moodle_params(item, '%s[%s]' % (prefix, key), out)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            flatten_moodle_params(item, '%s[%d]' % (prefix, index), out)
    elif value is None:
        return out
    elif isinstance(value, bool):
        out[prefix] = int(value)
    else:
        out[prefix] = value
    return out


class HttpTransport(object):

    @classmethod
    def prepare(cls, endpoint, event):
        """Илгээх хүсэлтийг бэлдэнэ (сүлжээ дуудахгүй). Нууц зөвхөн header/form-д байна."""
        if not endpoint.base_url:
            raise UserError(_('Суурь URL тохируулаагүй байна.'))
        secret = endpoint.get_secret() if endpoint.auth_method != 'none' or endpoint.kind == 'lms' else None
        if endpoint.kind == 'lms' and not secret:
            raise UserError(_('LMS токен олдсонгүй (лавлагаа: %s).') % endpoint.secret_key)
        if endpoint.auth_method != 'none' and not secret:
            raise UserError(_('Нууцын утга олдсонгүй (лавлагаа: %s).') % endpoint.secret_key)
        body = json.loads(event.payload_json or '{}')
        body.pop(ERP_META_KEY, None)
        timeout = endpoint.timeout_seconds or DEFAULT_TIMEOUT
        headers = {'User-Agent': USER_AGENT, 'X-Formula-Event': event.event_type}
        if endpoint.kind == 'lms':
            # Moodle REST: wsfunction + wstoken form параметр. Moodle idempotency-key дэмждэггүй тул
            # давхардлыг дотоод mapping/idempotency түлхүүрээр хамгаална.
            form = {'wsfunction': body.get('wsfunction'), 'moodlewsrestformat': 'json', 'wstoken': secret}
            for key, value in (body.get('params') or {}).items():
                flatten_moodle_params(value, str(key), form)
            return {'url': endpoint.base_url, 'headers': headers, 'form': form, 'data': None,
                    'timeout': timeout}
        headers['Content-Type'] = 'application/json'
        headers['Idempotency-Key'] = event.idempotency_key
        if endpoint.auth_method == 'bearer':
            headers['Authorization'] = 'Bearer %s' % secret
        elif endpoint.auth_method == 'header':
            headers[endpoint.header_name or 'X-API-Key'] = secret
        data = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        return {'url': endpoint.base_url, 'headers': headers, 'form': None, 'data': data, 'timeout': timeout}

    @classmethod
    def post(cls, request):
        """Хүсэлт илгээж (status_code, body_text) буцаана. Сүлжээний алдаа exception болж дээш гарна."""
        kwargs = {'headers': request['headers'], 'timeout': request['timeout'], 'allow_redirects': False}
        if request['form'] is not None:
            response = requests.post(request['url'], data=request['form'], **kwargs)
        else:
            response = requests.post(request['url'], data=request['data'], **kwargs)
        return response.status_code, (response.text or '')[:MAX_RESPONSE_CHARS]

    @classmethod
    def is_success(cls, endpoint, status, body_text):
        """2xx төдийгүй LMS-ийн хувьд Moodle 200 + exception JSON-ийг алдаа гэж үзнэ."""
        try:
            status = int(status or 0)
        except (TypeError, ValueError):
            return False
        if not 200 <= status < 300:
            return False
        if endpoint.kind != 'lms':
            return True
        try:
            data = json.loads(body_text or '')
        except ValueError:
            return False
        if isinstance(data, dict) and 'exception' in data:
            return False
        return isinstance(data, (list, dict))

    @classmethod
    def error_hint(cls, body_text):
        """Moodle errorcode гэх мэт богино, нууцгүй тайлбар."""
        try:
            data = json.loads(body_text or '')
        except ValueError:
            return ''
        if isinstance(data, dict):
            return str(data.get('errorcode') or data.get('exception') or '')[:60]
        return ''
