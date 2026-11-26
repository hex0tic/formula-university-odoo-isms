from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

DEFAULT_NOTE = (
    "Энэ утгууд нь тохируулж болох таамаглал (defaults) бөгөөд албан ёсны "
    "их сургуулийн журам биш. Сургалтын алба баталсан журмаар солино уу."
)


class CampusAcademicPolicy(models.Model):
    _name = "campus.academic.policy"
    _description = "Академик бодлого"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True, help="Зөвхөн нэг идэвхтэй бодлого байна.")
    note = fields.Text(default=DEFAULT_NOTE)
    pass_score = fields.Float(string="Тэнцэх дүн", default=60.0, required=True, digits=(5, 2))
    max_credits_per_term = fields.Integer(string="Улирлын дээд кредит", default=21, required=True)
    min_graduation_gpa = fields.Float(
        string="Төгсөх хамгийн бага GPA", default=0.0, required=True, digits=(3, 2),
        help="0 гэвэл GPA шаардлагагүй гэж тооцно (тохируулж болох таамаглал).",
    )
    scale_ids = fields.One2many("campus.grade.scale.line", "policy_id", string="Үнэлгээний шатлал", copy=True)

    @api.model
    def _get_active_policy(self, required=True):
        """Return the active policy as superuser (read-only helper), or an empty recordset."""
        policy = self.sudo().search([("active", "=", True)], limit=1)
        if not policy and required:
            raise UserError(_("Академик бодлого тохируулаагүй байна. Сургалтын албанд хандана уу."))
        return policy

    @api.constrains("active")
    def _check_single_active(self):
        if self.sudo().search_count([("active", "=", True)]) > 1:
            raise ValidationError(_("Идэвхтэй академик бодлого зөвхөн нэг байна."))

    @api.constrains("pass_score", "max_credits_per_term", "min_graduation_gpa", "scale_ids")
    def _check_values(self):
        for rec in self:
            if not 0 <= rec.pass_score <= 100:
                raise ValidationError(_("Тэнцэх дүн 0–100 хооронд байна."))
            if rec.max_credits_per_term <= 0:
                raise ValidationError(_("Улирлын дээд кредит 1-ээс их байна."))
            if not 0 <= rec.min_graduation_gpa <= 4:
                raise ValidationError(_("Төгсөх GPA 0–4 хооронд байна."))
            if rec.scale_ids and min(rec.scale_ids.mapped("min_score")) > 0:
                raise ValidationError(_("Үнэлгээний шатлалд 0 оноотой доод шатлал байх ёстой."))

    def _grade_for_score(self, score):
        """Return the scale line whose minimum score the given score reaches (highest first)."""
        self.ensure_one()
        for line in self.scale_ids.sorted(key=lambda l: l.min_score, reverse=True):
            if score >= line.min_score:
                return line
        return self.env["campus.grade.scale.line"]


class CampusGradeScaleLine(models.Model):
    _name = "campus.grade.scale.line"
    _description = "Үнэлгээний шатлал"
    _order = "min_score desc"

    policy_id = fields.Many2one("campus.academic.policy", required=True, ondelete="cascade")
    min_score = fields.Float(string="Доод оноо", required=True, digits=(5, 2))
    letter = fields.Char(string="Үсгэн дүн", required=True)
    grade_point = fields.Float(string="Дүнгийн оноо", required=True, digits=(3, 2))

    _sql_constraints = [
        ("min_score_range", "check(min_score between 0 and 100)", "Доод оноо 0–100 байна."),
        ("min_score_unique", "unique(policy_id, min_score)", "Нэг шатлалын доод оноо давхардахгүй."),
        ("grade_point_range", "check(grade_point between 0 and 4)", "Дүнгийн оноо 0–4 байна."),
    ]
