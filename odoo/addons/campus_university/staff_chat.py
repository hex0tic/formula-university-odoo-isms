from odoo import Command


def configure_staff_chat(env):
    """One-time conversion; later access is granted through the dedicated group."""
    channel = env.ref("mail.channel_all_employees")
    staff_chat = env.ref("campus_university.group_campus_staff_chat")
    students = env.ref("campus_university.group_campus_student")
    lecturers = env.ref("campus_university.group_campus_lecturer")
    internal = env.ref("base.group_user")
    User = env["res.users"].with_context(active_test=False)
    # Preserve the existing employees' channel access. Lecturers can receive it
    # separately after review, including those also teaching in another role.
    existing = User.search([
        ("partner_id", "in", channel.channel_partner_ids.ids),
        ("groups_id", "in", internal.ids),
        ("groups_id", "not in", (students | lecturers).ids),
    ])
    admin = env.ref("base.user_admin", raise_if_not_found=False)
    if admin and internal in admin.groups_id:
        existing |= admin
    if existing:
        staff_chat.write({"users": [Command.link(user.id) for user in existing]})
    channel.write({
        "group_public_id": staff_chat.id,
        "group_ids": [Command.set(staff_chat.ids)],
    })
    allowed_partners = staff_chat.with_context(active_test=False).users.partner_id
    channels = channel | env["discuss.channel"].search([("parent_channel_id", "=", channel.id)])
    channels.channel_member_ids.filtered(lambda member: member.partner_id not in allowed_partners).unlink()


def post_init_hook(env):
    configure_staff_chat(env)
