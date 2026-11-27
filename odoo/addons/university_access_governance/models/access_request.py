"""GOV-03: түр ба давуу эрхийн хүсэлт (ISO/IEC 27001 A.5.18, A.8.2, A.5.3)."""
import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, Command, _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError

from .governance_common import (
    MANAGER_GROUP, effective_groups, has_privileged_groups, is_system, link_groups,
    new_sod_conflicts, unlink_groups,
)

_logger = logging.getLogger(__name__)

REQUEST_STATES = [
    ('draft', 'Ноорог'), ('submitted', 'Илгээсэн'), ('approved', 'Батлагдсан'), ('active', 'Идэвхтэй'),
    ('expired', 'Хугацаа дууссан'), ('revoked', 'Цуцалсан'), ('rejected', 'Татгалзсан'),
]
REQUEST_AUDIT_FIELDS = {'approver_id', 'approved_at', 'activated_at', 'ended_at',
                        'added_group_ids', 'outcome', 'rejected_reason'}
PROTECTED_FIELDS = REQUEST_AUDIT_FIELDS | {'state', 'is_privileged'}
BUSINESS_FIELDS = {'requester_id', 'target_user_id', 'group_ids', 'justification', 'start_date', 'end_date'}
POLICY = {
    'min_justification': ('university_access_governance.min_justification_length', 20),
    'max_privileged_days': ('university_access_governance.max_privileged_days', 7),
    'max_temporary_days': ('university_access_governance.max_temporary_days', 30),
}


class AccessRequest(models.Model):
    _name = 'access.request'
    _description = 'Түр ба давуу эрхийн хүсэлт'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char('Дугаар', readonly=True, copy=False, default='Шинэ', index=True)
    requester_id = fields.Many2one('res.users', 'Хүсэлт гаргагч', required=True, index=True, tracking=True,
                                   default=lambda s: s._default_user(), domain=[('share', '=', False)])
    target_user_id = fields.Many2one('res.users', 'Эрх авах хэрэглэгч', required=True, index=True, tracking=True,
                                     default=lambda s: s._default_user(), domain=[('share', '=', False)])
    group_ids = fields.Many2many('res.groups', 'access_request_group_rel', 'request_id', 'group_id',
                                 'Хүсэж буй бүлгүүд')
    is_privileged = fields.Boolean('Давуу эрх', compute='_compute_is_privileged', store=True)
    justification = fields.Text('Үндэслэл', tracking=True)
    start_date = fields.Datetime('Эхлэх огноо', required=True, default=fields.Datetime.now, tracking=True)
    end_date = fields.Datetime('Дуусах огноо', required=True, tracking=True)
    duration_days = fields.Float('Хугацаа (өдөр)', compute='_compute_duration', digits=(6, 2))
    state = fields.Selection(REQUEST_STATES, 'Төлөв', required=True, default='draft', tracking=True, copy=False)
    approver_id = fields.Many2one('res.users', 'Батлагч', readonly=True, copy=False)
    approved_at = fields.Datetime('Батлагдсан огноо', readonly=True, copy=False)
    activated_at = fields.Datetime('Идэвхжсэн огноо', readonly=True, copy=False)
    ended_at = fields.Datetime('Дууссан огноо', readonly=True, copy=False)
    added_group_ids = fields.Many2many('res.groups', 'access_request_added_group_rel', 'request_id', 'group_id',
                                       'Нэмсэн бүлгүүд', readonly=True, copy=False,
                                       help='Олголтын үед хэрэглэгчид байгаагүй, энэ хүсэлтээр нэмэгдсэн бүлгүүд. '
                                            'Зөвхөн эдгээрийг хугацаа дуусахад хасна.')
    outcome = fields.Text('Үр дүн', readonly=True, copy=False)
    rejected_reason = fields.Text('Татгалзсан шалтгаан', copy=False)

    # ------------------------------------------------------------ defaults / computes
    @api.model
    def _default_user(self):
        # Superuser-ийн ачаалсан өгөгдөл OdooBot-ийг эзэн болгохгүй.
        return self.env.user if self.env.uid != SUPERUSER_ID else self.env['res.users']

    @api.model
    def default_get(self, fields_list):
        return super().default_get([name for name in fields_list if name != 'is_privileged'])

    @api.model
    def _policy(self, key):
        param, default = POLICY[key]
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(param, default))
        except (TypeError, ValueError):
            return default

    @api.depends('group_ids')
    def _compute_is_privileged(self):
        for rec in self:
            rec.is_privileged = has_privileged_groups(rec.group_ids)

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.duration_days = (rec.end_date - rec.start_date).total_seconds() / 86400.0
            else:
                rec.duration_days = 0.0

    # ------------------------------------------------------------ constraints
    @api.constrains('justification')
    def _check_justification(self):
        minimum = self._policy('min_justification')
        for rec in self:
            if len((rec.justification or '').strip()) < minimum:
                raise ValidationError(_('Үндэслэл хамгийн багадаа %s тэмдэгт байх ёстой.', minimum))

    @api.constrains('group_ids')
    def _check_groups(self):
        for rec in self:
            if not rec.group_ids:
                raise ValidationError(_('Дор хаяж нэг эрхийн бүлэг сонгоно уу.'))

    @api.constrains('start_date', 'end_date', 'group_ids')
    def _check_duration(self):
        for rec in self:
            if not rec.end_date:
                raise ValidationError(_('Түр хандалтын дуусах огноо заавал байна.'))
            if rec.end_date <= rec.start_date:
                raise ValidationError(_('Дуусах огноо нь эхлэх огнооноос хойш байх ёстой.'))
            key = 'max_privileged_days' if has_privileged_groups(rec.group_ids) else 'max_temporary_days'
            if rec.end_date - rec.start_date > timedelta(days=self._policy(key)):
                raise ValidationError(_('Хугацаа дээд хэмжээгээ (%s өдөр) давсан байна.', self._policy(key)))

    # ------------------------------------------------------------ guards
    @api.model_create_multi
    def create(self, vals_list):
        actor = self.env.user
        vals_list = [dict(vals) for vals in vals_list]
        for vals in vals_list:
            if not self.env.su:
                if (vals.get('requester_id') or actor.id) != actor.id:
                    raise AccessError(_('Хүсэлтийг өөрийн нэрээр гаргана.'))
                vals['requester_id'] = actor.id
            vals.update(dict.fromkeys(REQUEST_AUDIT_FIELDS, False), state='draft')
            vals.pop('is_privileged', None)
            if vals.get('name') in (None, False, 'Шинэ'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('access.request') or 'Шинэ'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            if set(vals) & PROTECTED_FIELDS:
                raise AccessError(_('Төлвийг зөвхөн батлах, идэвхжүүлэх, цуцлах үйлдлээр өөрчилнө (GOV-05).'))
            if set(vals) & BUSINESS_FIELDS:
                actor = self.env.user
                if 'requester_id' in vals and vals['requester_id'] != actor.id:
                    raise AccessError(_('Хүсэлт гаргагчийг солих боломжгүй.'))
                for rec in self:
                    if rec.state != 'draft' or rec.requester_id != actor:
                        raise AccessError(_('Хүсэлтийг зөвхөн гаргагч, ноорог үед засна.'))
        return super().write(vals)

    def _set_state(self, state, **vals):
        # Workflow callers authorize the transition. Keep the normal ORM access checks.
        return super().write(dict(vals, state=state))

    def _check_not_self_or_target(self, actor):
        for rec in self:
            if actor in (rec.requester_id, rec.target_user_id):
                raise AccessError(_('Өөрийн эсвэл эзэмшигч хэрэглэгчийн хүсэлтийг батлах, идэвхжүүлэхгүй (GOV-05).'))

    def _check_approver(self, actor):
        self.ensure_one()
        self._check_not_self_or_target(actor)
        if has_privileged_groups(self.group_ids):
            if not is_system(actor):
                raise AccessError(_('Давуу эрхийн хүсэлтийг зөвхөн системийн администратор батлана (A.8.2).'))
        elif not actor.has_group(MANAGER_GROUP):
            raise AccessError(_('Хүсэлтийг батлах эрх (erp менежер эсвэл администратор) байхгүй.'))

    # ------------------------------------------------------------ workflow
    def action_submit(self):
        self.check_access('write')
        actor = self.env.user
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Зөвхөн ноорог хүсэлтийг илгээнэ.'))
            if rec.requester_id != actor and not actor.has_group(MANAGER_GROUP):
                raise AccessError(_('Хүсэлтийг гаргагч илгээнэ.'))
            if rec.end_date <= fields.Datetime.now():
                raise UserError(_('Дуусах огноо өнгөрсөн байна.'))
            rec._set_state('submitted')
            rec.message_post(body=_('Хүсэлт илгээгдлээ.'))
        return True

    def action_approve(self):
        self.check_access('write')
        now = fields.Datetime.now()
        for rec in self:
            actor = self.env.user
            if rec.state != 'submitted':
                raise UserError(_('Зөвхөн илгээсэн хүсэлтийг батлана.'))
            rec._check_approver(actor)
            if rec.end_date <= now:
                raise UserError(_('Дуусах огноо өнгөрсөн байна.'))
            target = rec.target_user_id
            conflicts = new_sod_conflicts(self.env, target.groups_id, target.groups_id | rec.group_ids)
            if conflicts:
                raise UserError(_('Үүргийн тусгаарлалтын зөрчил (A.5.3), хүсэлтийг батлах боломжгүй: %s',
                                  '; '.join(conflicts)))
            rec._set_state('approved', approver_id=actor.id, approved_at=now)
            rec.message_post(body=_('Батлагдлаа (%s).', actor.name))
        return True

    def action_reject(self):
        self.check_access('write')
        for rec in self:
            actor = self.env.user
            if rec.state != 'submitted':
                raise UserError(_('Зөвхөн илгээсэн хүсэлтийг татгалзана.'))
            rec._check_approver(actor)
            rec._set_state('rejected', approver_id=actor.id, rejected_reason=rec.rejected_reason or False)
            rec.message_post(body=_('Татгалзлаа.'))
        return True

    def action_activate(self):
        self.check_access('write')
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Зөвхөн батлагдсан хүсэлтийг идэвхжүүлнэ.'))
            rec._check_approver(self.env.user)
            if rec.start_date > now:
                raise UserError(_('Эхлэх огноо болоогүй байна. Автомат идэвхжүүлэлт хийгдэнэ.'))
            rec._grant()
        return True

    def _grant(self):
        """Бүлгүүдийг олгоно. Хэрэглэгчид аль хэдийн байгаа бүлгийг хэзээ ч хасахгүй (add-only bookkeeping)."""
        self.ensure_one()
        now = fields.Datetime.now()
        target = self.target_user_id
        if self.end_date <= now:
            self._set_state('expired', ended_at=now, outcome=_('Хугацаа өнгөрсөн тул олгоогүй.'))
            return
        if not target.active:
            raise UserError(_('Эрх авах хэрэглэгч идэвхгүй байна.'))
        actor = self.env.user
        if target == actor and not self.env.su:
            raise AccessError(_('Өөрийн эрхийг өөрөө өөрчлөхгүй (GOV-05).'))
        if not self.env.su and has_privileged_groups(self.group_ids) and not is_system(actor):
            raise AccessError(_('Давуу эрхийг зөвхөн системийн администратор олгоно (A.8.2).'))
        effective = effective_groups(target.groups_id)
        added = self.group_ids - effective
        conflicts = new_sod_conflicts(self.env, target.groups_id, target.groups_id | added)
        if conflicts:
            raise UserError(_('Үүргийн тусгаарлалтын зөрчил (A.5.3): %s', '; '.join(conflicts)))
        link_groups(target, added)
        note = _('Нэмсэн бүлгүүд: %s', ', '.join(added.mapped('name'))) if added else \
            _('Бүлэг нэмэгдээгүй (хэрэглэгчид аль хэдийн байсан).')
        self._set_state('active', activated_at=now, added_group_ids=[Command.set(added.ids)], outcome=note)
        self.message_post(body=note)

    def action_revoke(self):
        self.check_access('write')
        for rec in self:
            actor = self.env.user
            if rec.state != 'active':
                raise UserError(_('Зөвхөн идэвхтэй хүсэлтийг цуцална.'))
            rec._check_approver(actor)
            rec._end_grant('revoked')
        return True

    def _end_grant(self, new_state):
        """Энэ хүсэлтээр нэмсэн бүлгүүдийг хасна. Өөр идэвхтэй хүсэлт шаарддаг бүлгийг хасахгүй."""
        self.ensure_one()
        now = fields.Datetime.now()
        target = self.target_user_id
        others = self.search([('target_user_id', '=', target.id), ('state', '=', 'active'),
                              ('id', '!=', self.id)]).mapped('added_group_ids')
        to_remove = (self.added_group_ids - others) & target.groups_id
        if not self.env.su and has_privileged_groups(to_remove) and not is_system(self.env.user):
            raise AccessError(_('Давуу эрхийг зөвхөн системийн администратор хасна (A.8.2).'))
        unlink_groups(target, to_remove)
        outcome = _('Хасагдсан бүлгүүд: %s', ', '.join(to_remove.mapped('name'))) if to_remove \
            else _('Хасах бүлэг байхгүй (өөр хүсэлт эсвэл өмнөх эрх).')
        self._set_state(new_state, ended_at=now, outcome=outcome)
        self.message_post(body=outcome)

    # ------------------------------------------------------------ scheduled jobs
    @api.model
    def _cron_process_grants(self):
        """Цаг бүр: эхлэх болсон батлагдсан хүсэлтийг идэвхжүүлж, хугацаа дууссаныг хасна.

        Нэг удаагийн шилжилт (төлөвөөр шүүнэ) тул давтан ажиллахад давхардахгүй. Бичлэг бүрийг
        savepoint-д явуулна: нэг алдаа бусдыг зогсоохгүй.
        """
        now = fields.Datetime.now()
        starts = self.sudo().search([('state', '=', 'approved'), ('start_date', '<=', now)])
        for rec in starts:
            self._cron_step(rec, lambda r: r._grant())
        ends = self.sudo().search([('state', '=', 'active'), ('end_date', '<=', now)])
        for rec in ends:
            self._cron_step(rec, lambda r: r._end_grant('expired'))
        return True

    def _cron_step(self, rec, action):
        try:
            with self.env.cr.savepoint():
                action(rec)
        except Exception as exc:
            _logger.exception('Access request %s: scheduled step failed', rec.id)
            rec.sudo().message_post(body=_('Автомат алхам амжилтгүй: %s', exc))
        if not tools.config['test_enable']:
            self.env.cr.commit()
