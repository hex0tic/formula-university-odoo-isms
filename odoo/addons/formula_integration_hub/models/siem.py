"""INT-04 SIEM: аюулгүй байдлын ҮЙЛ ЯВДЛЫН урсгал (login, incident, privileged group, MFA policy block).

Энэ нь university_isms_audit_chain.isms.audit.forward (аудит лог hash chain-ийн урсгал)-аас тусдаа.
* Нэвтрэлтийн IP хаяг HMAC-SHA256(pseudonym_key, ip) хэлбэрээр явна (түүхий IP байхгүй).
* Нэвтрэх нэр HMAC-аар (login_hash). Нэр, имэйл, дүн, инцидентийн гарчиг/тайлбар илгээгдэхгүй.
* Payload-ийн талбар бүр whitelist-ээр шүүгдэнэ.
* Зөвхөн enabled SIEM endpoint байгаа үед outbox-д мөр үүснэ.
* pseudonym_key нь ir.config_parameter-д анх удаа үүсгэгдэх ба tracked data-д орохгүй.
"""
import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timezone

from odoo import SUPERUSER_ID, _, api, models
from odoo.exceptions import AccessDenied

from odoo.addons.university_isms.models.audit import client_ip

_logger = logging.getLogger(__name__)

SIEM_SCHEMA = 'formula.security-event.v1'
EVENT_TYPES = (
    'login_success',
    'login_failed',
    'incident_created',
    'incident_escalated',
    'incident_state_changed',
    'privileged_group_change',
    'mfa_policy_block',
)
ATTRIBUTE_KEYS = (
    'severity', 'from_severity', 'to_severity', 'category', 'state', 'from_state', 'to_state',
    'groups_added', 'groups_removed', 'reason_code', 'mfa_method',
)
PRIVILEGED_XMLIDS = (
    'base.group_system',
    'base.group_erp_manager',
    'university_isms.group_isms_manager',
    'campus_university.group_campus_registrar',
)
PSEUDONYM_PARAM = 'formula_integration_hub.pseudonym_key'
SEVERITY_RANK = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}


def get_pseudonym_key(env):
    icp = env['ir.config_parameter'].sudo()
    key = icp.get_param(PSEUDONYM_PARAM)
    if not key:
        key = secrets.token_hex(32)
        icp.set_param(PSEUDONYM_PARAM, key)
    return key


def pseudonym(key, value):
    return hmac.new(key.encode('utf-8'), str(value).encode('utf-8'), hashlib.sha256).hexdigest()


def build_siem_payload(env, event_type, data):
    """Privacy-aware SIEM payload. Түүхий IP, нэвтрэх нэр, нэр, дүн агуулахгүй."""
    if event_type not in EVENT_TYPES:
        raise ValueError('Unknown SIEM event type: %s' % event_type)
    key = get_pseudonym_key(env)
    attributes = {}
    for name in ATTRIBUTE_KEYS:
        value = data.get(name)
        if value is None or value == '' or value == []:
            continue
        if isinstance(value, (list, tuple)):
            attributes[name] = [str(item)[:64] for item in value][:20]
        else:
            attributes[name] = str(value)[:64]
    login = data.get('login')
    ip = data.get('ip')
    user_id = data.get('user_id')
    record_id = data.get('record_id')
    return {
        'schema': SIEM_SCHEMA,
        'event_id': str(uuid.uuid4()),
        'event_type': event_type,
        'occurred_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': 'formula_integration_hub',
        'outcome': str(data.get('outcome') or '')[:16],
        'actor': {
            'user_id': int(user_id) if user_id else None,
            'login_hash': pseudonym(key, str(login).strip().lower()) if login else None,
            'ip_hmac': pseudonym(key, ip) if ip else None,
        },
        'object': {
            'model': str(data.get('model') or '')[:64],
            'record_id': int(record_id) if record_id else None,
            'ref': str(data.get('ref') or '')[:64],
        },
        'attributes': attributes,
    }


class FormulaIntegrationEventSiem(models.Model):
    _inherit = 'formula.integration.event'

    @api.model
    def _emit_siem(self, event_type, data):
        """SIEM endpoint бүрт outbox мөр үүсгэнэ. Идэвхтэй SIEM байхгүй бол юу ч хийхгүй."""
        endpoints = self.env['formula.integration.endpoint'].sudo().search([
            ('kind', '=', 'siem'), ('enabled', '=', True)])
        if not endpoints:
            return self.browse()
        payload = build_siem_payload(self.env, event_type, data)
        created = self.browse()
        for endpoint in endpoints:
            created |= self.enqueue(endpoint, 'siem.' + event_type, payload, payload['event_id'])
        return created

    @api.model
    def _safe_emit_siem(self, event_type, data):
        """Hook-ийн алдаа үндсэн үйлдлийг (нэвтрэлт, workflow) зогсоохгүй; savepoint-оор тусгаарлана."""
        try:
            with self.env.cr.savepoint():
                return self._emit_siem(event_type, data)
        except Exception:
            _logger.exception('SIEM emission failed for %s', event_type)
            return self.browse()


class ResUsersSiem(models.Model):
    _inherit = 'res.users'

    @classmethod
    def _login(cls, db, credential, user_agent_env):
        login = credential.get('login') if isinstance(credential, dict) else None
        try:
            auth_info = super()._login(db, credential, user_agent_env=user_agent_env)
        except AccessDenied:
            cls._formula_siem_login(login, False, None)
            raise
        cls._formula_siem_login(login, True, auth_info.get('uid'))
        return auth_info

    @classmethod
    def _formula_siem_login(cls, login, success, uid):
        """Нэвтрэлтийн үйл явдлыг тусдаа cursor-оор бичнэ (нэвтрэлт бүтэлгүйтсэн ч лог үлдэнэ)."""
        try:
            with cls.pool.cursor() as cr:
                cls._formula_siem_login_cr(cr, login, success, uid)
        except Exception:
            _logger.exception('SIEM login event failed')

    @classmethod
    def _formula_siem_login_cr(cls, cr, login, success, uid):
        env = api.Environment(cr, SUPERUSER_ID, {})
        env['formula.integration.event']._emit_siem(
            'login_success' if success else 'login_failed', {
                'login': login,
                'user_id': uid or False,
                'outcome': 'success' if success else 'failure',
                'ip': client_ip(),
            })

    def write(self, vals):
        if 'groups_id' not in vals:
            return super().write(vals)
        privileged = self.env['res.groups']
        for xmlid in PRIVILEGED_XMLIDS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                privileged |= group
        before = {user.id: user.groups_id & privileged for user in self.sudo()}
        res = super().write(vals)
        Event = self.env['formula.integration.event']
        for user in self.sudo():
            old = before.get(user.id, self.env['res.groups'])
            new = user.groups_id & privileged
            added, removed = new - old, old - new
            if added or removed:
                Event._safe_emit_siem('privileged_group_change', {
                    'user_id': user.id,
                    'login': user.login,
                    'outcome': 'change',
                    'ref': 'privileged',
                    'groups_added': added.mapped('name'),
                    'groups_removed': removed.mapped('name'),
                })
        return res


class IsmsIncidentSiem(models.Model):
    _inherit = 'isms.incident'

    def _formula_siem_incident_data(self):
        self.ensure_one()
        return {
            'user_id': self.env.uid,
            'login': self.env.user.login,
            'model': self._name,
            'record_id': self.id,
            'ref': self.code,
            'category': self.category,
            'severity': self.severity,
            'state': self.state,
            'outcome': 'success',
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        Event = self.env['formula.integration.event']
        for rec in records:
            Event._safe_emit_siem('incident_created', rec._formula_siem_incident_data())
        return records

    def write(self, vals):
        watched = {'state', 'severity'} & set(vals)
        before = {rec.id: (rec.state, rec.severity) for rec in self} if watched else {}
        res = super().write(vals)
        if not watched:
            return res
        Event = self.env['formula.integration.event']
        for rec in self:
            old_state, old_severity = before.get(rec.id, (None, None))
            if old_state is None:
                continue
            if rec.state != old_state:
                data = rec._formula_siem_incident_data()
                data.update({'from_state': old_state, 'to_state': rec.state})
                Event._safe_emit_siem('incident_state_changed', data)
            if SEVERITY_RANK.get(rec.severity, 0) > SEVERITY_RANK.get(old_severity, 0):
                data = rec._formula_siem_incident_data()
                data.update({'from_severity': old_severity, 'to_severity': rec.severity})
                Event._safe_emit_siem('incident_escalated', data)
        return res
