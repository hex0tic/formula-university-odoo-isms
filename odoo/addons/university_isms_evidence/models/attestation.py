"""ISMS-06 Бодлогын баталгаажуулалт: кампанит ажил ба хэрэглэгч тус бүрийн баталгаажуулалт.

Харьцаа isms.policy.ack-тай:
* isms.policy.ack (танилцсан бүртгэл, A.5.37) нь хэвээр үлдэж, бодлогын хувилбар бүрийн «уншсан»
  тэмдэглэл болно. Эдгээр өөрчлөгдөөгүй.
* Энэ модуль нэмэлтээр хамрах хүрээ (бүх хэрэглэгч / бүлэг), хүчинтэй хугацаа, бодлогын хувилбартай
  холбосон албан ёсны баталгаажуулалтыг хөтөлнө. Ажилтан «Баталгаажуулах» үед тухайн хувилбарт
  isms.policy.ack бүртгэл байхгүй бол нэмэх тул хоёр бүртгэл зөрөхгүй.

Төлөв (isms.policy.attestation.state):
* pending: хүлээгдэж буй
* attested: баталгаажсан, хүчинтэй
* expired: хүчинтэй хугацаа дууссан (cron)
* stale: бодлогын шинэ хувилбар гарсан тул хуучирсан (хувилбар таарахгүй)
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

GROUP_ANALYST = 'university_isms.group_isms_analyst'
GROUP_AUDITOR = 'university_isms.group_isms_auditor'
_CHATTER_PREFIXES = ('message_', 'activity_')
_META_KEYS = {'write_date', 'write_uid', 'display_name'}


class IsmsPolicyAttestationCampaign(models.Model):
    _name = 'isms.policy.attestation.campaign'
    _description = 'Бодлогын баталгаажуулалтын кампанит ажил'
    _inherit = ['mail.thread', 'isms.audit.mixin']
    _order = 'id desc'

    name = fields.Char('Кампанит ажлын нэр', required=True, tracking=True)
    policy_id = fields.Many2one('isms.policy', 'Бодлого', required=True, tracking=True, index=True,
                                domain=[('state', '=', 'approved')])
    policy_revision = fields.Char('Бодлогын хувилбар (revision)', readonly=True, copy=False,
                                  help='Кампанит ажил үүсэх үеийн бодлогын хувилбар.')
    scope = fields.Selection([
        ('all', 'Бүх дотоод хэрэглэгч'),
        ('groups', 'Сонгосон бүлгийн хэрэглэгч'),
    ], 'Хамрах хүрээ', required=True, default='all', tracking=True)
    group_ids = fields.Many2many('res.groups', 'isms_attest_campaign_group_rel', 'campaign_id', 'group_id',
                                 string='Бүлгүүд')
    start_date = fields.Date('Эхлэх огноо', required=True, default=fields.Date.context_today)
    due_date = fields.Date('Дуусах хугацаа', required=True, tracking=True)
    validity_days = fields.Integer('Баталгаажуулалтын хүчинтэй хоног', required=True, default=365,
                                   help='Баталгаажуулсны дараа хэдэн хоног хүчинтэй байх.')
    state = fields.Selection([
        ('draft', 'Ноорог'),
        ('open', 'Нээлттэй'),
        ('closed', 'Хаагдсан'),
    ], 'Төлөв', required=True, default='draft', tracking=True, copy=False)
    attestation_ids = fields.One2many('isms.policy.attestation', 'campaign_id', 'Баталгаажуулалт')
    total_count = fields.Integer('Нийт', compute='_compute_counts')
    attested_count = fields.Integer('Баталгаажсан', compute='_compute_counts')
    open_count = fields.Integer('Хүлээгдэж буй / хуучирсан', compute='_compute_counts')

    @api.depends('attestation_ids.state')
    def _compute_counts(self):
        for rec in self:
            states = rec.attestation_ids.mapped('state')
            rec.total_count = len(states)
            rec.attested_count = states.count('attested')
            rec.open_count = states.count('pending') + states.count('stale') + states.count('expired')

    # ------------------------------------------------------------ ORM
    @api.constrains('start_date', 'due_date', 'validity_days', 'scope', 'group_ids')
    def _check_campaign(self):
        for rec in self:
            if rec.due_date and rec.start_date and rec.due_date < rec.start_date:
                raise UserError(_('Дуусах хугацаа эхлэх огнооноос өмнө байж болохгүй.'))
            if rec.validity_days < 1:
                raise UserError(_('Хүчинтэй хугацаа дор хаяж 1 хоног байна.'))
            if rec.scope == 'groups' and not rec.group_ids:
                raise UserError(_('Бүлгийн хамрах хүрээнд хамгийн багадаа нэг бүлэг сонгоно.'))

    @api.model_create_multi
    def create(self, vals_list):
        internal = self._isms_is_internal()
        for vals in vals_list:
            if not internal:
                if set(vals) & {'policy_revision', 'state'}:
                    raise AccessError(_('Хувилбар болон төлөвийг гараар тохируулах боломжгүй.'))
            policy = self.env['isms.policy'].browse(vals.get('policy_id'))
            if not policy or policy.state != 'approved':
                raise UserError(_('Зөвхөн батлагдсан бодлогод баталгаажуулалтын кампанит ажил нээнэ.'))
            vals['policy_revision'] = policy.version
            vals.setdefault('state', 'draft')
        return super().create(vals_list)

    def write(self, vals):
        if not vals:
            return True
        if not self._isms_is_internal():
            content = {k for k in vals if not k.startswith(_CHATTER_PREFIXES) and k not in _META_KEYS}
            if content & {'policy_revision', 'state'}:
                raise AccessError(_('Төлөв болон бодлогын хувилбарыг зөвхөн үйлдлээр өөрчилнө.'))
            if content and any(rec.state != 'draft' for rec in self):
                raise UserError(_('Нээгдсэн эсвэл хаагдсан кампанитай ажлыг засах боломжгүй.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise AccessError(_('Кампанит ажлыг устгах боломжгүй (аудитын түүх).'))
        return super().unlink()

    # ------------------------------------------------------------ helpers
    def _isms_require_analyst(self):
        if not self.env.su and not self.env.user.has_group(GROUP_ANALYST):
            raise AccessError(_('Кампанит ажлыг зөвхөн МАБ шинжээч эсвэл менежер удирдана.'))

    def _scope_users(self):
        """Хамрах хүрээний дотоод хэрэглэгчид (selection-ийг серверт хийнэ)."""
        self.ensure_one()
        domain = [('share', '=', False), ('active', '=', True)]
        if self.scope == 'groups':
            domain.append(('groups_id', 'in', self.group_ids.ids))
        return self.env['res.users'].sudo().search(domain)

    def action_open(self):
        self.ensure_one()
        self._isms_require_analyst()
        if self.state != 'draft':
            raise UserError(_('Зөвхөн ноорог кампанитай ажлыг нээнэ.'))
        policy = self.policy_id
        if policy.state != 'approved' or policy.version != self.policy_revision:
            raise UserError(_('Бодлогын хувилбар өөрчлөгдсөн байна. Шинэ кампанит ажил үүсгэнэ үү.'))
        existing = set(self.attestation_ids.user_id.ids)
        vals_list = [{'campaign_id': self.id, 'user_id': user.id}
                     for user in self._scope_users() if user.id not in existing]
        self._isms_internal().write({'state': 'open'})
        if vals_list:
            self.env['isms.policy.attestation'].sudo().create(vals_list)
        return True

    def action_close(self):
        self.ensure_one()
        self._isms_require_analyst()
        if self.state != 'open':
            raise UserError(_('Зөвхөн нээлттэй кампанитай ажлыг хаана.'))
        self._isms_internal().write({'state': 'closed'})
        return True


class IsmsPolicyAttestation(models.Model):
    _name = 'isms.policy.attestation'
    _description = 'Бодлогын баталгаажуулалт (хэрэглэгч тус бүр)'
    _inherit = ['isms.audit.mixin']
    _order = 'id desc'
    _rec_names_search = ['user_id']

    campaign_id = fields.Many2one('isms.policy.attestation.campaign', 'Кампанит ажил', required=True,
                                  ondelete='cascade', index=True)
    policy_id = fields.Many2one(related='campaign_id.policy_id', store=True, readonly=True, index=True,
                                string='Бодлого')
    user_id = fields.Many2one('res.users', 'Хэрэглэгч', required=True, index=True, ondelete='restrict')
    revision = fields.Char('Баталгаажуулсан хувилбар', readonly=True, copy=False)
    attested_at = fields.Datetime('Баталгаажуулсан огноо', readonly=True, copy=False)
    expires_on = fields.Date('Хүчинтэй дуусах огноо', readonly=True, copy=False, index=True)
    state = fields.Selection([
        ('pending', 'Хүлээгдэж буй'),
        ('attested', 'Баталгаажсан'),
        ('expired', 'Хугацаа дууссан'),
        ('stale', 'Шинэ хувилбараар хуучирсан'),
    ], 'Төлөв', compute='_compute_state', store=True, index=True)
    is_mine = fields.Boolean('Миний', compute='_compute_is_mine')

    _sql_constraints = [
        ('campaign_user_uniq', 'unique(campaign_id, user_id)',
         'Нэг хэрэглэгч нэг кампанит ажилд нэг удаа баталгаажуулна.'),
    ]

    @api.depends('campaign_id.name', 'user_id.name')
    def _compute_display_name(self):
        for rec in self:
            campaign = rec.sudo().campaign_id
            rec.display_name = '%s / %s' % (campaign.name or '', rec.sudo().user_id.name or '')

    @api.depends('attested_at', 'revision', 'expires_on', 'policy_id.version')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.attested_at:
                rec.state = 'pending'
            elif rec.revision != rec.policy_id.sudo().version:
                rec.state = 'stale'
            elif rec.expires_on and rec.expires_on < today:
                rec.state = 'expired'
            else:
                rec.state = 'attested'

    @api.depends_context('uid')
    def _compute_is_mine(self):
        for rec in self:
            rec.is_mine = rec.user_id.id == self.env.uid

    # ------------------------------------------------------------ ORM
    @api.model_create_multi
    def create(self, vals_list):
        if not self._isms_is_internal():
            if not self.env.user.has_group(GROUP_ANALYST):
                raise AccessError(_('Баталгаажуулалтыг зөвхөн МАБ шинжээч үүсгэнэ.'))
            for vals in vals_list:
                if set(vals) & {'state', 'revision', 'attested_at', 'expires_on'}:
                    raise AccessError(_('Баталгаажуулалтын системийн талбарыг гараар тохируулах боломжгүй.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self._isms_is_internal():
            raise AccessError(_('Баталгаажуулалтыг өөрчлөх боломжгүй. Өөрөө «Баталгаажуулах» товчийг ашиглана.'))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise AccessError(_('Баталгаажуулалтын бүртгэлийг устгах боломжгүй (аудитын түүх).'))
        return super().unlink()

    # ------------------------------------------------------------ actions
    def action_attest(self):
        """Хэрэглэгч зөвхөн ӨӨРИЙНХӨӨ бүртгэлийг баталгаажуулна."""
        self.ensure_one()
        if self.user_id.id != self.env.uid:
            raise AccessError(_('Та зөвхөн өөрийнхөө бодлогын баталгаажуулалтыг хийнэ.'))
        # Кампанит ажил, бодлогын талбарыг хэрэглэгчийн эрхээс үл хамааран шалгана (зөвхөн уншина)
        campaign = self.campaign_id.sudo()
        policy = campaign.policy_id.sudo()
        if campaign.state != 'open':
            raise UserError(_('Кампанит ажил нээлттэй биш байна.'))
        if self.state != 'pending':
            raise UserError(_('Энэ баталгаажуулалт аль хэдийн хийгдсэн эсвэл хуучирсан байна.'))
        if policy.state != 'approved' or policy.version != campaign.policy_revision:
            raise UserError(_('Бодлогын хувилбар өөрчлөгдсөн байна. Шинэ кампанит ажлаар баталгаажуулна уу.'))
        today = fields.Date.context_today(self)
        self.sudo().write({
            'attested_at': fields.Datetime.now(),
            'revision': policy.version,
            'expires_on': today + relativedelta(days=campaign.validity_days),
        })
        # Танилцсан бүртгэлийг (isms.policy.ack) давхардуулахгүйгээр нэмнэ
        Ack = self.env['isms.policy.ack'].sudo()
        if not Ack.search_count([('policy_id', '=', policy.id), ('user_id', '=', self.user_id.id),
                                 ('version', '=', policy.version)]):
            Ack.create({'policy_id': policy.id, 'user_id': self.user_id.id, 'version': policy.version})
        return True

    @api.model
    def _cron_expire_attestations(self):
        """Хугацаа дууссан баталгаажуулалтыг 'expired' болгоно (өдөр тутмын cron)."""
        today = fields.Date.context_today(self)
        due = self.sudo().search([('state', '=', 'attested'), ('expires_on', '!=', False),
                                  ('expires_on', '<', today)])
        if due:
            due.modified(['expires_on'])
            self.env.flush_all()
        return len(due)
