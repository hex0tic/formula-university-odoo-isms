"""ISMS-01 Нотлох баримтын сан (Evidence Vault).

* Файлыг ir.attachment-д хадгална. SHA-256 нийлбэр, хэмжээ, MIME төрлийг СЕРВЕРТ хадгалсан байтаас
  тооцно; клиентээс ирсэн нийлбэрийг хүлээж авахгүй.
* Батлагдсан нотолгоо өөрчлөгдөхгүй (агуулга, нийлбэр, холбоос, хугацаа). Өөрчлөлт бүр шинэ хувилбар
  (previous_version_id) болж бүртгэгдэнэ.
* Хянагч нь эзэмшигч / оруулагчаас өөр, аудитор эсвэл МАБ менежер (CISO) байна. Батлах, татгалзах
  үйлдлийг зөвхөн томилогдсон хянагч хийнэ.
* Устгах: зөвхөн оруулсан хүн, ноорог төлөвөөс.
"""
import base64
import hashlib
import mimetypes
import os

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

GROUP_OWNER = 'university_isms.group_isms_asset_owner'
GROUP_ANALYST = 'university_isms.group_isms_analyst'
GROUP_AUDITOR = 'university_isms.group_isms_auditor'
GROUP_MANAGER = 'university_isms.group_isms_manager'

EVIDENCE_STATES = [
    ('draft', 'Ноорог'),
    ('submitted', 'Хянахаар илгээсэн'),
    ('approved', 'Батлагдсан'),
    ('rejected', 'Татгалзсан'),
]
EVIDENCE_SOURCES = [
    ('manual', 'Гараар оруулсан'),
    ('system', 'Системээс авсан'),
    ('test', 'Туршилтын'),
]

# Серверээс тооцдог / зөвхөн workflow-оор өөрчлөгдөх талбарууд (клиент шууд бичиж болохгүй)
_SERVER_ONLY = {'sha256', 'file_size', 'mimetype', 'version', 'uploaded_by_id',
                'previous_version_id', 'reviewed_at'}
_CHATTER_PREFIXES = ('message_', 'activity_')
_META_KEYS = {'write_date', 'write_uid', 'display_name'}


def _digest(value):
    """base64 утгаас (sha256 hex, байтын тоо) тооцно."""
    raw = base64.b64decode(value) if value else b''
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _safe_name(name):
    """Файлын нэрнээс зам хэсгийг хасна (path traversal-аас хамгаална)."""
    return os.path.basename((name or '').replace('\\', '/')) or 'evidence'


class IsmsEvidence(models.Model):
    _name = 'isms.evidence'
    _description = 'Нотлох баримт (Evidence Vault)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'isms.audit.mixin']
    _order = 'id desc'
    _rec_names_search = ['name', 'file_name', 'sha256']
    # Файлын агуулгыг аудит лог руу хуулахгүй (base64 агуулга, нууц мэдээлэл)
    _isms_audit_skip_fields = {'write_date', 'write_uid', 'create_date', 'create_uid',
                               'display_name', 'attachment'}

    name = fields.Char('Нэр', required=True, tracking=True)
    description = fields.Text('Тайлбар')
    control_ids = fields.Many2many('isms.control', 'isms_evidence_control_rel', 'evidence_id', 'control_id',
                                   string='Холбогдох Annex A хяналт', tracking=True)
    asset_id = fields.Many2one('isms.asset', 'Хөрөнгө', tracking=True, index=True)
    risk_id = fields.Many2one('isms.risk', 'Эрсдэл', tracking=True)
    owner_id = fields.Many2one('res.users', 'Эзэмшигч', required=True, tracking=True, index=True,
                               default=lambda self: self.env.user)
    uploaded_by_id = fields.Many2one('res.users', 'Оруулсан хүн', readonly=True, copy=False, index=True,
                                     default=lambda self: self.env.user)
    attachment = fields.Binary('Файл', attachment=True)
    file_name = fields.Char('Файлын нэр')
    file_size = fields.Integer('Хэмжээ (байт)', readonly=True, copy=False)
    mimetype = fields.Char('MIME төрөл', readonly=True, copy=False)
    sha256 = fields.Char('SHA-256 нийлбэр', readonly=True, copy=False, index=True,
                         help='Хадгалсан файлын байтаас серверт тооцсон.')
    version = fields.Integer('Хувилбар', readonly=True, copy=False, default=1)
    previous_version_id = fields.Many2one('isms.evidence', 'Өмнөх хувилбар', readonly=True, copy=False,
                                          ondelete='restrict')
    next_version_ids = fields.One2many('isms.evidence', 'previous_version_id', 'Дараагийн хувилбар')
    is_superseded = fields.Boolean('Шинэ хувилбараар солигдсон', compute='_compute_is_superseded')
    state = fields.Selection(EVIDENCE_STATES, 'Төлөв', default='draft', required=True, tracking=True,
                             copy=False)
    reviewer_id = fields.Many2one('res.users', 'Хянагч (аудитор / CISO)', tracking=True, copy=False)
    reviewed_at = fields.Datetime('Хянасан огноо', readonly=True, copy=False)
    review_note = fields.Text('Хянагчийн тэмдэглэл', copy=False)
    valid_until = fields.Date('Хүчинтэй дуусах огноо', tracking=True)
    is_expired = fields.Boolean('Хугацаа дууссан', compute='_compute_is_expired',
                                search='_search_is_expired')
    collected_at = fields.Datetime('Цуглуулсан огноо', required=True, default=fields.Datetime.now)
    source = fields.Selection(EVIDENCE_SOURCES, 'Эх сурвалж', required=True, default='manual')
    can_submit = fields.Boolean(compute='_compute_permissions')
    is_reviewer = fields.Boolean(compute='_compute_permissions')

    _sql_constraints = [
        ('previous_version_uniq', 'unique(previous_version_id)',
         'Нэг хувилбарт зөвхөн нэг дараагийн хувилбар байж болно.'),
    ]

    # ------------------------------------------------------------ compute
    @api.depends('name', 'version')
    def _compute_display_name(self):
        for rec in self:
            ident = rec.id if isinstance(rec.id, int) else 0
            rec.display_name = '[EV-%05d] %s (v%s)' % (ident, rec.name or '', rec.version or 1)

    @api.depends('next_version_ids.state')
    def _compute_is_superseded(self):
        for rec in self:
            rec.is_superseded = any(v.state == 'approved' for v in rec.next_version_ids)

    def _search_is_expired(self, operator, value):
        today = fields.Date.context_today(self)
        expired = [('valid_until', '<', today)]
        if (operator == '=' and value) or (operator == '!=' and not value):
            return expired
        return ['|', ('valid_until', '=', False), ('valid_until', '>=', today)]

    @api.depends('valid_until')
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = bool(rec.valid_until and rec.valid_until < today)

    @api.depends('owner_id', 'uploaded_by_id', 'reviewer_id')
    @api.depends_context('uid')
    def _compute_permissions(self):
        user = self.env.user
        for rec in self:
            rec.can_submit = user in (rec.owner_id | rec.uploaded_by_id)
            rec.is_reviewer = bool(rec.reviewer_id) and rec.reviewer_id == user

    # ------------------------------------------------------------ constraints
    @api.constrains('reviewer_id', 'owner_id', 'uploaded_by_id')
    def _check_reviewer_separation(self):
        for rec in self:
            reviewer = rec.reviewer_id
            if not reviewer:
                continue
            if reviewer in (rec.owner_id | rec.uploaded_by_id):
                raise ValidationError(_('Нотлох баримтыг эзэмшигч эсвэл оруулсан хүн өөрөө хянаж батлах '
                                        'боломжгүй (үүрэг салгах).'))
            if not (reviewer.sudo().has_group(GROUP_AUDITOR) or reviewer.sudo().has_group(GROUP_MANAGER)):
                raise ValidationError(_('Хянагчаар зөвхөн дотоод аудитор эсвэл МАБ менежер (CISO) томилно.'))

    # ------------------------------------------------------------ digest helpers
    def _isms_read_digest(self):
        """Хадгалсан файлыг дахин уншиж (raw bytes, sha256 hex) буцаана. Файлгүй бол (None, None)."""
        self.ensure_one()
        self.invalidate_recordset(['attachment'])
        value = self.attachment
        if not value:
            return None, None
        raw = base64.b64decode(value)
        return raw, hashlib.sha256(raw).hexdigest()

    def _digest_check(self):
        """'match' | 'mismatch' | 'missing'."""
        self.ensure_one()
        raw, actual = self._isms_read_digest()
        if raw is None:
            return 'missing'
        return 'match' if actual == self.sha256 else 'mismatch'

    def _isms_fill_digest(self, vals):
        """Серверт файлын нийлбэр, хэмжээ, MIME-г тооцоолж vals-д нэмнэ."""
        if 'file_name' in vals:
            vals['file_name'] = _safe_name(vals['file_name'])
        value = vals.get('attachment')
        if value:
            digest, size = _digest(value)
            file_name = vals.get('file_name') or (self[:1].file_name if self else '') or ''
            vals.update({
                'sha256': digest,
                'file_size': size,
                'mimetype': mimetypes.guess_type(file_name)[0] or 'application/octet-stream',
            })
        else:
            vals.update({'sha256': False, 'file_size': 0, 'mimetype': False})

    # ------------------------------------------------------------ ORM
    @api.model_create_multi
    def create(self, vals_list):
        internal = self._isms_is_internal()
        for vals in vals_list:
            if not internal:
                if set(vals) & _SERVER_ONLY or vals.get('state', 'draft') != 'draft':
                    raise AccessError(_('Системийн талбарыг (нийлбэр, хувилбар, төлөв, оруулсан хүн) '
                                        'гараар тохируулах боломжгүй.'))
                vals['uploaded_by_id'] = self.env.uid
            prev = self.browse(vals['previous_version_id']) if vals.get('previous_version_id') else self.browse()
            vals['version'] = prev.version + 1 if prev else 1
            if 'attachment' in vals:
                self._isms_fill_digest(vals)
        return super().create(vals_list)

    def _isms_user_can_edit(self, rec):
        user = self.env.user
        return user.has_group(GROUP_ANALYST) or user in (rec.owner_id | rec.uploaded_by_id)

    def write(self, vals):
        if not vals:
            return True
        if not self._isms_is_internal():
            content = {k for k in vals if not k.startswith(_CHATTER_PREFIXES) and k not in _META_KEYS}
            if content & (_SERVER_ONLY | {'state'}):
                raise AccessError(_('Системийн талбарыг (төлөв, нийлбэр, хувилбар, оруулсан хүн) гараар '
                                    'засах боломжгүй.'))
            if content:
                review_note_only = content == {'review_note'} and all(
                    rec.state == 'submitted' and rec.reviewer_id == self.env.user for rec in self)
                if not review_note_only:
                    if any(rec.state not in ('draft', 'rejected') for rec in self):
                        raise UserError(_('Энэ төлөвт нотолгоог засах боломжгүй. Батлагдсан бол шинэ хувилбар '
                                          'үүсгэнэ; хянуулахаар илгээсэн бол эхлээд буцаан авна.'))
                    for rec in self:
                        if not self._isms_user_can_edit(rec):
                            raise AccessError(_('Энэ нотолгоог засах эрх байхгүй.'))
        if 'attachment' in vals:
            self._isms_fill_digest(vals)
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not self._isms_is_internal():
            for rec in self:
                if rec.state != 'draft' or rec.uploaded_by_id != self.env.user:
                    raise AccessError(_('Нотлох баримтыг зөвхөн оруулсан хүн, ноорог төлөвөөс устгана.'))
        return super().unlink()

    # ------------------------------------------------------------ workflow
    def _isms_check_owner_or_uploader(self):
        if self.env.su:
            return
        if self.env.user not in (self.owner_id | self.uploaded_by_id):
            raise AccessError(_('Зөвхөн эзэмшигч эсвэл оруулсан хүн энэ үйлдлийг хийнэ.'))

    def _isms_check_reviewer(self):
        self.ensure_one()
        if self.env.su:
            return
        user = self.env.user
        if not (user.has_group(GROUP_AUDITOR) or user.has_group(GROUP_MANAGER)):
            raise AccessError(_('Зөвхөн дотоод аудитор эсвэл МАБ менежер (CISO) хянана.'))
        if self.reviewer_id != user:
            raise AccessError(_('Зөвхөн энэ нотолгоонд томилогдсон хянагч батална.'))
        if user in (self.owner_id | self.uploaded_by_id):
            raise AccessError(_('Өөрийн оруулсан нотолгоог өөрөө хянаж болохгүй.'))

    def action_submit(self):
        self.ensure_one()
        self._isms_check_owner_or_uploader()
        if self.state not in ('draft', 'rejected'):
            raise UserError(_('Зөвхөн ноорог эсвэл татгалзсан нотолгоог хянуулахаар илгээнэ.'))
        missing = []
        if not self.attachment:
            missing.append(_('файл'))
        if not self.control_ids:
            missing.append(_('Annex A хяналт'))
        if not self.valid_until:
            missing.append(_('хүчинтэй дуусах огноо'))
        if not self.reviewer_id:
            missing.append(_('хянагч'))
        if missing:
            raise UserError(_('Дутуу талбар: %s') % ', '.join(missing))
        if self.valid_until < fields.Date.context_today(self):
            raise UserError(_('Хүчинтэй дуусах огноо өнгөрсөн байна.'))
        self._isms_internal().write({'state': 'submitted'})
        return True

    def action_withdraw(self):
        self.ensure_one()
        self._isms_check_owner_or_uploader()
        if self.state != 'submitted':
            raise UserError(_('Зөвхөн хянуулахаар илгээсэн нотолгоог буцаан авна.'))
        self._isms_internal().write({'state': 'draft'})
        return True

    def action_approve(self):
        self.ensure_one()
        self._isms_check_reviewer()
        if self.state != 'submitted':
            raise UserError(_('Зөвхөн хянуулахаар илгээсэн нотолгоог батална.'))
        if not self.valid_until or self.valid_until < fields.Date.context_today(self):
            raise UserError(_('Хугацаа дууссан эсвэл огноогүй нотолгоог батлахгүй.'))
        check = self._digest_check()
        if check != 'match':
            raise UserError(_('SHA-256 шалгалт тэнцээгүй (%s). Батлах боломжгүй.') % check)
        self._isms_internal().write({'state': 'approved', 'reviewed_at': fields.Datetime.now()})
        self.message_post(body=_('Батлагдсан. SHA-256: %s') % self.sha256)
        return True

    def action_reject(self):
        self.ensure_one()
        self._isms_check_reviewer()
        if self.state != 'submitted':
            raise UserError(_('Зөвхөн хянуулахаар илгээсэн нотолгоог татгалзана.'))
        if not (self.review_note or '').strip():
            raise UserError(_('Татгалзахдаа хянагчийн тэмдэглэл заавал бичнэ.'))
        self._isms_internal().write({'state': 'rejected', 'reviewed_at': fields.Datetime.now()})
        self.message_post(body=_('Татгалзсан: %s') % self.review_note)
        return True

    def action_new_version(self):
        """Батлагдсан нотолгооны шинэ хувилбар (өмнөхтэй холбоотой, ноорог)."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Шинэ хувилбар зөвхөн батлагдсан нотолгооноос үүснэ.'))
        if not (self.env.user.has_group(GROUP_ANALYST) or self.env.user in (self.owner_id | self.uploaded_by_id)):
            raise AccessError(_('Шинэ хувилбар үүсгэх эрх байхгүй.'))
        new = self._isms_internal().create({
            'name': self.name,
            'description': self.description,
            'control_ids': [(6, 0, self.control_ids.ids)],
            'asset_id': self.asset_id.id or False,
            'risk_id': self.risk_id.id or False,
            'owner_id': self.owner_id.id,
            'source': self.source,
            'previous_version_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'isms.evidence',
            'res_id': new.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_verify_digest(self):
        """Файлыг дахин хэшлэж бүртгэсэн нийлбэртэй харьцуулна. Үр дүнг чатад болон аудит логт бичнэ."""
        self.ensure_one()
        status = self._digest_check()
        labels = {
            'match': _('тохирсон'),
            'mismatch': _('ТОХИРОХГҮЙ (файл өөрчлөгдсөн байна)'),
            'missing': _('файл алга'),
        }
        msg = _('SHA-256 шалгалт: %(result)s. Бүртгэгдсэн нийлбэр: %(digest)s') % {
            'result': labels[status], 'digest': self.sha256 or '-'}
        self.message_post(body=msg)
        self.env['isms.audit.log']._log('write', self, {self.id: msg})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Нийлбэр шалгалт'),
                'message': msg,
                'type': 'success' if status == 'match' else 'danger',
                'sticky': False,
            },
        }
