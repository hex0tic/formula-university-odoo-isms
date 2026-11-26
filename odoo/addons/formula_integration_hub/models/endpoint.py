"""Интеграцийн endpoint: feature flag, суурь URL, нууцын ЛАВЛАГАА (утга хадгалахгүй)."""
import logging
import os
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 500
_PARAM_KEY_RE = re.compile(r'^[a-z0-9_.]{1,128}$')
_ENV_KEY_RE = re.compile(r'^[A-Z][A-Z0-9_]{0,127}$')

KIND_SELECTION = [
    ('sso', 'SSO (OIDC)'),
    ('lms', 'LMS (Moodle)'),
    ('notify', 'Мэдэгдэл'),
    ('siem', 'SIEM'),
    ('api', 'API'),
]
AUTH_SELECTION = [
    ('none', 'Нууцлалгүй'),
    ('bearer', 'Bearer токен'),
    ('header', 'Тусгай header'),
]
SECRET_SOURCE_SELECTION = [
    ('param', 'ir.config_parameter түлхүүр'),
    ('env', 'Орчны хувьсагч'),
]


class FormulaIntegrationEndpoint(models.Model):
    _name = 'formula.integration.endpoint'
    _description = 'Интеграцийн тохиргоо (endpoint)'
    _order = 'kind, name'

    name = fields.Char('Нэр', required=True)
    kind = fields.Selection(KIND_SELECTION, 'Төрөл', required=True)
    enabled = fields.Boolean(
        'Идэвхтэй (feature flag)', default=False,
        help='Унтраалттай үед дараалал илгээгдэхгүй, API 404 буцаана. Анхдагчаар унтраалттай.')
    base_url = fields.Char('Суурь URL (https)')
    auth_method = fields.Selection(AUTH_SELECTION, 'Нэвтрэлтийн арга', default='none', required=True)
    header_name = fields.Char('Header нэр', default='X-API-Key')
    secret_source = fields.Selection(SECRET_SOURCE_SELECTION, 'Нууцын эх сурвалж',
                                     default='param', required=True)
    secret_key = fields.Char(
        'Нууцын лавлагаа (утга биш)',
        help='ir.config_parameter түлхүүрийн нэр эсвэл орчны хувьсагчийн нэр. Нууцын утгыг энд оруулахгүй.')
    issuer = fields.Char('OIDC issuer')
    client_id = fields.Char('Client ID')
    allowed_domains = fields.Char('Зөвшөөрөгдсөн домэйн (таслалаар)')
    timeout_seconds = fields.Integer('Timeout (сек)', default=10)
    max_attempts = fields.Integer('Дээд оролдлого', default=5)
    note = fields.Text('Тайлбар')
    group_rule_ids = fields.One2many('formula.sso.group.rule', 'endpoint_id', 'SSO бүлгийн дүрэм')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Endpoint-ийн нэр давхардсан байна.'),
        ('timeout_range', 'check(timeout_seconds between 1 and 60)', 'Timeout 1-60 секунд байна.'),
        ('attempts_range', 'check(max_attempts between 1 and 20)', 'Оролдлого 1-20 байна.'),
    ]

    @api.constrains('base_url')
    def _check_base_url(self):
        for rec in self:
            if rec.base_url and not rec.base_url.startswith('https://'):
                raise ValidationError(_('Суурь URL нь https:// -ээр эхлэх ёстой.'))

    @api.constrains('secret_source', 'secret_key')
    def _check_secret_key(self):
        for rec in self:
            if not rec.secret_key:
                continue
            pattern = _ENV_KEY_RE if rec.secret_source == 'env' else _PARAM_KEY_RE
            if not pattern.match(rec.secret_key):
                raise ValidationError(_(
                    'Нууцын лавлагааны формат буруу. Зөвхөн түлхүүрийн нэрийг оруулна, утгыг оруулахгүй.'))

    @api.constrains('enabled', 'kind', 'issuer', 'client_id', 'allowed_domains')
    def _check_sso_ready(self):
        for rec in self:
            if rec.enabled and rec.kind == 'sso' and not (rec.issuer and rec.client_id and rec.allowed_domains):
                raise ValidationError(_(
                    'SSO-г идэвхжүүлэхийн өмнө issuer, client ID, зөвшөөрөгдсөн домэйныг бөглөнө.'))

    def get_secret(self):
        """Нууцын утгыг лавлагаанаас уншина. Утгыг лог, view, payload-д хэзээ ч оруулахгүй."""
        self.ensure_one()
        if not self.secret_key:
            return None
        if self.secret_source == 'env':
            return os.environ.get(self.secret_key) or None
        return self.env['ir.config_parameter'].sudo().get_param(self.secret_key) or None

    def _redact(self, text):
        """Алдааны текстээс нууцын утгыг арилгаж, урт бол тайрна."""
        self.ensure_one()
        text = str(text or '')
        try:
            secret = self.get_secret()
        except Exception:  # лавлагаа уншихад алдаа гарсан ч алдааны текстийг хамгаална
            secret = None
        if secret:
            text = text.replace(secret, '***')
        return text[:MAX_ERROR_LENGTH]

    @api.model
    def _enabled_endpoints(self, kind):
        return self.sudo().search([('kind', '=', kind), ('enabled', '=', True)])

    def _ensure_enabled(self):
        self.ensure_one()
        if not self.enabled:
            raise UserError(_('Интеграц унтраалттай байна: %s') % self.name)
