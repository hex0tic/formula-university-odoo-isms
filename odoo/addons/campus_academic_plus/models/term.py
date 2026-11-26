from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CampusAcademicTerm(models.Model):
    _name = "campus.academic.term"
    _description = "Академик улирал"
    _order = "date_start desc, id desc"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True, help="Жишээ нь: 2026-A")
    date_start = fields.Date(string="Улирал эхлэх", required=True)
    date_end = fields.Date(string="Улирал дуусах", required=True)
    registration_start = fields.Date(string="Бүртгэл эхлэх", required=True)
    registration_end = fields.Date(string="Бүртгэл дуусах", required=True)
    add_drop_end = fields.Date(string="Нэмэх/хасах дуусах", required=True)
    state = fields.Selection(
        [("draft", "Бэлтгэл"), ("open", "Нээлттэй"), ("closed", "Хаасан")],
        default="draft", required=True,
    )
    offering_ids = fields.One2many("campus.offering", "term_id", string="Хичээлүүд")

    _sql_constraints = [("code_unique", "unique(code)", "Улирлын код давхардахгүй.")]

    @api.constrains("date_start", "date_end", "registration_start", "registration_end", "add_drop_end")
    def _check_dates(self):
        for rec in self:
            if rec.date_start > rec.date_end:
                raise ValidationError(_("Улирлын эхлэх огноо дуусах огнооноос хойш байж болохгүй."))
            if rec.registration_start > rec.registration_end:
                raise ValidationError(_("Бүртгэлийн эхлэх огноо дуусах огнооноос хойш байж болохгүй."))
            if rec.registration_end > rec.add_drop_end:
                raise ValidationError(_("Бүртгэл нэмэх/хасахаас хойш дуусч болохгүй."))
