"""Аудит лог (ISO/IEC 27001:2022 A.8.15 Logging, A.8.16 Monitoring, A.5.28 Collection of evidence).

`isms.audit.log` нь өөрчлөх, устгах боломжгүй бүртгэл. ISMS-ийн бүх модел `isms.audit.mixin`-ийг
inherit хийснээр create / write / unlink үйлдэл бүр хуучин → шинэ утгатайгаар бичигдэнэ.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

# Workflow-ийн дотоод token: Python объект тул JSON-RPC/context-оор хуурамчаар дамжуулах боломжгүй.
ISMS_TRANSITION_TOKEN = object()

AUDIT_ACTIONS = [
    ('create', 'Үүсгэсэн'),
    ('write', 'Өөрчилсөн'),
    ('state', 'Төлөв өөрчилсөн'),
    ('unlink', 'Устгасан'),
    ('login', 'Амжилттай нэвтэрсэн'),
    ('login_failed', 'Нэвтрэлт амжилтгүй'),
    ('access_change', 'Эрхийн өөрчлөлт'),
]


def client_ip():
    """HTTP хүсэлтийн IP хаяг (CLI/cron үед False)."""
    try:
        if request and request.httprequest:
            return request.httprequest.environ.get('REMOTE_ADDR')
    except RuntimeError:
        pass
    return False


class IsmsAuditLog(models.Model):
    _name = 'isms.audit.log'
    _description = 'ISMS аудит лог'
    _order = 'timestamp desc, id desc'
    _rec_name = 'res_name'

    timestamp = fields.Datetime('Огноо, цаг', default=fields.Datetime.now, required=True,
                                readonly=True, index=True)
    user_id = fields.Many2one('res.users', 'Хэрэглэгч', readonly=True, index=True, ondelete='set null')
    login = fields.Char('Нэвтрэх нэр', readonly=True)
    action = fields.Selection(AUDIT_ACTIONS, 'Үйлдэл', required=True, readonly=True, index=True)
    model = fields.Char('Модел', readonly=True, index=True)
    model_name = fields.Char('Объект', readonly=True)
    res_id = fields.Integer('Бичлэгийн ID', readonly=True)
    res_name = fields.Char('Бичлэг', readonly=True)
    changes = fields.Text('Өөрчлөлт (хуучин → шинэ)', readonly=True)
    ip_address = fields.Char('IP хаяг', readonly=True)

    @api.model
    def _log(self, action, records=None, changes=None, model=None, res_name=None):
        """Аудит бичлэг үүсгэнэ. `changes` нь текст эсвэл {record_id: текст} dict."""
        user = self.env.user
        base = {
            'action': action,
            'user_id': user.id,
            'login': user.login,
            'ip_address': client_ip(),
        }
        vals_list = []
        if records:
            for rec in records:
                text = changes.get(rec.id) if isinstance(changes, dict) else changes
                vals_list.append(dict(base, model=rec._name, model_name=rec._description,
                                      res_id=rec.id, res_name=rec.sudo().display_name, changes=text))
        else:
            vals_list.append(dict(base, model=model, res_name=res_name, changes=changes))
        return self.sudo().create(vals_list)

    def write(self, vals):
        raise UserError(_('Аудит логийг өөрчлөх боломжгүй (ISO/IEC 27001:2022 A.8.15).'))

    def unlink(self):
        raise UserError(_('Аудит логийг устгах боломжгүй (ISO/IEC 27001:2022 A.8.15).'))


class IsmsAuditMixin(models.AbstractModel):
    _name = 'isms.audit.mixin'
    _description = 'ISMS аудит лог mixin'

    _isms_audit_skip_fields = {'write_date', 'write_uid', 'create_date', 'create_uid', 'display_name'}
    _isms_audit_skip_prefixes = ('message_', 'activity_', 'website_message', 'has_message')

    def _isms_is_internal(self):
        """Сервер талын workflow (token) эсвэл superuser код эсэх. RPC-ээс ирсэн context хүрэлцэхгүй."""
        return self.env.su or self.env.context.get('isms_transition') is ISMS_TRANSITION_TOKEN

    def _isms_internal(self):
        return self.with_context(isms_transition=ISMS_TRANSITION_TOKEN)

    @api.model
    def _isms_next_code(self, sequence_code):
        """Sequence-ээс дараагийн код (импортоор орсон кодтой давхардвал алгасна)."""
        sequence = self.env['ir.sequence'].sudo()
        code = '/'
        for _attempt in range(100):
            code = sequence.next_by_code(sequence_code) or '/'
            if not self.sudo().with_context(active_test=False).search_count([('code', '=', code)]):
                break
        return code

    def _isms_audit_fields(self, fnames):
        result = []
        for fname in fnames:
            field = self._fields.get(fname)
            if (not field or fname in self._isms_audit_skip_fields
                    or fname.startswith(self._isms_audit_skip_prefixes)
                    or (field.compute and not field.store and not field.inverse)):
                continue
            result.append(fname)
        return result

    def _isms_audit_value(self, fname):
        self.ensure_one()
        field = self._fields[fname]
        value = self[fname]
        if field.type == 'many2one':
            return value.display_name or ''
        if field.type in ('many2many', 'one2many'):
            return ', '.join(value.mapped('display_name'))
        if field.type == 'selection':
            return dict(field._description_selection(self.env)).get(value, value or '')
        if field.type == 'html':
            return html2plaintext(value or '')[:300]
        if field.type == 'boolean':
            return 'Тийм' if value else 'Үгүй'
        if value is False or value is None:
            return ''
        return str(value)[:500]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env['isms.audit.log']._log('create', records)
        return records

    _isms_lock_code = False  # sequence-ээр олгосон дугаарыг гараар өөрчлөхийг хориглох эсэх

    def write(self, vals):
        if self._isms_lock_code and 'code' in vals and not self._isms_is_internal() \
                and any(rec.code != vals['code'] for rec in self):
            from odoo.exceptions import AccessError
            raise AccessError(_('Бүртгэлийн дугаарыг өөрчлөх боломжгүй.'))
        fnames = self._isms_audit_fields(vals.keys())
        old = {}
        if fnames:
            for rec in self.sudo():
                old[rec.id] = {f: rec._isms_audit_value(f) for f in fnames}
        res = super().write(vals)
        if fnames:
            changes = {}
            for rec in self.sudo():
                lines = []
                for fname in fnames:
                    new = rec._isms_audit_value(fname)
                    if old[rec.id][fname] != new:
                        lines.append('%s: %s → %s' % (rec._fields[fname].string,
                                                      old[rec.id][fname] or '∅', new or '∅'))
                if lines:
                    changes[rec.id] = '\n'.join(lines)
            if changes:
                action = 'state' if 'state' in fnames else 'write'
                self.env['isms.audit.log']._log(action, self.browse(list(changes)), changes)
        return res

    def unlink(self):
        self.env['isms.audit.log']._log(
            'unlink', self, {rec.id: 'Устгагдсан: %s' % rec.sudo().display_name for rec in self})
        return super().unlink()
