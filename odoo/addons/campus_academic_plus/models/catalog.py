from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .common import is_registrar


class CampusProgramAcademic(models.Model):
    _inherit = "campus.program"

    required_credits = fields.Integer(string="Төгсөх шаардлагатай кредит", default=0)

    _sql_constraints = [
        ("required_credits_nonnegative", "check(required_credits >= 0)", "Төгсөх кредит сөрөг байж болохгүй."),
    ]


class CampusCourseAcademic(models.Model):
    _inherit = "campus.course"

    prerequisite_ids = fields.Many2many(
        "campus.course", "campus_course_prereq_rel", "course_id", "prereq_id",
        string="Урьдчилсан нөхцөл",
    )

    @api.constrains("prerequisite_ids")
    def _check_prerequisites(self):
        for rec in self:
            if rec in rec.prerequisite_ids:
                raise ValidationError(_("Хичээл өөрийгөө урьдчилсан нөхцөл байж болохгүй."))


class CampusOfferingAcademic(models.Model):
    _inherit = "campus.offering"

    term_id = fields.Many2one("campus.academic.term", string="Улирал", ondelete="restrict", index=True)
    # Default keeps offerings created by existing campus flows valid after install; registrar adjusts per offering.
    capacity = fields.Integer(string="Багтаамж", default=30)
    seats_taken = fields.Integer(
        string="Эзлэгдсэн суудал", compute="_compute_seats_taken", store=True,
    )
    seats_left = fields.Integer(string="Үлдсэн суудал", compute="_compute_seats_left")
    session_ids = fields.One2many("campus.session", "offering_id", string="Цагийн хуваарь")

    @api.depends("enrollment_ids.reg_state")
    def _compute_seats_taken(self):
        Enrollment = self.env["campus.enrollment"].sudo()
        for rec in self:
            if not isinstance(rec.id, int):
                rec.seats_taken = 0
                continue
            rec.seats_taken = Enrollment.search_count(
                [("offering_id", "=", rec.id), ("reg_state", "=", "enrolled")]
            )

    @api.depends("capacity", "seats_taken")
    def _compute_seats_left(self):
        for rec in self:
            rec.seats_left = rec.capacity - rec.seats_taken

    @api.constrains("capacity", "state")
    def _check_capacity(self):
        for rec in self:
            if rec.capacity < 0:
                raise ValidationError(_("Багтаамж сөрөг байж болохгүй."))
            if rec.state == "open" and rec.capacity <= 0:
                raise ValidationError(_(
                    "Нээлттэй хичээлд багтаамжийг 1-ээс дээш тохируулна уу. 0 нь хязгааргүй гэж тооцогдохгүй."
                ))
        self._check_capacity_not_exceeded()

    def _check_capacity_not_exceeded(self):
        Enrollment = self.env["campus.enrollment"].sudo()
        for rec in self.filtered(lambda o: o.state == "open" and o.capacity > 0):
            taken = Enrollment.search_count([("offering_id", "=", rec.id), ("reg_state", "=", "enrolled")])
            if taken > rec.capacity:
                raise ValidationError(_("Суудлын багтаамж давсан байна (%s / %s).") % (taken, rec.capacity))

    def register_student(self, student):
        """Register a student for this offering after all server-side academic checks.

        A student may register only themself. A registrar may register anyone.
        Returns the active campus.enrollment record (in the caller's environment).
        """
        self.ensure_one()
        # Re-browse in the caller's environment so ACL and record rules apply to this call.
        student_id = student if isinstance(student, int) else student.id
        student = self.env["campus.student"].browse(student_id).exists()
        if not student:
            raise UserError(_("Оюутан сонгогдоогүй байна."))

        user = self.env.user
        registrar = is_registrar(self.env)
        if not registrar and (not student.user_id or student.user_id != user):
            raise AccessError(_("Зөвхөн өөрийн бүртгэлээр хичээлд бүртгүүлнэ."))
        self.check_access("read")
        student.check_access("read")
        if not student.active or student.status != "active":
            raise UserError(_("Идэвхтэй суралцагч биш тул хичээлд бүртгүүлэх боломжгүй."))

        # Serialize concurrent registrations for the same offering (seat counting).
        self.env.cr.execute("SELECT id FROM campus_offering WHERE id = %s FOR UPDATE", [self.id])

        policy = self.env["campus.academic.policy"]._get_active_policy()
        Enrollment = self.env["campus.enrollment"].sudo()
        sudo_offering = self.sudo()

        term = sudo_offering.term_id
        if not term:
            raise UserError(_("Хичээлд улирал оноогоогүй тул бүртгүүлэх боломжгүй."))
        today = fields.Date.context_today(self)
        if not term.registration_start <= today <= term.registration_end:
            raise UserError(_("Бүртгэлийн хугацаа нээлттэй биш байна: %s – %s.") % (
                term.registration_start, term.registration_end))
        if sudo_offering.state != "open":
            raise UserError(_("Энэ хичээлийн бүртгэл нээлттэй биш байна."))

        existing = Enrollment.search([("student_id", "=", student.id), ("offering_id", "=", self.id)], limit=1)
        if existing and existing.reg_state != "dropped":
            raise UserError(_("Оюутан энэ хичээлд аль хэдийн бүртгэгдсэн байна."))

        taken = Enrollment.search_count([("offering_id", "=", self.id), ("reg_state", "=", "enrolled")])
        if taken >= sudo_offering.capacity:
            raise UserError(_("Суудал дүүрсэн байна (багтаамж %s).") % sudo_offering.capacity)

        course = sudo_offering.course_id
        passed = Enrollment.search([
            ("student_id", "=", student.id),
            ("reg_state", "=", "completed"),
            ("score", ">=", policy.pass_score),
        ]).mapped("offering_id.course_id")
        missing = course.prerequisite_ids - passed
        if missing:
            raise UserError(_("Урьдчилсан нөхцөл хангагдаагүй: %s хичээлийг тэнцсэн байх шаардлагатай.")
                            % ", ".join(missing.mapped("code")))

        active = Enrollment.search([
            ("student_id", "=", student.id),
            ("reg_state", "=", "enrolled"),
            ("offering_id.term_id", "=", term.id),
        ])
        current_credits = sum(active.mapped("offering_id.course_id.credits"))
        if current_credits + course.credits > policy.max_credits_per_term:
            raise UserError(_(
                "Улирлын кредитийн дээд хэмжээ (%s) давна. Одоогийн: %s, нэмэх: %s."
            ) % (policy.max_credits_per_term, current_credits, course.credits))

        my_sessions = sudo_offering.session_ids
        if my_sessions:
            other_offerings = Enrollment.search([
                ("student_id", "=", student.id),
                ("reg_state", "=", "enrolled"),
                ("offering_id", "!=", self.id),
            ]).mapped("offering_id")
            if other_offerings:
                Session = self.env["campus.session"].sudo()
                for session in my_sessions:
                    clash = Session.search([
                        ("offering_id", "in", other_offerings.ids),
                        ("start", "<", session.end),
                        ("end", ">", session.start),
                    ], limit=1)
                    if clash:
                        raise UserError(_("Цагийн хуваарь давхцаж байна: %s / %s.") % (
                            clash.offering_id.name, clash.offering_id.course_id.code))

        values = {
            "reg_state": "enrolled",
            "registered_by_id": user.id,
            "registered_at": fields.Datetime.now(),
            "dropped_by_id": False,
            "dropped_at": False,
        }
        if existing:
            existing.write(values)
            enrollment = existing
        else:
            enrollment = Enrollment.create(dict(values, student_id=student.id, offering_id=self.id))
        return enrollment.with_env(self.env)
