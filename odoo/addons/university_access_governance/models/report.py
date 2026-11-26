"""GOV-04: давуу эрхийн тайлан (SQL view, зөвхөн унших).

Нууц үг, TOTP нууц, токен хэзээ ч уншигдахгүй: TOTP-ийн зөвхөн logic (тийм/үгүй) утгыг авна.
Хандалтыг ACL-ээр хязгаарлана: erp менежер, системийн администратор, ISMS аудитор, CISO.
"""
from odoo import SUPERUSER_ID, api, fields, models, tools

from .governance_common import privileged_groups


class AccessGovReport(models.Model):
    _name = 'access.gov.report'
    _description = 'Давуу эрхийн тайлан'
    _auto = False
    _order = 'login, id'

    user_id = fields.Many2one('res.users', 'Хэрэглэгч', readonly=True)
    login = fields.Char('Нэвтрэх нэр', readonly=True)
    user_active = fields.Boolean('Идэвхтэй', readonly=True)
    group_id = fields.Many2one('res.groups', 'Давуу эрхийн бүлэг', readonly=True)
    last_login = fields.Datetime('Сүүлд нэвтэрсэн', compute='_compute_security', compute_sudo=True)
    totp_enabled = fields.Boolean('Хоёр шатлалт (TOTP)', compute='_compute_security', compute_sudo=True,
                                  help='auth_totp суулгасан үед л утга гарна. Нууц утгыг уншихгүй.')
    temp_grant_count = fields.Integer('Идэвхтэй түр эрх', compute='_compute_security', compute_sudo=True)
    open_recert_count = fields.Integer('Нээлттэй тойм', compute='_compute_security', compute_sudo=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        group_ids = privileged_groups(self.env).ids or [0]
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %(table)s AS (
                SELECT ROW_NUMBER() OVER (ORDER BY ru.id, rel.gid) AS id,
                       ru.id AS user_id,
                       ru.login AS login,
                       ru.active AS user_active,
                       rel.gid AS group_id
                FROM res_groups_users_rel rel
                JOIN res_users ru ON ru.id = rel.uid
                WHERE rel.gid IN (%(groups)s) AND ru.id <> %(root)s
            )
        """ % {
            'table': self._table,
            'groups': ','.join(str(int(gid)) for gid in group_ids),
            'root': int(SUPERUSER_ID),
        })

    @api.depends('user_id', 'group_id')
    def _compute_security(self):
        env = self.env
        Users = env['res.users'].sudo()
        has_totp = 'totp_enabled' in Users._fields
        Request = env['access.request'].sudo()
        Line = env['access.recert.line'].sudo()
        cache = {}
        for rec in self:
            user = Users.browse(rec.user_id.id)
            key = (user.id, rec.group_id.id)
            if key not in cache:
                cache[key] = {
                    'last_login': user.login_date or False,
                    'totp_enabled': bool(user.totp_enabled) if has_totp else False,
                    'temp_grant_count': Request.search_count([
                        ('target_user_id', '=', user.id), ('state', '=', 'active'),
                        ('group_ids', 'in', [rec.group_id.id])]),
                    'open_recert_count': Line.search_count([
                        ('user_id', '=', user.id), ('decision', '=', 'pending')]),
                }
            for name, value in cache[key].items():
                setattr(rec, name, value)
