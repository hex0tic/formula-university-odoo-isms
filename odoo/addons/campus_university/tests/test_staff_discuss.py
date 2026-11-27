from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestStaffDiscuss(TransactionCase):

    def test_historical_messages_require_current_staff_channel_group(self):
        channel = self.env.ref("mail.channel_all_employees")
        staff = self.env.ref("campus_university.group_campus_staff_chat")
        teacher = new_test_user(
            self.env, login="campus_chat_teacher", groups="campus_university.group_campus_lecturer",
        )
        employee = new_test_user(
            self.env, login="campus_chat_staff", groups="campus_university.group_campus_staff_chat",
        )
        self.assertEqual(channel.group_public_id, staff)
        self.assertFalse(channel.with_user(teacher).has_access("read"))
        with self.assertRaises(UserError), self.cr.savepoint():
            self.env["discuss.channel.member"].sudo().create({
                "channel_id": channel.id, "partner_id": teacher.partner_id.id,
            })

        teacher.write({"groups_id": [Command.link(staff.id)]})
        old_message = channel.with_user(teacher).message_post(body="Internal staff update",
                                                              subtype_xmlid="mail.mt_comment")
        self.assertTrue(old_message.with_user(employee).has_access("read"))
        self.assertTrue(old_message.with_user(teacher).has_access("read"))
        teacher.write({"groups_id": [Command.unlink(staff.id)]})
        self.assertFalse(channel.with_user(teacher).has_access("read"))
        self.assertFalse(old_message.with_user(teacher).has_access("read"))
        self.assertFalse(old_message.with_user(teacher).search_count([("id", "=", old_message.id)]))
        with self.assertRaises(AccessError):
            old_message.with_user(teacher).read(["body"])
