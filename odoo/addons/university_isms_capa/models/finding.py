"""ISMS олдвор (finding). Бусад addon олдвор үүсгэхдээ `_upsert_from_source`-ийг ашиглана.

Гэрээ (contract):
- `source`: олдвор хаанаас ирсэн (control_test, monitoring, audit, incident, manual).
- `source_key`: эх сурвалжийн давтагдашгүй түлхүүр. Нэг түлхүүртэй нээлттэй олдвор давхар үүсэхгүй;
  дахин илэрвэл `occurrence_count` нэмэгдэж, `last_seen_at` шинэчлэгдэнэ.
- `state`: open, capa, verified, closed. Шилжилтийг зөвхөн сервер талын үйлдлүүд хийнэ:
  open→capa (CAPA эхэлнэ), capa→verified (бүх идэвхтэй CAPA баталгаажна),
  verified→closed (CISO), open/capa→closed (CISO, хүлээн зөвшөөрөх шалтгаантай).
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .common import GROUP_ANALYST, GROUP_CISO, require_group

SEVERITY = [('low', 'Бага'), ('medium', 'Дунд'), ('high', 'Өндөр'), ('critical', 'Ноцтой')]
SOURCE = [('control_test', 'Хяналтын тест'), ('monitoring', 'Мониторинг'), ('audit', 'Аудит'),
          ('incident', 'Зөрчил'), ('manual', 'Гараар')]
STATE = [('open', 'Нээлттэй'), ('capa', 'Залруулж буй'), ('verified', 'Баталгаажсан'), ('closed', 'Хаасан')]
ACTIVE_CAPA_STATES = ('draft', 'in_progress', 'implemented')


class IsmsFinding(models.Model):
    _name = 'isms.finding'
    _description = 'ISMS олдвор'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'isms.audit.mixin']
    _order = 'state_sequence, severity_sequence desc, detected_at desc, id desc'

    code = fields.Char('Дугаар', readonly=True, copy=False, default='New')
    name = fields.Char('Олдвор', required=True, tracking=True)
    description = fields.Text('Тайлбар')
    source = fields.Selection(SOURCE, 'Эх сурвалж', required=True, default='manual', tracking=True)
    source_key = fields.Char('Эх сурвалжийн түлхүүр', index=True, copy=False,
                             help='Нэг түлхүүртэй нээлттэй олдвор давхар үүсэхгүй.')
    severity = fields.Selection(SEVERITY, 'Ноцтой байдал', required=True, default='medium', tracking=True)
    severity_sequence = fields.Integer(compute='_compute_sequences', store=True)
    state = fields.Selection(STATE, 'Төлөв', required=True, default='open', tracking=True, copy=False)
    state_sequence = fields.Integer(compute='_compute_sequences', store=True)
    control_id = fields.Many2one('isms.control', 'Annex A хяналт', index=True, tracking=True)
    risk_id = fields.Many2one('isms.risk', 'Эрсдэл', index=True, tracking=True)
    asset_id = fields.Many2one('isms.asset', 'Хөрөнгө', index=True)
    owner_id = fields.Many2one('res.users', 'Хариуцагч', tracking=True, index=True)
    detected_at = fields.Datetime('Илэрсэн', required=True, default=fields.Datetime.now, readonly=True)
    last_seen_at = fields.Datetime('Сүүлд илэрсэн', readonly=True)
    occurrence_count = fields.Integer('Давтамж', default=1, readonly=True)
    closed_at = fields.Datetime('Хаасан', readonly=True, copy=False)
    acceptance_reason = fields.Text('Хүлээн зөвшөөрөх шалтгаан', tracking=True, copy=False,
                                    help='CAPA-гүйгээр эрсдлийг хүлээн зөвшөөрч хаахад CISO заавал бичнэ.')
    accepted_by_id = fields.Many2one('res.users', 'Хүлээн зөвшөөрсөн', readonly=True, copy=False)
    accepted_at = fields.Datetime('Хүлээн зөвшөөрсөн огноо', readonly=True, copy=False)
    capa_ids = fields.One2many('isms.capa', 'finding_id', 'Залруулах арга хэмжээ (CAPA)')
    capa_count = fields.Integer('CAPA тоо', compute='_compute_capa_count')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Олдворын дугаар давтагдахгүй.'),
    ]

    # Төлөв, хаасан огнооны өөрчлөлтийг зөвхөн сервер талын үйлдэл хийнэ (RPC/form-оос биш)
    _PROTECTED = {'state', 'closed_at', 'accepted_by_id', 'accepted_at'}

    @api.depends('state', 'severity')
    def _compute_sequences(self):
        states = [s[0] for s in STATE]
        severities = [s[0] for s in SEVERITY]
        for rec in self:
            rec.state_sequence = states.index(rec.state) if rec.state in states else 99
            rec.severity_sequence = severities.index(rec.severity) if rec.severity in severities else 0

    @api.depends('capa_ids')
    def _compute_capa_count(self):
        for rec in self:
            rec.capa_count = len(rec.capa_ids)

    @api.model_create_multi
    def create(self, vals_list):
        internal = self._isms_is_internal()
        for vals in vals_list:
            if not internal and (vals.get('state', 'open') != 'open' or self._PROTECTED & set(vals)):
                raise AccessError(_('Олдворын төлөв, хаасан огноог гараар тавих боломжгүй.'))
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('isms.finding') or 'New'
            vals.setdefault('last_seen_at', fields.Datetime.now())
        records = super().create(vals_list)
        # ISMS-07: өндөр/ноцтой олдвор эрсдэлтэй холбогдвол эрсдлийг дахин үнэлгээнд тэмдэглэнэ
        for rec in records:
            if rec.risk_id and rec.severity in ('high', 'critical'):
                rec.risk_id.sudo()._flag_reeval(_('%s: %s ноцтой байдлын олдвор илэрсэн') % (rec.code, rec.severity))
        return records

    def write(self, vals):
        if not self._isms_is_internal() and self._PROTECTED & set(vals):
            raise AccessError(_('Олдворын төлөвийг зөвхөн CAPA урсгалын товчлуураар өөрчилнө.'))
        return super().write(vals)

    @api.model
    def _upsert_from_source(self, source, source_key, vals):
        """Давхардалгүй олдвор үүсгэх эсвэл шинэчлэх. Буцаах: (олдвор, шинээр үүссэн эсэх).

        Дуудагч тал эрхээ өөрөө шалгана; автомат cron ба хяналтын тест энэ аргыг
        системийн нэрээр дуудаж болно.
        """
        existing = self.search([('source', '=', source), ('source_key', '=', source_key),
                                ('state', '!=', 'closed')], limit=1)
        if existing:
            existing.write({'last_seen_at': fields.Datetime.now(),
                            'occurrence_count': existing.occurrence_count + 1})
            return existing, False
        values = dict(vals, source=source, source_key=source_key)
        return self.create(values), True

    # ------------------------------------------------------------ CAPA урсгалын төлөвийн шилжилт
    def _capa_started(self):
        """CAPA эхэлсэн: open → capa. Бусад төлөвт нөлөөлөхгүй."""
        self.filtered(lambda f: f.state == 'open').sudo()._isms_internal().write({'state': 'capa'})

    def _sync_state_from_capas(self):
        """Бүх идэвхтэй CAPA баталгаажсан бол capa → verified. Цуцалсан CAPA-г тооцохгүй."""
        for rec in self.filtered(lambda f: f.state == 'capa'):
            active = rec.capa_ids.filtered(lambda c: c.state != 'cancelled')
            if active and all(c.state in ('verified', 'closed') for c in active):
                rec.sudo()._isms_internal().write({'state': 'verified'})

    def action_new_capa(self):
        self.ensure_one()
        require_group(self.env, GROUP_ANALYST, _('МАБ шинжээч'))
        if self.state in ('verified', 'closed'):
            raise UserError(_('%s: баталгаажсан эсвэл хаасан олдворт шинэ CAPA нээх боломжгүй.') % self.code)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Залруулах арга хэмжээ'),
            'res_model': 'isms.capa',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_finding_id': self.id},
        }

    def action_view_capas(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Залруулах арга хэмжээ'),
            'res_model': 'isms.capa',
            'view_mode': 'list,form',
            'domain': [('finding_id', '=', self.id)],
            'context': {'default_finding_id': self.id},
        }

    def action_accept_risk(self):
        """CAPA-гүйгээр хүлээн зөвшөөрч хаах (зөвхөн CISO, шалтгаан заавал)."""
        self.ensure_one()
        require_group(self.env, GROUP_CISO, _('МАБ менежер (CISO)'))
        if self.state not in ('open', 'capa'):
            raise UserError(_('%s: зөвхөн нээлттэй эсвэл залруулж буй олдворыг хүлээн зөвшөөрч хаана.') % self.code)
        if not (self.acceptance_reason or '').strip():
            raise UserError(_('%s: хүлээн зөвшөөрөх шалтгааныг бичнэ үү.') % self.code)
        if self.capa_ids.filtered(lambda c: c.state in ACTIVE_CAPA_STATES):
            raise UserError(_('%s: идэвхтэй CAPA байна. Эхлээд баталгаажуулах эсвэл цуцлана уу.') % self.code)
        now = fields.Datetime.now()
        self.sudo()._isms_internal().write({
            'state': 'closed', 'closed_at': now,
            'accepted_by_id': self.env.user.id, 'accepted_at': now,
        })
        return True

    def action_close(self):
        """Баталгаажсан олдворыг хаана (зөвхөн CISO)."""
        self.ensure_one()
        require_group(self.env, GROUP_CISO, _('МАБ менежер (CISO)'))
        if self.state != 'verified':
            raise UserError(_('%s: олдворыг зөвхөн CAPA баталгаажсаны дараа хаана.') % self.code)
        self.sudo()._isms_internal().write({'state': 'closed', 'closed_at': fields.Datetime.now()})
        return True
