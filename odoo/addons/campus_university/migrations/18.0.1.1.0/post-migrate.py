from odoo import SUPERUSER_ID, api

from odoo.addons.campus_university.staff_chat import configure_staff_chat


def migrate(cr, version):
    configure_staff_chat(api.Environment(cr, SUPERUSER_ID, {}))
