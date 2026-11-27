import hashlib
import re
import secrets

from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+", re.ASCII)
_DECISION = object()

STATE_LABELS = (
    ("submitted", "Хүлээн авсан"),
    ("review", "Хянаж буй"),
    ("accepted", "Элсэх эрх олгосон"),
    ("declined", "Тэнцээгүй"),
)


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class FormulaPublicProgram(models.Model):
    _inherit = "formula.public.program"

    academic_program_id = fields.Many2one(
        "campus.program", string="ERP-ийн сургалтын хөтөлбөр", ondelete="restrict",
    )

    @api.model
    def _match_academic_programs(self):
        known = {
            "cybersecurity": ("FU-CY", "SEC"),
            "business-analytics": ("FU-BA",),
            "digital-design": ("FU-DD",),
        }
        for slug, codes in known.items():
            entry = self.search([("slug", "=", slug), ("academic_program_id", "=", False)], limit=1)
            for code in codes if entry else ():
                academic = self.env["campus.program"].search([("code", "=", code)], limit=1)
                if academic:
                    entry.academic_program_id = academic
                    break


class FormulaAdmission(models.Model):
    _name = "formula.campus.admission"
    _description = "Элсэх өргөдөл"
    _inherit = ["mail.thread"]
    _order = "id desc"

    reference = fields.Char(string="Өргөдлийн дугаар", readonly=True, required=True, copy=False, index=True)
    name = fields.Char(string="Овог нэр", required=True)
    email = fields.Char(string="Холбогдох цахим шуудан", required=True, index=True)
    program_id = fields.Many2one("formula.public.program", string="Сонгосон хөтөлбөр", required=True,
                                 ondelete="restrict")
    academic_program_id = fields.Many2one("campus.program", string="Сургалтын хөтөлбөр",
                                          required=True, ondelete="restrict")
    motivation = fields.Text(string="Суралцах зорилго", required=True)
    state = fields.Selection(STATE_LABELS, string="Төлөв", default="submitted", required=True,
                             readonly=True, tracking=True, index=True)
    checked_by_id = fields.Many2one("res.users", string="Шийдвэр гаргасан", readonly=True)
    decision_at = fields.Datetime(string="Шийдвэрийн огноо", readonly=True)
    review_note = fields.Text(string="Сургалтын албаны дотоод тэмдэглэл")
    decision_message = fields.Text(string="Өргөдөл гаргагчид харуулах тайлбар")
    student_id = fields.Many2one("campus.student", string="Үүссэн оюутны бүртгэл", readonly=True,
                                 copy=False, ondelete="restrict")
    token_digest = fields.Char(required=True, copy=False, index=True, groups="base.group_system")
    invited_at = fields.Datetime(string="Порталын урилга илгээсэн", readonly=True)

    _sql_constraints = [
        ("reference_uniq", "unique(reference)", "Өргөдлийн дугаар давхардахгүй."),
        ("token_uniq", "unique(token_digest)", "Төлөв шалгах код давхардахгүй."),
        ("student_uniq", "unique(student_id)", "Оюутанд нэг элсэлтийн шийдвэр холбоно."),
    ]

    def _check_registrar(self):
        if not self.env.user.has_group("campus_university.group_campus_registrar"):
            raise AccessError(_("Элсэх өргөдлийг сургалтын алба шийднэ."))
        self.check_access("write")

    def write(self, vals):
        if self.env.context.get("_formula_admission_decision") is not _DECISION:
            self._check_registrar()
            if not set(vals) <= {"review_note", "decision_message"}:
                raise AccessError(_("Өргөдлийн шийдвэрийг зориулалтын үйлдлээр өөрчилнө."))
            self._lock_for_review()
            if self.filtered(lambda row: row.state in ("accepted", "declined")):
                raise UserError(_("Шийдвэрлэсэн өргөдлийн мэдээллийг өөрчлөхгүй."))
        return super().write(vals)

    def _lock_for_review(self):
        self.flush_recordset()
        self.env.cr.execute(
            "SELECT id FROM formula_campus_admission WHERE id = ANY(%s) ORDER BY id FOR UPDATE", [self.ids],
        )
        self.invalidate_recordset()

    def _official_write(self, values):
        return self.with_context(_formula_admission_decision=_DECISION).write(values)

    @api.model
    def _submit_public(self, *, name, email, program, motivation):
        program.check_access("read")
        if not program.published or not program.academic_program_id.active:
            raise ValidationError(_("Энэ хөтөлбөр одоогоор өргөдөл авахгүй байна."))
        if not 2 <= len(name) <= 100 or len(email) > 160 or not _EMAIL.fullmatch(email):
            raise ValidationError(_("Овог нэр, цахим шуудангаа шалгана уу."))
        if not 20 <= len(motivation) <= 1200:
            raise ValidationError(_("Суралцах зорилгоо 20–1200 тэмдэгтээр бичнэ үү."))
        token = secrets.token_urlsafe(24)
        record = self.create({
            "reference": self.env["ir.sequence"].next_by_code("formula.campus.admission"),
            "name": name, "email": email, "program_id": program.id,
            "academic_program_id": program.academic_program_id.id, "motivation": motivation,
            "token_digest": token_digest(token),
        })
        return record.reference, token

    def action_start_review(self):
        self.ensure_one()
        self._check_registrar()
        self._lock_for_review()
        if self.state != "submitted":
            raise UserError(_("Зөвхөн шинээр ирсэн өргөдлийг хянана."))
        self._official_write({"state": "review"})

    def action_decide_decline(self):
        self.ensure_one()
        self._check_registrar()
        self._lock_for_review()
        if self.state != "review" or not (self.decision_message or "").strip():
            raise UserError(_("Хянаж буй өргөдөлд шийдвэрийн тайлбар оруулна уу."))
        self._official_write({"state": "declined", "decision_at": fields.Datetime.now(),
                              "checked_by_id": self.env.uid})

    def action_decide_accept(self):
        self.ensure_one()
        self._check_registrar()
        self._lock_for_review()
        if self.state != "review":
            raise UserError(_("Зөвхөн хянаж буй өргөдлийг батална."))
        if not self.academic_program_id.active:
            raise UserError(_("Сургалтын хөтөлбөр идэвхгүй байна."))
        student_group = self.env.ref("campus_university.group_campus_student")
        Users = self.env["res.users"].sudo().with_context(active_test=False, no_reset_password=True)
        # Never attach an application to an existing account by email alone.
        if Users.search_count(["|", ("login", "=ilike", self.email), ("email", "=ilike", self.email)]):
            raise UserError(_("Энэ хаягтай бүртгэл байна. Өргөдөл гаргагчийн мэдээллийг сургалтын алба тулгана уу."))
        user = Users.create({
            "name": self.name, "login": self.email, "email": self.email,
            "groups_id": [Command.set(student_group.ids)], "notification_type": "email",
        })
        student = self.env["campus.student"].create({
            "student_code": self.env["ir.sequence"].sudo().next_by_code("formula.campus.admitted_student"),
            "name": self.name, "user_id": user.id, "program_id": self.academic_program_id.id,
        })
        self._official_write({"state": "accepted", "student_id": student.id,
                              "decision_at": fields.Datetime.now(), "checked_by_id": self.env.uid})

    def action_invite_portal(self):
        self.ensure_one()
        self._check_registrar()
        self._lock_for_review()
        if self.state != "accepted" or not self.student_id.user_id or self.invited_at:
            raise UserError(_("Зөвхөн элссэн, урилга аваагүй оюутанд илгээнэ."))
        if not self.env["ir.mail_server"].sudo().search_count([], limit=1):
            raise UserError(_("Цахим шуудангийн сервер тохируулаагүй байна."))
        user = self.student_id.user_id.sudo()
        if user.login != self.email or user.email != self.email or not user.share:
            raise UserError(_("Оюутны порталын бүртгэл өөрчлөгдсөн байна."))
        user.with_context(create_user=True).action_reset_password()
        self._official_write({"invited_at": fields.Datetime.now()})
