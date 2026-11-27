"""INT-01 SSO adapter (OIDC). Сүлжээ дуудахгүй; discovery баримтыг дуудагч өгнө.

Аюулгүй байдлын шийдвэр:
* IdP бүлэг → Odoo бүлгийн дүрэм зөвхөн ALLOWLIST-ийн бүлэгт байж болно. Админ/CISO/ERP менежер/
  регистраторын эрх автоматаар олгогдохгүй (дүрмийн constraint + provisioning дээр давхар шалгана).
* Имэйл баталгаажаагүй, домэйн зөвшөөрөгдөөгүй бол хэрэглэгч үүсгэхгүй.
* Одоо байгаа, холбогдоогүй хэрэглэгчийг имэйлээр «таньж» холбохгүй (account takeover-ээс сэргийлнэ).
* Rule-ээр удирдагддаг бүлгээс л хасна; админ гараар олгосон бусад бүлэгт хүрэхгүй.
* Auth_oauth суулгаагүй; энэ модуль auth_oauth-тай холбогдоогүй. NOT VERIFIED (live IdP).
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

ALLOWED_GROUP_XMLIDS = (
    'base.group_user',
    'base.group_portal',
    'university_isms.group_isms_reporter',
    'university_isms.group_isms_asset_owner',
    'university_isms.group_isms_analyst',
    'university_isms.group_isms_auditor',
    'campus_university.group_campus_student',
    'campus_university.group_campus_lecturer',
    'campus_university.group_campus_auditor',
)
FORBIDDEN_GROUP_XMLIDS = (
    'base.group_system',
    'base.group_erp_manager',
    'university_isms.group_isms_manager',
    'campus_university.group_campus_registrar',
)
PRESERVED_GROUP_XMLIDS = ('base.group_user', 'base.group_portal')


def _group_ids(env, xmlids):
    ids = set()
    for xmlid in xmlids:
        group = env.ref(xmlid, raise_if_not_found=False)
        if group:
            ids.add(group.id)
    return ids


class FormulaSsoGroupRule(models.Model):
    _name = 'formula.sso.group.rule'
    _description = 'SSO IdP бүлэг → Odoo бүлгийн дүрэм'
    _order = 'endpoint_id, idp_group'

    endpoint_id = fields.Many2one('formula.integration.endpoint', 'SSO endpoint', required=True,
                                  ondelete='cascade', index=True, domain=[('kind', '=', 'sso')])
    idp_group = fields.Char('IdP бүлгийн нэр (claim)', required=True)
    group_id = fields.Many2one('res.groups', 'Odoo бүлэг', required=True,
                               help='Зөвхөн allowlist-ийн бүлэг. Админ бүлэг сонгох боломжгүй.')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('idp_group_uniq', 'unique(endpoint_id, idp_group)', 'Нэг IdP бүлэгт нэг дүрэм.'),
    ]

    @api.constrains('group_id')
    def _check_group_allowlist(self):
        allowed = _group_ids(self.env, ALLOWED_GROUP_XMLIDS)
        forbidden = _group_ids(self.env, FORBIDDEN_GROUP_XMLIDS)
        for rec in self:
            group = rec.group_id
            implied = set(group.trans_implied_ids.ids) | {group.id}
            if implied & forbidden:
                raise ValidationError(_('Энэ бүлэг админ эрх агуулсан тул SSO-оор автоматаар олгохгүй.'))
            if group.id not in allowed:
                raise ValidationError(_('Энэ бүлэг SSO allowlist-д байхгүй.'))


class FormulaSsoAdapter(models.AbstractModel):
    _name = 'formula.sso.adapter'
    _description = 'SSO provisioning adapter (OIDC)'

    @api.model
    def parse_discovery(self, document, expected_issuer):
        """OIDC discovery баримтыг шалгана. Сүлжээ дуудахгүй."""
        if not isinstance(document, dict):
            raise ValidationError(_('Discovery баримт буруу форматтай.'))
        if not expected_issuer or document.get('issuer') != expected_issuer:
            raise ValidationError(_('Discovery issuer тохируулсантай таарахгүй байна.'))
        result = {'issuer': expected_issuer, 'scopes': ['openid', 'email', 'profile']}
        for key in ('authorization_endpoint', 'token_endpoint', 'jwks_uri'):
            value = document.get(key)
            if not isinstance(value, str) or not value.startswith('https://'):
                raise ValidationError(_('Discovery-ийн %s https байх ёстой.') % key)
            result[key] = value
        return result

    @api.model
    def client_settings(self, endpoint):
        """Client тохиргоо. Нууцын утгыг буцаахгүй; зөвхөн тохируулсан эсэхийг заана."""
        endpoint.ensure_one()
        return {
            'issuer': endpoint.issuer or '',
            'client_id': endpoint.client_id or '',
            'secret_configured': bool(endpoint.get_secret()),
            'allowed_domains': [d.strip().lower() for d in (endpoint.allowed_domains or '').split(',')
                                if d.strip()],
        }

    @api.model
    def map_groups(self, endpoint, idp_groups):
        """IdP бүлгүүдээс хамаарах Odoo бүлгүүд. Дүрэмгүй бүлэг бүрэн үл тоомсорлоно."""
        rules = self.env['formula.sso.group.rule'].sudo().search([
            ('endpoint_id', '=', endpoint.id),
            ('active', '=', True),
            ('idp_group', 'in', list(idp_groups)),
        ])
        return rules.mapped('group_id')

    @api.model
    @api.private
    def provision_user(self, endpoint, claims):
        """Login үед хэрэглэгч үүсгэх/шинэчлэх. Нууц үг үүсгэхгүй (SSO-р нэвтэрнэ).

        Нэвтрэлтээс өмнө ажилладаг тул sudo зөвхөн энэ функцэд, claim-аас хамаарах хязгаарт ашиглана.
        """
        endpoint = endpoint.sudo()
        if endpoint.kind != 'sso' or not endpoint.enabled:
            raise UserError(_('SSO интеграц идэвхгүй байна.'))
        sub = str(claims.get('sub') or '').strip()
        email = str(claims.get('email') or '').strip().lower()
        if not sub or '@' not in email:
            raise ValidationError(_('Шаардлагатай claim (sub, email) дутуу байна.'))
        if claims.get('email_verified') is not True:
            raise AccessError(_('Имэйл баталгаажаагүй тул нэвтрүүлэхгүй.'))
        domain = email.rsplit('@', 1)[1]
        allowed_domains = [d.strip().lower() for d in (endpoint.allowed_domains or '').split(',') if d.strip()]
        if domain not in allowed_domains:
            raise AccessError(_('Имэйлийн домэйн зөвшөөрөгдөөгүй.'))
        idp_groups = claims.get('groups') or []
        if not isinstance(idp_groups, (list, tuple)) or not all(isinstance(g, str) for g in idp_groups):
            raise ValidationError(_('groups claim буруу форматтай.'))

        Users = self.env['res.users'].sudo().with_context(no_reset_password=True)
        mapping = self.env['formula.integration.mapping'].sudo().search([
            ('endpoint_id', '=', endpoint.id), ('local_model', '=', 'res.users'), ('remote_id', '=', sub),
        ], limit=1)
        user = Users.browse(mapping.local_id).exists() if mapping else Users.browse()
        if mapping and not user:
            raise ValidationError(_('Холбоотой хэрэглэгч олдсонгүй. Админ холбоосыг шалгана уу.'))
        if not user:
            existing = Users.search([('login', '=', email)], limit=1)
            if existing:
                raise ValidationError(_('Энэ имэйлтэй хэрэглэгч аль хэдийн бий. Админ гараар холбоно уу.'))

        rule_groups = self.map_groups(endpoint, idp_groups)
        managed = self.env['formula.sso.group.rule'].sudo().search([('endpoint_id', '=', endpoint.id)]).mapped(
            'group_id')
        preserved = _group_ids(self.env, PRESERVED_GROUP_XMLIDS)
        forbidden = _group_ids(self.env, FORBIDDEN_GROUP_XMLIDS)
        effective_rules = rule_groups | rule_groups.trans_implied_ids
        if forbidden & set(effective_rules.ids):
            raise ValidationError(_('Дүрэмд админ бүлэг байна; SSO-д зөвшөөрөгдөхгүй.'))

        user_types = self.env['res.groups'].browse(list(preserved))
        internal = self.env.ref('base.group_user')
        incoming_type = effective_rules & user_types
        if len(incoming_type) > 1:
            raise AccessError(_('Оюутны болон ажилтны эрхийг нэг бүртгэлд тохируулах боломжгүй.'))

        if not user:
            default_group = incoming_type or internal
            user = Users.create({
                'name': str(claims.get('name') or email)[:128],
                'login': email,
                'email': email,
                'groups_id': [(6, 0, list((rule_groups | default_group).ids))],
            })
            self.env['formula.integration.mapping'].sudo().link(endpoint, 'res.users', user.id, sub, 'user')
        else:
            # Rule-ээр удирдагддаг бүлгээс зөвхөн rule-д байхгүй болсныг хасна; preserved бүлэг хэзээ ч хасагдахгүй.
            removable = managed - rule_groups - self.env['res.groups'].browse(list(preserved))
            new_groups = (user.groups_id - removable) | rule_groups
            if len((new_groups | new_groups.trans_implied_ids) & user_types) > 1:
                raise AccessError(_('Энэ хэрэглэгчийн төрлийг солихын тулд системийн админд хандана уу.'))
            if set(new_groups.ids) != set(user.groups_id.ids):
                user.write({'groups_id': [(6, 0, new_groups.ids)]})
            if claims.get('name') and user.name != str(claims['name'])[:128]:
                user.write({'name': str(claims['name'])[:128]})
        return user
