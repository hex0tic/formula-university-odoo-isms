"""Гинжийн толгой: сүүлийн seq/хэш, дамжуулалтын курсор, сүүлийн шалгалтын үр дүн."""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .audit_chain import GENESIS_HASH
from .audit_forward import get_setting

GROUP_AUDITOR = 'university_isms.group_isms_auditor'
GROUP_MANAGER = 'university_isms.group_isms_manager'


class IsmsAuditChainHead(models.Model):
    _name = 'isms.audit.chain.head'
    _description = 'ISMS аудит гинжийн толгой ба төлөв'

    name = fields.Char('Нэр', default='Аудит гинжийн толгой', readonly=True)
    last_seq = fields.Integer('Сүүлийн гинжийн дугаар', default=0, readonly=True, copy=False)
    last_hash = fields.Char('Сүүлийн бичлэгийн хэш', default=GENESIS_HASH, readonly=True, copy=False)
    forward_file_seq = fields.Integer('Файлд илгээсэн сүүлийн seq', default=0, readonly=True, copy=False)
    forward_http_seq = fields.Integer('HTTP-д илгээсэн сүүлийн seq', default=0, readonly=True, copy=False)
    last_verified_at = fields.Datetime('Сүүлийн шалгалтын огноо', readonly=True, copy=False)
    last_verified_ok = fields.Boolean('Сүүлийн шалгалт бүрэн', readonly=True, copy=False)
    last_verified_checked = fields.Integer('Шалгасан бичлэг', readonly=True, copy=False)
    last_verified_seq = fields.Integer('Эвдрэлийн seq', readonly=True, copy=False)
    last_verified_reason = fields.Char('Шалгалтын үр дүн', readonly=True, copy=False)

    chained_count = fields.Integer('Гинжинд орсон бичлэг', compute='_compute_status')
    unchained_count = fields.Integer('Гинжинд ороогүй бичлэг', compute='_compute_status')
    file_target_state = fields.Char('Файлын дамжуулалт', compute='_compute_status')
    http_target_state = fields.Char('HTTP дамжуулалт', compute='_compute_status')
    queue_pending = fields.Integer('Хүлээгдэж буй багц', compute='_compute_status')
    queue_failed = fields.Integer('Амжилтгүй багц', compute='_compute_status')

    def _compute_status(self):
        self.env.cr.execute("SELECT COUNT(seq), COUNT(*) - COUNT(seq) FROM isms_audit_log")
        chained, unchained = self.env.cr.fetchone()
        file_state = _('тохируулсан') if get_setting(self.env, 'file_path') else _('тохируулаагүй')
        http_state = _('тохируулсан') if get_setting(self.env, 'http_url') else _('тохируулаагүй')
        queue = self.env['isms.audit.forward'].sudo()
        pending = queue.search_count([('state', '=', 'pending')])
        failed = queue.search_count([('state', '=', 'failed')])
        for rec in self:
            rec.chained_count = chained or 0
            rec.unchained_count = unchained or 0
            rec.file_target_state = file_state
            rec.http_target_state = http_state
            rec.queue_pending = pending
            rec.queue_failed = failed

    @api.model
    def _lock_head(self):
        """Толгойн мөрийг түгжиж, шинэчилсэн утгыг буцаана. Мөр байхгүй бол үүсгэнэ.

        Энэ нь аудит бичлэгийн seq олгох цорын ганц газар. Гүйлгээ дуустал түгжээ хадгалагдана.
        """
        cr = self.env.cr
        cr.execute("SELECT id FROM isms_audit_chain_head ORDER BY id LIMIT 1 FOR UPDATE")
        row = cr.fetchone()
        if not row:
            self.create({})
            cr.execute("SELECT id FROM isms_audit_chain_head ORDER BY id LIMIT 1 FOR UPDATE")
            row = cr.fetchone()
        head = self.browse(row[0])
        head.invalidate_recordset()
        return head

    def forward_seq(self, target):
        self.ensure_one()
        return self.forward_file_seq if target == 'file' else self.forward_http_seq

    def _check_chain_access(self):
        user = self.env.user
        if not (user.has_group(GROUP_AUDITOR) or user.has_group(GROUP_MANAGER)):
            raise AccessError(_('Аудит гинжийг шалгах эрх зөвхөн дотоод аудитор эсвэл CISO-д байна.'))

    @api.model
    def action_verify_chain(self):
        """Гинжийг бүрэн шалгаад үр дүнг толгойд хадгална (зөвхөн аудитор / CISO)."""
        self._check_chain_access()
        result = self.env['isms.audit.log'].sudo()._verify_chain()
        head = self.sudo().search([], order='id', limit=1) or self.sudo()._lock_head()
        head.write({
            'last_verified_at': fields.Datetime.now(),
            'last_verified_ok': result['ok'],
            'last_verified_checked': result['checked'],
            'last_verified_seq': result['broken_seq'] or 0,
            'last_verified_reason': (result['reason'] or _('Бүрэн')) if not result['ok'] else _('Бүрэн'),
        })
        if result['ok']:
            message = _('Аудит гинж бүрэн: %s бичлэг шалгалаа. Сүүлийн хэш: %s') % (
                result['checked'], result['last_hash'])
            kind = 'success'
        else:
            message = _('Аудит гинж эвдэрсэн: seq %s. Шалтгаан: %s') % (
                result['broken_seq'], result['reason'])
            kind = 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Аудит гинжийн шалгалт'), 'message': message,
                       'type': kind, 'sticky': True},
        }
