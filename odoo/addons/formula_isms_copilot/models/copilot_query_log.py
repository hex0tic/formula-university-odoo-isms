"""Туслахын асуултын аудит лог (AI-05).

* Асуулт бүрт хэрэглэгч, цаг, асуултын hash, маскласан богино хэсэг, хөдөлгүүр, буцаасан бичлэгийн тоо,
  татгалзсан эсэхийг хадгална.
* Хариултын текстийг хэзээ ч хадгалахгүй.
* Уншихыг зөвхөн ISMS аудитор ба CISO (group_isms_auditor / group_isms_manager) хийнэ.
* Бичилтийг сервис дотроос sudo()-оор хийнэ (системийн журналын бичилт); хэрэглэгч шууд бичих эрхгүй.
"""
from datetime import timedelta

from odoo import api, fields, models

RETENTION_KEY = 'formula_isms_copilot.log_retention_days'
DEFAULT_RETENTION_DAYS = 365


class FormulaCopilotQueryLog(models.Model):
    _name = 'formula.copilot.query.log'
    _description = 'ISMS туслахын асуултын лог'
    _order = 'queried_at desc, id desc'
    _rec_name = 'question_excerpt'

    queried_at = fields.Datetime('Огноо, цаг', required=True, default=fields.Datetime.now,
                                 readonly=True, index=True)
    user_id = fields.Many2one('res.users', 'Хэрэглэгч', readonly=True, index=True, ondelete='set null')
    login = fields.Char('Нэвтрэх нэр', readonly=True)
    action_type = fields.Selection([
        ('query', 'Асуулт'),
        ('suggest', 'Санал'),
    ], 'Төрөл', readonly=True, required=True, default='query')
    question_hash = fields.Char('Асуултын hash (SHA-256)', readonly=True, index=True)
    question_excerpt = fields.Char('Асуултын товч (маскласан)', readonly=True)
    scope_keys = fields.Char('Хамрах хүрээ', readonly=True)
    engine = fields.Selection([
        ('local', 'Дотоод хөдөлгүүр'),
        ('external', 'Гадаад провайдер'),
        ('refused', 'Татгалзсан'),
        ('suggestion', 'Санал'),
        ('none', 'Хоосон хариулт'),
    ], 'Хөдөлгүүр', readonly=True)
    record_count = fields.Integer('Буцаасан бичлэг', readonly=True)
    refused = fields.Boolean('Татгалзсан', readonly=True, index=True)
    fallback_reason = fields.Char('Нөөц горимын шалтгаан', readonly=True)

    @api.model
    def _cron_purge_old_logs(self):
        """Тохируулсан хугацаанаас хуучин бичлэгийг устгана (ир.cron)."""
        days = self.env['formula.isms.copilot']._retention_days()
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.sudo().search([('queried_at', '<', cutoff)])
        count = len(old)
        old.unlink()
        return count
