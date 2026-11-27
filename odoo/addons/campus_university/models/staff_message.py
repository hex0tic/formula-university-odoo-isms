from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


class MailMessage(models.Model):
    _inherit = "mail.message"

    campus_staff_chat_message = fields.Boolean(
        compute="_compute_campus_staff_chat_message",
        search="_search_campus_staff_chat_message",
    )

    @api.model
    def _campus_staff_channel_ids(self):
        root = self.env.ref("mail.channel_all_employees", raise_if_not_found=False)
        if not root:
            return []
        # The standard Discuss subthread inherits the root channel's group.
        children = self.env["discuss.channel"].sudo().search([("parent_channel_id", "=", root.id)])
        return root.ids + children.ids

    @api.depends("model", "res_id")
    def _compute_campus_staff_chat_message(self):
        ids = set(self._campus_staff_channel_ids())
        for message in self:
            message.campus_staff_chat_message = message.model == "discuss.channel" and message.res_id in ids

    @api.model
    def _search_campus_staff_chat_message(self, operator, value):
        if operator in ("=", "!="):
            allowed = {bool(value)} if operator == "=" else {not bool(value)}
        elif operator in ("in", "not in"):
            allowed = {bool(item) for item in value}
            if operator == "not in":
                allowed = {False, True} - allowed
        else:
            raise UserError(_("Энэ талбарт тохирох хайлтын нөхцөл сонгоно уу."))
        if allowed == {True, False}:
            return []
        if not allowed:
            return expression.FALSE_DOMAIN
        ids = self._campus_staff_channel_ids()
        is_staff_message = True in allowed
        if is_staff_message:
            return expression.AND([[("model", "=", "discuss.channel")], [("res_id", "in", ids)]])
        return expression.OR([[("model", "!=", "discuss.channel")], [("res_id", "not in", ids)]])

    def _message_notifications_to_store(self, store):
        staff = self.env.ref("campus_university.group_campus_staff_chat", raise_if_not_found=False)
        if staff and staff not in self.env.user.groups_id:
            self = self.filtered(lambda message: not message.campus_staff_chat_message)
        return super(MailMessage, self)._message_notifications_to_store(store)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _is_campus_staff_channel(self):
        self.ensure_one()
        root = self.env.ref("mail.channel_all_employees", raise_if_not_found=False)
        return bool(root and (self == root or self.sudo().parent_channel_id == root))

    @api.model
    def _campus_staff_partners(self):
        group = self.env.ref("campus_university.group_campus_staff_chat", raise_if_not_found=False)
        return group.sudo().users.partner_id if group else self.env["res.partner"]

    def write(self, vals):
        if "group_public_id" in vals:
            root = self.env.ref("mail.channel_all_employees", raise_if_not_found=False)
            staff = self.env.ref("campus_university.group_campus_staff_chat", raise_if_not_found=False)
            if root and root in self and staff and vals["group_public_id"] != staff.id:
                raise UserError(_("Ажилтны сувгийн хандалтыг «Ажилтны хэлэлцүүлэг» бүлгээр удирдана."))
        return super().write(vals)

    def message_post(self, *, partner_ids=None, **kwargs):
        if partner_ids and self._is_campus_staff_channel():
            allowed = set(self._campus_staff_partners().ids)
            partner_ids = [partner_id for partner_id in partner_ids if partner_id in allowed]
        return super().message_post(partner_ids=partner_ids, **kwargs)

    def _notify_get_recipients(self, message, msg_vals, **kwargs):
        recipients = super()._notify_get_recipients(message, msg_vals, **kwargs)
        if self._is_campus_staff_channel():
            allowed = set(self._campus_staff_partners().ids)
            recipients = [recipient for recipient in recipients if recipient["id"] in allowed]
        return recipients


class DiscussChannelMember(models.Model):
    _inherit = "discuss.channel.member"

    @api.constrains("channel_id", "partner_id", "guest_id")
    def _check_campus_staff_member(self):
        for member in self.sudo():
            if member.channel_id._is_campus_staff_channel():
                if not member.partner_id or member.partner_id not in member.channel_id._campus_staff_partners():
                    raise UserError(_("Ажилтны сувагт зөвхөн тусдаа эрх авсан ажилтан нэгдэнэ."))
