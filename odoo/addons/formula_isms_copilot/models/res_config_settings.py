"""Админ тохиргоо (Settings > ISMS туслах). Нууцийг шууд хадгалахгүй, зөвхөн нууцийн лавлагааг."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

PREFIX = 'formula_isms_copilot.'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    formula_isms_copilot_external_enabled = fields.Boolean(
        'Гадаад LLM провайдер ашиглах (анхдагчаар унтраалттай)')
    formula_isms_copilot_endpoint_url = fields.Char(
        'Провайдерын endpoint URL (https)')
    formula_isms_copilot_model_name = fields.Char('Загварын нэр')
    formula_isms_copilot_secret_ref = fields.Char(
        'Нууцийн лавлагаа',
        help='Орчны хувьсагчийн нэр (ж: ISMS_COPILOT_KEY) эсвэл ir.config_parameter-ийн түлхүүр. '
             'Нууцийн утга энд хадгалагдахгүй.')
    formula_isms_copilot_data_policy_ack = fields.Boolean(
        'Өгөгдлийн бодлого: зөвхөн зөвшөөрөгдсөн, маскласан эх сурвалжийг гадаад провайдерт илгээхийг зөвшөөрч байна')
    formula_isms_copilot_timeout_seconds = fields.Integer('Хүлээх хугацаа (сек, 1–30)', default=10)
    formula_isms_copilot_log_retention_days = fields.Integer('Асуултын логыг хадгалах хугацаа (өдөр)', default=365)

    @api.model
    def get_values(self):
        res = super().get_values()
        icp = self.env['ir.config_parameter'].sudo()
        res.update(
            formula_isms_copilot_external_enabled=icp.get_param(PREFIX + 'external_enabled', 'False') == 'True',
            formula_isms_copilot_endpoint_url=icp.get_param(PREFIX + 'endpoint_url', '') or '',
            formula_isms_copilot_model_name=icp.get_param(PREFIX + 'model_name', '') or '',
            formula_isms_copilot_secret_ref=icp.get_param(PREFIX + 'secret_ref', '') or '',
            formula_isms_copilot_data_policy_ack=icp.get_param(PREFIX + 'data_policy_ack', 'False') == 'True',
            formula_isms_copilot_timeout_seconds=int(icp.get_param(PREFIX + 'timeout_seconds', '10') or 10),
            formula_isms_copilot_log_retention_days=int(
                icp.get_param(PREFIX + 'log_retention_days', '365') or 365),
        )
        return res

    def set_values(self):
        for rec in self:
            if rec.formula_isms_copilot_external_enabled:
                if not rec.formula_isms_copilot_data_policy_ack:
                    raise UserError(_('Гадаад провайдерыг идэвхжүүлэхийн өмнө өгөгдлийн бодлогыг зөвшөөрнө үү.'))
                url = (rec.formula_isms_copilot_endpoint_url or '').strip()
                if not url.lower().startswith('https://'):
                    raise UserError(_('Endpoint URL нь https:// гэж эхлэх ёстой.'))
                if not (rec.formula_isms_copilot_model_name or '').strip():
                    raise UserError(_('Загварын нэрийг оруулна уу.'))
            if rec.formula_isms_copilot_timeout_seconds and not 1 <= rec.formula_isms_copilot_timeout_seconds <= 30:
                raise UserError(_('Хүлээх хугацаа 1-30 секундын хооронд байх ёстой.'))
            if not 1 <= (rec.formula_isms_copilot_log_retention_days or 0) <= 3650:
                raise UserError(_('Логын хадгалах хугацаа 1-3650 өдрийн хооронд байх ёстой.'))
            if rec.formula_isms_copilot_secret_ref and ' ' in rec.formula_isms_copilot_secret_ref.strip():
                raise UserError(_('Нууцийн лавлагаа хоосон зайгүй байх ёстой.'))
        super().set_values()
        icp = self.env['ir.config_parameter'].sudo()
        for rec in self:
            icp.set_param(PREFIX + 'external_enabled', str(bool(rec.formula_isms_copilot_external_enabled)))
            icp.set_param(PREFIX + 'endpoint_url', (rec.formula_isms_copilot_endpoint_url or '').strip())
            icp.set_param(PREFIX + 'model_name', (rec.formula_isms_copilot_model_name or '').strip())
            icp.set_param(PREFIX + 'secret_ref', (rec.formula_isms_copilot_secret_ref or '').strip())
            icp.set_param(PREFIX + 'data_policy_ack', str(bool(rec.formula_isms_copilot_data_policy_ack)))
            icp.set_param(PREFIX + 'timeout_seconds', str(rec.formula_isms_copilot_timeout_seconds or 10))
            icp.set_param(PREFIX + 'log_retention_days', str(rec.formula_isms_copilot_log_retention_days or 365))
