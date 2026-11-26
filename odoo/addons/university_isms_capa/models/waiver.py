"""ISMS-07: эрсдлийн зөвшөөрөл (waiver / accepted-risk exception).

Хүсэлт шинжээчээс гарна; батлах зөвхөн CISO, батлагч ≠ хүсэлтлэгч. Хугацаа дуусахад өдөр бүр
ажилладаг cron нь төлвийг `expired` болгож, мониторингийн олдвор нээж, эрсдлийг дахин үнэлгээнд
тэмдэглэнэ. Давтан ажиллахад нэг л олдвор үүснэ.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .common import GROUP_ANALYST, GROUP_CISO, require_group

_logger = logging.getLogger(__name__)

WAIVER_STATES = [
    ('draft', 'Ноорог'),
    ('approved', 'Батлагдсан'),
    ('expired', 'Хугацаа дууссан'),
    ('revoked', 'Цуцалсан'),
]


class IsmsRiskWaiver(models.Model):
    _name = 'isms.risk.waiver'
    _description = 'Эрсдлийн зөвшөөрөл (waiver)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'isms.audit.mixin']
    _order = 'expiry_date asc, id desc'

    code = fields.Char('Дугаар', readonly=True, copy=False, default='New')
    name = fields.Char('Гарчиг', required=True, tracking=True)
    risk_id = fields.Many2one('isms.risk', 'Эрсдэл', required=True, index=True, tracking=True)
    justification = fields.Text('Үндэслэл', required=True)
    compensating_controls = fields.Text('Нөхөн хамгаалах хяналт')
    owner_id = fields.Many2one('res.users', 'Хариуцагч (хүлээн зөвшөөрөгч)', required=True, tracking=True)
    requested_by_id = fields.Many2one('res.users', 'Хүсэлтлэгч', default=lambda self: self.env.user,
                                      readonly=True, copy=False, tracking=True)
    approved_by_id = fields.Many2one('res.users', 'Батласан (CISO)', readonly=True, copy=False, tracking=True)
    approved_at = fields.Datetime('Батласан огноо', readonly=True, copy=False)
    expiry_date = fields.Date('Дуусах огноо', required=True, tracking=True)
    state = fields.Selection(WAIVER_STATES, 'Төлөв', default='draft', required=True, tracking=True,
                             copy=False, group_expand='_group_expand_states')
    revoke_reason = fields.Text('Цуцалсан шалтгаан', copy=False)

    _sql_constraints = [('code_uniq', 'unique(code)', 'Зөвшөөрлийн дугаар давтагдахгүй.')]

    _PROTECTED = {'code', 'state', 'requested_by_id', 'approved_by_id', 'approved_at'}

    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, _label in WAIVER_STATES]

    @api.model_create_multi
    def create(self, vals_list):
        internal = self._isms_is_internal()
        for vals in vals_list:
            if not internal:
                if vals.get('state', 'draft') != 'draft' or {'approved_by_id', 'approved_at'} & set(vals):
                    raise AccessError(_('Зөвшөөрлийг зөвхөн ноорог төлөвөөр үүсгэнэ.'))
                if vals.get('requested_by_id', self.env.uid) != self.env.uid:
                    raise AccessError(_('Өөр хүний нэрийн өмнөөс хүсэлт гаргах боломжгүй.'))
                vals['requested_by_id'] = self.env.user.id
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('isms.risk.waiver') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if self._isms_is_internal():
            return super().write(vals)
        business = {k for k in vals if not k.startswith(('message_', 'activity_'))}
        if self._PROTECTED & business:
            raise AccessError(_('Зөвшөөрлийн төлөв, батлагчийг зөвхөн батлах/цуцлах үйлдлээр өөрчилнө.'))
        if any(rec.state != 'draft' for rec in self) and business - {'revoke_reason'}:
            raise UserError(_('Батлагдсан эсвэл хаагдсан зөвшөөрлийг засах боломжгүй.'))
        return super().write(vals)

    def action_approve(self):
        """Батлах: зөвхөн CISO, батлагч нь хүсэлтлэгч байж болохгүй."""
        self.ensure_one()
        require_group(self.env, GROUP_CISO, _('МАБ менежер (CISO)'))
        user = self.env.user
        if self.state != 'draft':
            raise UserError(_('%s: зөвхөн ноорог зөвшөөрлийг батлана.') % self.code)
        if user == self.requested_by_id:
            raise AccessError(_('%s: өөрийн хүсэлтээ өөрөө батлах боломжгүй (үүрэг салгах).') % self.code)
        if not (self.justification or '').strip() or not self.owner_id:
            raise UserError(_('%s: үндэслэл болон хариуцагчийг бөглөнө үү.') % self.code)
        if not self.expiry_date or self.expiry_date <= fields.Date.context_today(self):
            raise UserError(_('%s: дуусах огноо ирээдүйд байх ёстой.') % self.code)
        self.sudo()._isms_internal().write({
            'state': 'approved', 'approved_by_id': user.id, 'approved_at': fields.Datetime.now(),
        })
        return True

    def action_revoke(self):
        """Батлагдсан зөвшөөрлийг цуцлах (зөвхөн CISO, шалтгаан заавал)."""
        self.ensure_one()
        require_group(self.env, GROUP_CISO, _('МАБ менежер (CISO)'))
        if self.state != 'approved':
            raise UserError(_('%s: зөвхөн батлагдсан зөвшөөрлийг цуцлана.') % self.code)
        if not (self.revoke_reason or '').strip():
            raise UserError(_('%s: цуцлах шалтгааныг бичнэ үү.') % self.code)
        self.sudo()._isms_internal().write({'state': 'revoked'})
        return True

    # ------------------------------------------------------------ cron
    @api.model
    def _cron_expire_waivers(self):
        """Хугацаа дууссан батлагдсан зөвшөөрлүүдийг хаана. Бичлэг бүр тусдаа savepoint-д."""
        today = fields.Date.context_today(self)
        waivers = self.sudo().search([('state', '=', 'approved'), ('expiry_date', '<', today)])
        result = {'expired': 0, 'errors': 0}
        for waiver in waivers:
            try:
                with self.env.cr.savepoint():
                    waiver._expire()
                result['expired'] += 1
            except Exception:
                result['errors'] += 1
                _logger.exception('ISMS waiver expiry failed for id %s', waiver.id)
        _logger.info('ISMS waiver expiry: %s', result)
        return result

    def _expire(self):
        self.ensure_one()
        self._isms_internal().write({'state': 'expired'})
        self.env['isms.finding']._upsert_from_source('monitoring', 'waiver-expired:%s' % self.id, {
            'name': _('Хугацаа дууссан эрсдлийн зөвшөөрөл %s') % self.code,
            'description': _('Зөвшөөрөл %s дууссан. Эрсдлийг дахин үнэлж, шинэ шийдвэр гаргана уу '
                             '(ISO/IEC 27001 6.1.3).') % self.code,
            'severity': 'high',
            'risk_id': self.risk_id.id,
            'owner_id': self.owner_id.id,
        })
        self.risk_id._flag_reeval(_('Зөвшөөрөл %s хугацаа дууссан') % self.code)
        return True
