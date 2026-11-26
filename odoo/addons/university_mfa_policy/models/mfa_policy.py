"""Step-up MFA policy (SEC-01, ISO/IEC 27001:2022 A.8.5).

Нэвтрэлтийг хаадаггүй: давуу эрхтэй хэрэглэгч TOTP идэвхжүүлээгүй ч нэвтэрч, TOTP-оо
идэвхжүүлж чадна. Хүчинтэй огнооноос хойш зөвхөн өндөр нөлөөтэй үйлдлүүдийг хориглоно.
Cron ба системийн (su) дуудлагад хамаарахгүй.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

PARAM_DATE = 'university_mfa_policy.enforce_date'
PRIVILEGED = [
    'base.group_system',
    'base.group_erp_manager',
    'university_isms.group_isms_manager',
    'campus_university.group_campus_registrar',
]


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _mfa_privileged(self):
        self.ensure_one()
        return any(self.env.ref(x, raise_if_not_found=False) and self.has_group(x) for x in PRIVILEGED)

    @api.model
    def _mfa_enforce_date(self):
        value = (self.env['ir.config_parameter'].sudo().get_param(PARAM_DATE) or '').strip()
        try:
            return fields.Date.to_date(value) if value else False
        except ValueError:
            return False

    @api.model
    def _mfa_enforced(self):
        date = self._mfa_enforce_date()
        return bool(date) and fields.Date.context_today(self) >= date

    @api.model
    def _mfa_step_up_check(self, action_label):
        """Raise if the acting privileged user lacks TOTP once enforcement is active."""
        if self.env.su or not self._mfa_enforced():
            return
        user = self.env.user
        if user._mfa_privileged() and not user.totp_enabled:
            raise AccessError(_(
                '«%s» үйлдэлд хоёр шатлалт баталгаажуулалт (TOTP) шаардлагатай (A.8.5). '
                'Хувийн тохиргоо, Account Security хэсгээс TOTP идэвхжүүлнэ үү.') % action_label)

    @api.model
    def get_mfa_status(self):
        """Current user's MFA posture for the web client notice. Contains no secrets."""
        user = self.env.user
        date = self._mfa_enforce_date()
        return {
            'privileged': user._mfa_privileged(),
            'totp_enabled': bool(user.totp_enabled),
            'enforce_date': fields.Date.to_string(date) if date else False,
            'enforced': self._mfa_enforced(),
        }

    def write(self, vals):
        if any(k == 'groups_id' or k.startswith(('in_group_', 'sel_groups_')) for k in vals):
            self._mfa_step_up_check(_('Хэрэглэгчийн эрх өөрчлөх'))
        return super().write(vals)


class IsmsPolicy(models.Model):
    _inherit = 'isms.policy'

    def action_approve(self):
        self.env['res.users']._mfa_step_up_check(_('Бодлого батлах'))
        return super().action_approve()


class IsmsIncident(models.Model):
    _inherit = 'isms.incident'

    def action_close(self):
        self.env['res.users']._mfa_step_up_check(_('Зөрчил хаах'))
        return super().action_close()

    def action_reopen(self):
        self.env['res.users']._mfa_step_up_check(_('Зөрчил дахин нээх'))
        return super().action_reopen()


class IsmsRisk(models.Model):
    _inherit = 'isms.risk'

    def action_accept_risk(self):
        self.env['res.users']._mfa_step_up_check(_('Эрсдэл хүлээн зөвшөөрөх'))
        return super().action_accept_risk()

    def action_accept_residual(self):
        self.env['res.users']._mfa_step_up_check(_('Үлдэгдэл эрсдэл батлах'))
        return super().action_accept_residual()


class CampusGradeChange(models.Model):
    _inherit = 'campus.grade.change'

    def action_approve(self):
        self.env['res.users']._mfa_step_up_check(_('Дүнгийн засвар батлах'))
        return super().action_approve()

    def action_reject(self):
        self.env['res.users']._mfa_step_up_check(_('Дүнгийн засвар татгалзах'))
        return super().action_reject()


class AccessReview(models.TransientModel):
    _inherit = 'access.review'

    def action_apply_groups(self):
        self.env['res.users']._mfa_step_up_check(_('Хэрэглэгчийн эрх өөрчлөх'))
        return super().action_apply_groups()
