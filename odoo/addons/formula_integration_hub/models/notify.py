"""INT-03 мэдэгдэл: хэрэглэгчийн тохиргоо, mail template, Odoo mail queue, event log.

* Имэйл: mail.mail state='outgoing' (Odoo mail queue). SMTP энд тохируулаагүй; тест зөвхөн «queued» төлөвийг баталгаажуулна.
* Inbox: mail.message + mail.notification (notification_type='inbox') — Odoo Discuss-ийн inbox.
* Аюулгүй байдлын (security) мэдэгдэл заавал: хэрэглэгч сувгийг унтраах боломжгүй.
* Академик/системийн мэдэгдлийг хэрэглэгч унтраана.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

CATEGORY_SELECTION = [
    ('academic', 'Академик'),
    ('security', 'Аюулгүй байдал'),
    ('system', 'Систем'),
]
MANDATORY_CATEGORIES = ('security',)


class FormulaNotificationPreference(models.Model):
    _name = 'formula.notification.preference'
    _description = 'Хэрэглэгчийн мэдэгдлийн тохиргоо'
    _order = 'user_id, category'

    user_id = fields.Many2one('res.users', 'Хэрэглэгч', required=True, ondelete='cascade', index=True,
                              default=lambda self: self.env.user)
    category = fields.Selection(CATEGORY_SELECTION, 'Ангилал', required=True)
    email = fields.Boolean('Имэйлээр', default=True)
    inbox = fields.Boolean('Inbox-д', default=True)

    _sql_constraints = [
        ('user_category_uniq', 'unique(user_id, category)', 'Нэг хэрэглэгч нэг ангилалд нэг тохиргоотой.'),
    ]

    @api.constrains('category', 'email', 'inbox')
    def _check_mandatory(self):
        for rec in self:
            if rec.category in MANDATORY_CATEGORIES and not (rec.email and rec.inbox):
                raise ValidationError(_('Аюулгүй байдлын мэдэгдлийн сувгийг унтраах боломжгүй (заавал).'))

    @api.model
    def channels_for(self, user, category):
        """(email, inbox) bool. Мөр байхгүй бол идэвхтэй. Заавал ангилал үргэлж идэвхтэй."""
        if category in MANDATORY_CATEGORIES:
            return True, True
        pref = self.sudo().search([('user_id', '=', user.id), ('category', '=', category)], limit=1)
        if not pref:
            return True, True
        return bool(pref.email), bool(pref.inbox)


class FormulaNotificationLog(models.Model):
    _name = 'formula.notification.log'
    _description = 'Мэдэгдлийн event log'
    _order = 'id desc'

    user_id = fields.Many2one('res.users', 'Хүлээн авагч', readonly=True, index=True)
    category = fields.Selection(CATEGORY_SELECTION, 'Ангилал', readonly=True)
    channel = fields.Selection([('email', 'Имэйл'), ('inbox', 'Inbox')], 'Суваг', readonly=True)
    template_ref = fields.Char('Template', readonly=True)
    res_model = fields.Char('Объект', readonly=True)
    res_id = fields.Integer('Объектын ID', readonly=True)
    state = fields.Selection([
        ('queued', 'Дарааллад орсон'),
        ('skipped_pref', 'Хэрэглэгч унтраасан'),
        ('skipped_no_email', 'Имэйл хаяг байхгүй'),
        ('failed', 'Алдаа'),
    ], 'Төлөв', readonly=True, index=True)
    mail_id = fields.Many2one('mail.mail', 'Mail', readonly=True, ondelete='set null')
    message_id = fields.Many2one('mail.message', 'Inbox мессеж', readonly=True, ondelete='set null')
    note = fields.Char('Тэмдэглэл', readonly=True)

    @api.model
    def notify(self, user, category, template_xmlid, record):
        """Хэрэглэгчид мэдэгдэл дараалалд оруулна. Бүх сувгийн үр дүнг log-д бичнэ."""
        user = user.sudo()
        partner = user.partner_id
        template = self.env.ref(template_xmlid).sudo()
        subject = template._render_field('subject', [record.id])[record.id]
        body = template._render_field('body_html', [record.id])[record.id]
        email_on, inbox_on = self.env['formula.notification.preference'].channels_for(user, category)
        Log = self.sudo()
        common = {'user_id': user.id, 'category': category, 'template_ref': template_xmlid,
                  'res_model': record._name, 'res_id': record.id}
        logs = Log.browse()

        # Имэйл → Odoo mail queue
        if not email_on:
            logs |= Log.create(dict(common, channel='email', state='skipped_pref'))
        elif not partner.email:
            logs |= Log.create(dict(common, channel='email', state='skipped_no_email'))
        else:
            try:
                with self.env.cr.savepoint():
                    mail = self.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'body_html': body,
                        'email_to': partner.email,
                        'auto_delete': False,
                        'state': 'outgoing',
                        'model': record._name,
                        'res_id': record.id,
                    })
                logs |= Log.create(dict(common, channel='email', state='queued', mail_id=mail.id))
            except Exception as exc:
                _logger.exception('Notification email queue failed for user %s', user.id)
                logs |= Log.create(dict(common, channel='email', state='failed',
                                        note=str(exc)[:200]))

        # Inbox → Odoo mail.notification (inbox)
        if not inbox_on:
            logs |= Log.create(dict(common, channel='inbox', state='skipped_pref'))
        else:
            try:
                with self.env.cr.savepoint():
                    # Thread-гүй мессеж: Odoo reply-to тооцоолол record-ийн thread-д холбогдохгүй.
                    # Объектын холбоос event log (res_model/res_id)-д байна.
                    message = self.env['mail.message'].sudo().create({
                        'model': False,
                        'res_id': False,
                        'message_type': 'user_notification',
                        'subtype_id': self.env.ref('mail.mt_note').id,
                        'subject': subject,
                        'body': body,
                        'author_id': False,
                    })
                    self.env['mail.notification'].sudo().create({
                        'mail_message_id': message.id,
                        'res_partner_id': partner.id,
                        'notification_type': 'inbox',
                        'is_read': False,
                    })
                logs |= Log.create(dict(common, channel='inbox', state='queued', message_id=message.id))
            except Exception as exc:
                _logger.exception('Notification inbox failed for user %s', user.id)
                logs |= Log.create(dict(common, channel='inbox', state='failed', note=str(exc)[:200]))
        return logs


class CampusGradeChangeNotify(models.Model):
    _inherit = 'campus.grade.change'

    def write(self, vals):
        before = {rec.id: rec.state for rec in self} if 'state' in vals else {}
        res = super().write(vals)
        for rec in self:
            if rec.id in before and before[rec.id] != rec.state and rec.state in ('approved', 'rejected'):
                try:
                    with self.env.cr.savepoint():
                        self.env['formula.notification.log'].notify(
                            rec.requester_id, 'academic',
                            'formula_integration_hub.mail_tpl_grade_decided', rec)
                except Exception:
                    _logger.exception('Grade decision notification failed for %s', rec.id)
        return res


class IsmsIncidentNotify(models.Model):
    _inherit = 'isms.incident'

    def write(self, vals):
        before = {rec.id: rec.assignee_id.id for rec in self} if 'assignee_id' in vals else {}
        res = super().write(vals)
        for rec in self:
            if rec.id in before and rec.assignee_id and rec.assignee_id.id != before[rec.id]:
                try:
                    with self.env.cr.savepoint():
                        self.env['formula.notification.log'].notify(
                            rec.assignee_id, 'security',
                            'formula_integration_hub.mail_tpl_incident_assigned', rec)
                except Exception:
                    _logger.exception('Incident assignment notification failed for %s', rec.id)
        return res
