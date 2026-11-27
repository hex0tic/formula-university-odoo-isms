import logging

from odoo import Command, SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref("campus_university.group_campus_student")
    catalog = env.ref("campus_university.group_campus_user")
    students = group.with_context(active_test=False).users
    staff = (
        env.ref("campus_university.group_campus_lecturer")
        | env.ref("campus_university.group_campus_registrar")
        | env.ref("campus_university.group_campus_auditor")
        | env.ref("base.group_system")
    )
    overlap = students.filtered(lambda user: bool(staff & user.groups_id))
    if overlap:
        raise RuntimeError(
            "Separate student/employee accounts before migrating Campus. Conflicting user IDs: "
            + ", ".join(map(str, overlap.ids))
        )

    reporter = env.ref("university_isms.group_isms_reporter", raise_if_not_found=False)
    if reporter and reporter in catalog.implied_ids:
        # Odoo materializes inherited membership. _remove_group drops those old
        # grants, retaining other users' independent ISMS role inheritance.
        catalog._remove_group(reporter)
    catalog.write({"implied_ids": [Command.unlink(env.ref("base.group_user").id)]})
    portal = env.ref("base.group_portal")
    for student in students:
        # Dedicated student accounts intentionally lose employee/app grants.
        student.write({
            "groups_id": [Command.set((group | portal).ids)],
            "notification_type": "email",
            "action_id": False,
        })
    _logger.info("Converted %d Campus Student accounts to Portal", len(students))
