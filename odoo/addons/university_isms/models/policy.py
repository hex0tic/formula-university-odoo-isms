"""ISMS бодлогын бүртгэл (A.5.1, A.5.37, Clause 7.5).

Odoo Documents/Knowledge нь Enterprise тул Community-д баримтын хувилбар, батлалт, танилцсан
бүртгэлийг өөрсдөө хөтөлнө. Бодлогын төрөл нь Лекц 5-ын EISP / ISSP / SysSP ангиллаар.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class IsmsPolicy(models.Model):
    _name = 'isms.policy'
    _description = 'ISMS бодлого, баримт бичиг'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'isms.audit.mixin']
    _order = 'code'
    _rec_names_search = ['code', 'name']
    _isms_lock_code = True

    code = fields.Char('Код', required=True, copy=False, readonly=True, default='/', index=True)
    name = fields.Char('Нэр', required=True, tracking=True)
    policy_type = fields.Selection([
        ('eisp', 'EISP — Байгууллагын МАБ-ын бодлого'),
        ('issp', 'ISSP — Асуудал тус бүрийн бодлого'),
        ('syssp', 'SysSP — Системийн бодлого'),
        ('plan', 'Төлөвлөгөө'),
        ('procedure', 'Журам, заавар'),
    ], 'Төрөл', required=True, default='issp', tracking=True)
    version = fields.Char('Хувилбар', default='1.0', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Ноорог'),
        ('review', 'Хянагдаж буй'),
        ('approved', 'Батлагдсан'),
        ('retired', 'Хүчингүй'),
    ], 'Төлөв', default='draft', required=True, tracking=True)
    owner_id = fields.Many2one('res.users', 'Эзэмшигч', tracking=True, default=lambda self: self.env.user)
    approver_id = fields.Many2one('res.users', 'Баталсан', readonly=True, tracking=True)
    approval_date = fields.Date('Баталсан огноо', readonly=True, tracking=True)
    next_review_date = fields.Date('Дахин хянах огноо', tracking=True)
    summary = fields.Text('Товч агуулга')
    content = fields.Html('Агуулга')
    control_ids = fields.Many2many('isms.control', 'isms_policy_control_rel', 'policy_id', 'control_id',
                                   string='Холбогдох Annex A хяналт')
    ack_ids = fields.One2many('isms.policy.ack', 'policy_id', 'Танилцсан бүртгэл')
    ack_count = fields.Integer('Танилцсан', compute='_compute_ack')
    user_has_ack = fields.Boolean('Би танилцсан', compute='_compute_ack')

    _sql_constraints = [('code_uniq', 'unique(code)', 'Бодлогын код давхардахгүй.')]

    # Батлалтын төлөв, батлагч, огноог зөвхөн workflow өөрчилнө; батлагдсан агуулгыг шууд засахгүй (A.5.37, 7.5.3)
    _PROTECTED = {'approver_id', 'approval_date'}
    _FROZEN_WHEN_APPROVED = {'content', 'version', 'name', 'policy_type', 'summary'}
    _TRANSITIONS = {
        ('draft', 'review'): 'action_submit',
        ('draft', 'approved'): 'action_approve',
        ('review', 'approved'): 'action_approve',
        ('approved', 'retired'): 'action_retire',
        ('review', 'draft'): 'action_reset_draft',
        ('approved', 'draft'): 'action_reset_draft',
        ('retired', 'draft'): 'action_reset_draft',
    }

    @api.model_create_multi
    def create(self, vals_list):
        if not self._isms_is_internal():
            for vals in vals_list:
                if vals.get('state', 'draft') != 'draft' or self._PROTECTED & set(vals):
                    raise AccessError(_('Бодлогыг зөвхөн «Ноорог» төлөвөөс эхлүүлнэ.'))
        for vals in vals_list:
            if not vals.get('code') or vals['code'] == '/':
                vals['code'] = self._isms_next_code('isms.policy')
        return super().create(vals_list)

    def write(self, vals):
        if self._isms_is_internal():
            return super().write(vals)
        if self._PROTECTED & set(vals):
            raise AccessError(_('Батлагч, батлсан огноог зөвхөн CISO «Батлах» үйлдлээр бүртгэнэ.'))
        if self._FROZEN_WHEN_APPROVED & set(vals) and any(r.state in ('approved', 'retired') for r in self):
            raise UserError(_('Батлагдсан бодлогыг засахын тулд эхлээд «Ноорог болгож», шинэ хувилбар гаргана.'))
        vals = dict(vals)
        target = vals.pop('state', None)
        res = super().write(vals) if vals else True
        if target:
            for rec in self.filtered(lambda r: r.state != target):
                method = self._TRANSITIONS.get((rec.state, target))
                if not method:
                    raise UserError(_('%s: төлөвийн шилжилт зөвшөөрөгдөхгүй.') % rec.code)
                getattr(rec, method)()
        return res

    @api.depends('code', 'name', 'version')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s %s (v%s)' % (rec.code, rec.name, rec.version)

    @api.depends('ack_ids', 'version')
    @api.depends_context('uid')
    def _compute_ack(self):
        for rec in self:
            acks = rec.sudo().ack_ids.filtered(lambda a: a.version == rec.version)
            rec.ack_count = len(acks)
            rec.user_has_ack = self.env.user in acks.user_id

    def _require_manager(self):
        if not self.env.su and not self.env.user.has_group('university_isms.group_isms_manager'):
            raise AccessError(_('Бодлогыг зөвхөн МАБ менежер (CISO) батална.'))

    def action_submit(self):
        if not self.env.su and not self.env.user.has_group('university_isms.group_isms_analyst'):
            raise AccessError(_('Хянуулахаар зөвхөн МАБ шинжээч илгээнэ.'))
        self.filtered(lambda r: r.state == 'draft')._isms_internal().write({'state': 'review'})

    def action_approve(self):
        self._require_manager()
        today = fields.Date.context_today(self)
        self.filtered(lambda r: r.state in ('draft', 'review'))._isms_internal().write({
            'state': 'approved',
            'approver_id': self.env.user.id,
            'approval_date': today,
            'next_review_date': today + relativedelta(years=1),
        })

    def action_retire(self):
        self._require_manager()
        self._isms_internal().write({'state': 'retired'})

    def action_reset_draft(self):
        self._require_manager()
        self._isms_internal().write({'state': 'draft', 'approver_id': False, 'approval_date': False})

    def action_acknowledge(self):
        for rec in self.filtered(lambda r: r.state == 'approved' and not r.user_has_ack):
            self.env['isms.policy.ack'].create({'policy_id': rec.id, 'version': rec.version})
        return True


class IsmsPolicyAck(models.Model):
    _name = 'isms.policy.ack'
    _description = 'Бодлоготой танилцсан бүртгэл'
    _inherit = ['isms.audit.mixin']
    _order = 'date desc'

    policy_id = fields.Many2one('isms.policy', 'Бодлого', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', 'Хэрэглэгч', required=True, default=lambda self: self.env.user,
                              index=True)
    version = fields.Char('Хувилбар', required=True)
    date = fields.Datetime('Огноо', default=fields.Datetime.now, required=True)

    _sql_constraints = [('ack_uniq', 'unique(policy_id, user_id, version)',
                         'Энэ хувилбартай аль хэдийн танилцсан байна.')]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            policy = self.env['isms.policy'].browse(vals.get('policy_id'))
            if not self.env.su:
                if vals.get('user_id', self.env.uid) != self.env.uid:
                    raise AccessError(_('Зөвхөн өөрийн нэрээр танилцсанаа бүртгэнэ.'))
                if policy.state != 'approved':
                    raise UserError(_('Зөвхөн батлагдсан бодлоготой танилцана.'))
                vals['user_id'] = self.env.uid
                vals['date'] = fields.Datetime.now()
            vals['version'] = policy.version
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise AccessError(_('Танилцсан бүртгэлийг өөрчлөх боломжгүй.'))
        return super().write(vals)
