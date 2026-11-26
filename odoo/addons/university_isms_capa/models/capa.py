"""CAPA: залруулах арга хэмжээ (ISO/IEC 27001:2022 10.2).

Урсгал: draft → in_progress → implemented → verified → closed (+ cancelled).
Хараат бус баталгаажуулалт: баталгаажуулагч нь CAPA-ийн хариуцагч, хэрэгжүүлсэн гэж тэмдэглэсэн
хүн биш байх ёстой. Баталгаажуулах: ISMS аудитор эсвэл CISO. Хаах: зөвхөн CISO.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .common import GROUP_ANALYST, GROUP_AUDITOR, GROUP_CISO, require_group

CAPA_STATES = [
    ('draft', 'Ноорог'),
    ('in_progress', 'Хэрэгжүүлж буй'),
    ('implemented', 'Хэрэгжүүлсэн (баталгаажуулалт хүлээж буй)'),
    ('verified', 'Баталгаажсан'),
    ('closed', 'Хаасан'),
    ('cancelled', 'Цуцалсан'),
]
ACTIVE = ('draft', 'in_progress', 'implemented')


class IsmsCapa(models.Model):
    _name = 'isms.capa'
    _description = 'Залруулах арга хэмжээ (CAPA)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'isms.audit.mixin']
    _order = 'deadline asc, id desc'

    code = fields.Char('Дугаар', readonly=True, copy=False, default='New')
    name = fields.Char('Гарчиг', required=True, tracking=True)
    finding_id = fields.Many2one('isms.finding', 'Олдвор', required=True, ondelete='cascade',
                                 index=True, tracking=True)
    finding_severity = fields.Selection(related='finding_id.severity', string='Олдворын ноцтой байдал',
                                        readonly=True)
    root_cause = fields.Text('Үндсэн шалтгаан')
    corrective_action = fields.Text('Засварлах арга хэмжээний төлөвлөгөө')
    owner_id = fields.Many2one('res.users', 'Хариуцагч (хэрэгжүүлэгч)', tracking=True, index=True)
    deadline = fields.Date('Хугацаа', required=True, tracking=True)
    is_overdue = fields.Boolean('Хугацаа хэтэрсэн', compute='_compute_is_overdue',
                                search='_search_is_overdue')
    state = fields.Selection(CAPA_STATES, 'Төлөв', default='draft', required=True, tracking=True,
                             copy=False, group_expand='_group_expand_states')
    implementation_notes = fields.Text('Хэрэгжилтийн тайлбар')
    evidence_ref = fields.Char('Нотолгооны лавлагаа', help='Evidence Vault дугаар эсвэл баримтын байршил')
    implemented_by_id = fields.Many2one('res.users', 'Хэрэгжүүлсэн гэж тэмдэглэсэн', readonly=True,
                                        copy=False)
    implemented_at = fields.Datetime('Хэрэгжүүлсэн огноо', readonly=True, copy=False)
    verifier_id = fields.Many2one('res.users', 'Баталгаажуулагч', readonly=True, copy=False, tracking=True)
    verified_at = fields.Datetime('Баталгаажсан огноо', readonly=True, copy=False)
    verification_notes = fields.Text('Баталгаажуулалтын тэмдэглэл')
    closed_at = fields.Datetime('Хаасан огноо', readonly=True, copy=False)
    cancel_reason = fields.Text('Цуцалсан шалтгаан', copy=False)

    _sql_constraints = [('code_uniq', 'unique(code)', 'CAPA-ийн дугаар давтагдахгүй.')]

    # Төлөв болон баталгаажуулалтын талбарыг зөвхөн сервер талын үйлдэл бичнэ
    _PROTECTED = {'code', 'state', 'finding_id', 'implemented_by_id', 'implemented_at',
                  'verifier_id', 'verified_at', 'closed_at'}
    _LOCKED_ON_CREATE = {'state', 'implemented_by_id', 'implemented_at', 'verifier_id', 'verified_at',
                         'closed_at'}
    _AUDITOR_FIELDS = {'verification_notes'}

    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, _label in CAPA_STATES]

    @api.depends('deadline', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(rec.deadline and rec.deadline < today and rec.state in ACTIVE)

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        positive = (operator == '=') == bool(value)
        if positive:
            return [('deadline', '<', today), ('state', 'in', list(ACTIVE))]
        return ['|', '|', ('deadline', '=', False), ('deadline', '>=', today),
                ('state', 'not in', list(ACTIVE))]

    @api.model_create_multi
    def create(self, vals_list):
        internal = self._isms_is_internal()
        for vals in vals_list:
            if not internal and (vals.get('state', 'draft') != 'draft' or self._LOCKED_ON_CREATE & set(vals)):
                raise AccessError(_('CAPA-ийн төлөв, баталгаажуулалтын талбарыг гараар тавих боломжгүй.'))
            finding = self.env['isms.finding'].browse(vals.get('finding_id'))
            if finding.state == 'closed':
                raise UserError(_('Хаагдсан олдворт CAPA нэмэх боломжгүй.'))
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('isms.capa') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if self._isms_is_internal():
            return super().write(vals)
        business = {k for k in vals if not k.startswith(('message_', 'activity_'))}
        if self._PROTECTED & business:
            raise AccessError(_('CAPA-ийн төлөв болон баталгаажуулалтын талбарыг зөвхөн CAPA урсгалын үйлдлээр өөрчилнө.'))
        if self.env.user.has_group(GROUP_ANALYST):
            if any(rec.state in ('verified', 'closed', 'cancelled') for rec in self) and business:
                raise UserError(_('Баталгаажсан, хаасан, цуцалсан CAPA-г засах боломжгүй.'))
        else:
            # Аудитор зөвхөн хэрэгжүүлсний дараа баталгаажуулалтын тэмдэглэлийг бичнэ
            if business - self._AUDITOR_FIELDS:
                raise AccessError(_('Аудитор CAPA-ийн агуулгыг засах эрхгүй; зөвхөн баталгаажуулалтын тэмдэглэл.'))
            if any(rec.state != 'implemented' for rec in self):
                raise UserError(_('Баталгаажуулалтын тэмдэглэлийг зөвхөн «Хэрэгжүүлсэн» үед бичнэ.'))
        return super().write(vals)

    # ------------------------------------------------------------ урсгал
    def action_start(self):
        """ноорог → хэрэгжүүлж буй. Олдвор open → capa."""
        self.ensure_one()
        require_group(self.env, GROUP_ANALYST, _('МАБ шинжээч'))
        if self.state != 'draft':
            raise UserError(_('%s: зөвхөн ноорог CAPA-г эхлүүлнэ.') % self.code)
        missing = [label for label, value in [
            (_('Хариуцагч'), self.owner_id),
            (_('Хугацаа'), self.deadline),
            (_('Үндсэн шалтгаан'), (self.root_cause or '').strip()),
            (_('Засварлах арга хэмжээ'), (self.corrective_action or '').strip()),
        ] if not value]
        if missing:
            raise UserError(_('%s: дутуу талбар: %s') % (self.code, ', '.join(missing)))
        self.sudo()._isms_internal().write({'state': 'in_progress'})
        self.finding_id.sudo()._capa_started()
        return True

    def action_mark_implemented(self):
        """хэрэгжүүлж буй → хэрэгжүүлсэн. Хариуцагч эсвэл МАБ шинжээч; нотолгоо заавал."""
        self.ensure_one()
        user = self.env.user
        if self.state != 'in_progress':
            raise UserError(_('%s: зөвхөн «Хэрэгжүүлж буй» CAPA-г хэрэгжүүлсэн гэж тэмдэглэнэ.') % self.code)
        if not (user == self.owner_id or user.has_group(GROUP_ANALYST)):
            raise AccessError(_('Хэрэгжүүлсэн гэж тэмдэглэхийг CAPA-ийн хариуцагч эсвэл МАБ шинжээч хийнэ.'))
        if not ((self.implementation_notes or '').strip() or (self.evidence_ref or '').strip()):
            raise UserError(_('%s: хэрэгжилтийн тайлбар эсвэл нотолгооны лавлагааг оруулна уу.') % self.code)
        self.sudo()._isms_internal().write({
            'state': 'implemented', 'implemented_by_id': user.id, 'implemented_at': fields.Datetime.now(),
        })
        return True

    def action_verify(self):
        """хэрэгжсэн → баталгаажсан. Аудитор эсвэл CISO; хариуцагч/хэрэгжүүлэгч болохгүй."""
        self.ensure_one()
        require_group(self.env, GROUP_AUDITOR, _('ISMS аудитор эсвэл CISO'))
        user = self.env.user
        if self.state != 'implemented':
            raise UserError(_('%s: зөвхөн «Хэрэгжүүлсэн» CAPA-г баталгаажуулна.') % self.code)
        if user == self.owner_id:
            raise AccessError(_('%s: CAPA-ийн хариуцагч өөрийн CAPA-г баталгаажуулах боломжгүй.') % self.code)
        if user == self.implemented_by_id:
            raise AccessError(_('%s: хэрэгжүүлсэн хүн өөрөө баталгаажуулах боломжгүй.') % self.code)
        if not (self.verification_notes or '').strip():
            raise UserError(_('%s: баталгаажуулалтын тэмдэглэлийг бичнэ үү.') % self.code)
        self.sudo()._isms_internal().write({
            'state': 'verified', 'verifier_id': user.id, 'verified_at': fields.Datetime.now(),
        })
        self.finding_id.sudo()._sync_state_from_capas()
        return True

    def action_reject(self):
        """хэрэгжсэн → хэрэгжүүлж буй (буцаах). Шалтгааныг баталгаажуулалтын тэмдэглэлд бичнэ."""
        self.ensure_one()
        require_group(self.env, GROUP_AUDITOR, _('ISMS аудитор эсвэл CISO'))
        if self.state != 'implemented':
            raise UserError(_('%s: зөвхөн «Хэрэгжүүлсэн» CAPA-г буцаана.') % self.code)
        if not (self.verification_notes or '').strip():
            raise UserError(_('%s: буцаах шалтгааныг баталгаажуулалтын тэмдэглэлд бичнэ үү.') % self.code)
        self.sudo()._isms_internal().write({
            'state': 'in_progress', 'implemented_by_id': False, 'implemented_at': False,
        })
        return True

    def action_close(self):
        """баталгаажсан → хаасан. Зөвхөн CISO."""
        self.ensure_one()
        require_group(self.env, GROUP_CISO, _('МАБ менежер (CISO)'))
        if self.state != 'verified':
            raise UserError(_('%s: зөвхөн баталгаажсан CAPA-г хаана.') % self.code)
        if not (self.verification_notes or '').strip():
            raise UserError(_('%s: хаахаас өмнө баталгаажуулалтын тэмдэглэл шаардлагатай.') % self.code)
        self.sudo()._isms_internal().write({'state': 'closed', 'closed_at': fields.Datetime.now()})
        return True

    def action_cancel(self):
        """идэвхтэй → цуцалсан. Зөвхөн CISO, шалтгаан заавал."""
        self.ensure_one()
        require_group(self.env, GROUP_CISO, _('МАБ менежер (CISO)'))
        if self.state not in ACTIVE:
            raise UserError(_('%s: хаагдсан эсвэл баталгаажсан CAPA-г цуцлах боломжгүй.') % self.code)
        if not (self.cancel_reason or '').strip():
            raise UserError(_('%s: цуцлах шалтгааныг бичнэ үү.') % self.code)
        self.sudo()._isms_internal().write({'state': 'cancelled'})
        self.finding_id.sudo()._sync_state_from_capas()
        return True
