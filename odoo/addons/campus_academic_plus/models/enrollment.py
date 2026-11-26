from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .common import is_registrar

ACADEMIC_VIEW_GROUPS = (
    "campus_university.group_campus_student,"
    "campus_university.group_campus_registrar,"
    "campus_university.group_campus_auditor"
)


class CampusEnrollmentAcademic(models.Model):
    _inherit = "campus.enrollment"

    reg_state = fields.Selection(
        [("enrolled", "Бүртгэгдсэн"), ("dropped", "Хасагдсан"), ("completed", "Дууссан")],
        string="Бүртгэлийн төлөв", default="enrolled", required=True, index=True,
    )
    registered_by_id = fields.Many2one("res.users", string="Бүртгэсэн", readonly=True, copy=False,
                                       ondelete="restrict")
    registered_at = fields.Datetime(string="Бүртгэсэн огноо", readonly=True, copy=False)
    dropped_by_id = fields.Many2one("res.users", string="Хассан", readonly=True, copy=False,
                                    ondelete="restrict")
    dropped_at = fields.Datetime(string="Хассан огноо", readonly=True, copy=False)
    credits = fields.Integer(related="offering_id.course_id.credits", string="Кредит")
    letter_grade = fields.Char(string="Үсгэн дүн", compute="_compute_grade", readonly=True)
    grade_point = fields.Float(string="Дүнгийн оноо", compute="_compute_grade", readonly=True,
                               digits=(3, 2))
    attendance_ids = fields.One2many("campus.attendance", "enrollment_id", string="Ирц")
    attendance_rate = fields.Float(string="Ирцийн хувь (%)", compute="_compute_attendance_rate",
                                   readonly=True, digits=(5, 2))

    @api.depends("score", "reg_state")
    def _compute_grade(self):
        policy = self.env["campus.academic.policy"]._get_active_policy(required=False)
        for rec in self:
            rec.letter_grade = False
            rec.grade_point = 0.0
            # Letter grade and grade point only exist for completed records, so an
            # in-progress score of 0 is never shown as an F.
            if policy and rec.reg_state == "completed":
                line = policy._grade_for_score(rec.score)
                if line:
                    rec.letter_grade = line.letter
                    rec.grade_point = line.grade_point

    @api.depends("attendance_ids.status")
    def _compute_attendance_rate(self):
        for rec in self:
            statuses = rec.sudo().attendance_ids.mapped("status")
            counted = [s for s in statuses if s != "excused"]
            attended = len([s for s in counted if s in ("present", "late")])
            rec.attendance_rate = round(100.0 * attended / len(counted), 2) if counted else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.offering_id._check_capacity_not_exceeded()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"reg_state", "offering_id"}.intersection(vals):
            self.offering_id._check_capacity_not_exceeded()
        return res

    def _check_actor_is_student_or_registrar(self):
        user = self.env.user
        if is_registrar(self.env):
            return
        if any(not rec.student_id.user_id or rec.student_id.user_id != user for rec in self):
            raise AccessError(_("Зөвхөн өөрийн бүртгэлээс хасна."))

    def action_drop(self):
        """Drop an enrollment within the term add/drop window. Records are never deleted."""
        self.check_access("read")
        self._check_actor_is_student_or_registrar()
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.reg_state != "enrolled":
                raise UserError(_("Зөвхөн идэвхтэй бүртгэлийг хасна."))
            term = rec.offering_id.sudo().term_id
            if not term:
                raise UserError(_("Хичээлд улирал оноогоогүй тул хасах боломжгүй."))
            if today > term.add_drop_end:
                raise UserError(_("Нэмэх/хасах хугацаа дууссан байна (%s).") % term.add_drop_end)
        self.sudo().write({
            "reg_state": "dropped",
            "dropped_by_id": self.env.uid,
            "dropped_at": fields.Datetime.now(),
        })
        return True

    def action_complete(self):
        """Registrar closes an enrollment as completed so its grade counts toward GPA and credits."""
        if not is_registrar(self.env):
            raise AccessError(_("Зөвхөн сургалтын алба хичээлийг дуусгана."))
        for rec in self:
            if rec.reg_state != "enrolled":
                raise ValidationError(_("Зөвхөн идэвхтэй бүртгэлийг дуусгана."))
        self.sudo().write({"reg_state": "completed"})
        return True


class CampusStudentAcademic(models.Model):
    _inherit = "campus.student"

    gpa = fields.Float(
        string="GPA", compute="_compute_academic", digits=(3, 2), groups=ACADEMIC_VIEW_GROUPS,
    )
    credits_earned = fields.Integer(
        string="Олгосон кредит", compute="_compute_academic", groups=ACADEMIC_VIEW_GROUPS,
    )
    graduation_eligible = fields.Boolean(
        string="Төгсөх шаардлага", compute="_compute_academic", groups=ACADEMIC_VIEW_GROUPS,
    )
    graduation_missing = fields.Text(
        string="Дутуу шаардлага", compute="_compute_academic", groups=ACADEMIC_VIEW_GROUPS,
    )

    @api.depends("enrollment_ids.reg_state", "enrollment_ids.score", "enrollment_ids.grade_point",
                 "enrollment_ids.credits", "program_id.required_credits")
    def _compute_academic(self):
        policy = self.env["campus.academic.policy"]._get_active_policy(required=False)
        for rec in self:
            sudo_rec = rec.sudo()
            completed = sudo_rec.enrollment_ids.filtered(lambda e: e.reg_state == "completed")
            total_credits = sum(completed.mapped("credits"))
            weighted = sum(e.grade_point * e.credits for e in completed)
            gpa = weighted / total_credits if total_credits else 0.0
            earned = 0
            if policy:
                earned = sum(e.credits for e in completed if e.score >= policy.pass_score)
            required = sudo_rec.program_id.required_credits

            missing = []
            if not policy:
                missing.append(_("Академик бодлого тохируулаагүй тул шалгах боломжгүй."))
            if required <= 0:
                missing.append(_("Хөтөлбөрийн төгсөх кредит тохируулаагүй."))
            elif earned < required:
                missing.append(_("Кредит дутуу: %s / %s (дутуу %s).") % (earned, required, required - earned))
            if policy and gpa < policy.min_graduation_gpa:
                missing.append(_("GPA хангалтгүй: %.2f / %.2f шаардлагатай.") % (gpa, policy.min_graduation_gpa))

            rec.gpa = round(gpa, 2)
            rec.credits_earned = earned
            rec.graduation_eligible = not missing
            rec.graduation_missing = "\n".join(missing) if missing else _("Төгсөх шаардлага хангасан.")

    def action_transcript(self):
        """Return the transcript report action. Students print only their own transcript."""
        self.ensure_one()
        user = self.env.user
        if not is_registrar(self.env) and (not self.user_id or self.user_id != user):
            raise AccessError(_("Зөвхөн өөрийн транскриптыг хэвлэнэ."))
        self.check_access("read")
        return self.env.ref("campus_academic_plus.action_report_transcript").report_action(self)
