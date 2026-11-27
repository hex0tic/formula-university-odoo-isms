from odoo import fields, models


class FormulaPublicProgram(models.Model):
    _name = "formula.public.program"
    _description = "University website programme"
    _order = "sequence, id"

    name = fields.Char(required=True)
    slug = fields.Char(required=True, index=True)
    area = fields.Selection(
        [("technology", "Технологи"), ("business", "Бизнес"), ("design", "Дизайн")],
        required=True,
    )
    school = fields.Char(required=True)
    summary = fields.Text(required=True)
    curriculum = fields.Text(required=True)
    outcome = fields.Text(required=True)
    degree = fields.Char(default="Бакалавр", required=True)
    duration = fields.Char(default="4 жил", required=True)
    sequence = fields.Integer(default=10)
    published = fields.Boolean(default=False, index=True)

    _sql_constraints = [
        ("unique_slug", "unique(slug)", "Хөтөлбөрийн холбоос давхцахгүй."),
        ("safe_slug", "CHECK(slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$')", "Холбоосод латин жижиг үсэг, тоо, зураас хэрэглэнэ."),
    ]


class FormulaCampusInquiry(models.Model):
    _name = "formula.campus.inquiry"
    _description = "University admissions inquiry"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True)
    email = fields.Char(required=True)
    program_id = fields.Many2one("formula.public.program", ondelete="set null")
    message = fields.Text(required=True)
    state = fields.Selection([("new", "Шинэ"), ("reviewed", "Хянасан"), ("closed", "Хаасан")],
                             default="new", required=True, index=True)
