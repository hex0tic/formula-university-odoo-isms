"""ISMS-07: эрсдлийн дахин үнэлгээний өдөөгч (re-evaluation trigger).

Эрсдлийг дараах үед дахин үнэлэх шаардлагатайд тооцно:
- холбогдох эрсдлийн зөвшөөрөл (waiver) хугацаа дуусах;
- эрсдэлтэй холбогдсон өндөр/ноцтой олдвор илэрсэн.
Флаг нь системийн үйлдлээр тавигдаж, шинжээч «Дахин үнэлсэн» товчоор цэвэрлэнэ.
"""
from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from .common import GROUP_ANALYST, require_group

REEVAL_FIELDS = {'reeval_required', 'reeval_reason', 'reeval_flagged_at', 'reeval_completed_at'}


class IsmsRiskReeval(models.Model):
    _inherit = 'isms.risk'

    reeval_required = fields.Boolean('Дахин үнэлгээ шаардлагатай', default=False, copy=False,
                                     tracking=True, index=True)
    reeval_reason = fields.Char('Дахин үнэлгээний шалтгаан', copy=False)
    reeval_flagged_at = fields.Datetime('Тэмдэглэсэн огноо', readonly=True, copy=False)
    reeval_completed_at = fields.Datetime('Дахин үнэлсэн огноо', readonly=True, copy=False)

    def write(self, vals):
        if not self._isms_is_internal() and REEVAL_FIELDS & set(vals):
            raise AccessError(_('Дахин үнэлгээний тэмдэглэлийг зөвхөн системийн үйлдлээр өөрчилнө.'))
        return super().write(vals)

    def _flag_reeval(self, reason):
        """Эрсдлийг дахин үнэлгээнд тэмдэглэнэ. Аль хэдийн тэмдэглэгдсэн бол шалтгааныг хэвээр үлдээнэ."""
        now = fields.Datetime.now()
        for rec in self.filtered(lambda r: not r.reeval_required):
            rec._isms_internal().write({
                'reeval_required': True, 'reeval_reason': (reason or '')[:250], 'reeval_flagged_at': now,
            })

    def action_complete_reeval(self):
        """Шинжээч дахин үнэлгээ хийснийг бүртгэж флагийг цэвэрлэнэ."""
        self.ensure_one()
        require_group(self.env, GROUP_ANALYST, _('МАБ шинжээч'))
        if not self.reeval_required:
            raise UserError(_('%s: дахин үнэлгээ шаардлагагүй байна.') % self.code)
        self.sudo()._isms_internal().write({
            'reeval_required': False, 'reeval_reason': False, 'reeval_completed_at': fields.Datetime.now(),
        })
        self.sudo().message_post(body=_('Эрсдлийг дахин үнэлсэн (ISO/IEC 27001 6.1.2).'))
        return True
