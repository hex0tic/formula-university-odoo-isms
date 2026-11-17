from odoo import fields, models


class CampusStudentAudit(models.Model):
    _name = "campus.student"
    _inherit = ["campus.student", "isms.audit.mixin"]


class CampusEnrollmentAudit(models.Model):
    _name = "campus.enrollment"
    _inherit = ["campus.enrollment", "isms.audit.mixin"]


class CampusGradeChangeAudit(models.Model):
    _name = "campus.grade.change"
    _inherit = ["campus.grade.change", "isms.audit.mixin"]

    isms_asset_id = fields.Many2one(
        "isms.asset", string="Холбогдох мэдээллийн хөрөнгө", ondelete="restrict",
        groups="university_isms.group_isms_analyst,university_isms.group_isms_auditor",
    )
    isms_incident_id = fields.Many2one(
        "isms.incident", string="Холбогдох зөрчлийн бүртгэл", ondelete="restrict",
        groups="university_isms.group_isms_analyst,university_isms.group_isms_auditor",
    )
