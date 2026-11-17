from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare


# An RPC caller can supply arbitrary context values, but cannot recreate this
# process-local identity. Never use a truthy context flag for grade authority.
_GRADE_AUTHORITY = object()
_REVIEW_AUTHORITY = object()


def _require_registrar(env):
    if not env.su and not env.user.has_group("campus_university.group_campus_registrar"):
        raise AccessError(_("Зөвхөн сургалтын алба энэ үйлдлийг гүйцэтгэнэ."))


class CampusProgram(models.Model):
    _name = "campus.program"
    _description = "Сургалтын хөтөлбөр"
    _order = "code"

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    department = fields.Char(required=True)
    owner_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    active = fields.Boolean(default=True)

    _sql_constraints = [("code_unique", "unique(code)", "Хөтөлбөрийн код давхардахгүй.")]


class CampusStudent(models.Model):
    _name = "campus.student"
    _description = "Оюутны сургалтын бүртгэл"
    _order = "student_code"

    student_code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    user_id = fields.Many2one("res.users", ondelete="restrict", index=True)
    program_id = fields.Many2one("campus.program", required=True, ondelete="restrict")
    institutional_email = fields.Char(string="Сургуулийн цахим шуудан")
    status = fields.Selection(
        [("active", "Суралцаж буй"), ("leave", "Чөлөөтэй"), ("graduated", "Төгссөн")],
        default="active", required=True,
    )
    enrollment_ids = fields.One2many("campus.enrollment", "student_id", string="Хичээлийн бүртгэл")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("student_code_unique", "unique(student_code)", "Оюутны код давхардахгүй."),
        ("user_unique", "unique(user_id)", "Нэг хэрэглэгч нэг оюутантай холбогдоно."),
    ]


class CampusCourse(models.Model):
    _name = "campus.course"
    _description = "Хичээлийн каталог"
    _order = "code"

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    credits = fields.Integer(default=3, required=True)
    program_id = fields.Many2one("campus.program", required=True, ondelete="restrict")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_unique", "unique(code)", "Хичээлийн код давхардахгүй."),
        ("credits_range", "check(credits between 1 and 6)", "Кредит 1–6 байна."),
    ]


class CampusOffering(models.Model):
    _name = "campus.offering"
    _description = "Улирлын хичээл"
    _order = "semester desc, name"

    name = fields.Char(required=True)
    course_id = fields.Many2one("campus.course", required=True, ondelete="restrict")
    semester = fields.Char(required=True, default="2026-A")
    lecturer_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    state = fields.Selection(
        [("draft", "Бэлтгэл"), ("open", "Нээлттэй"), ("locked", "Улирал хаасан")],
        default="draft", required=True,
    )
    enrollment_ids = fields.One2many("campus.enrollment", "offering_id")

    def action_open(self):
        _require_registrar(self.env)
        self.write({"state": "open"})

    def action_lock(self):
        _require_registrar(self.env)
        self.write({"state": "locked"})


class CampusEnrollment(models.Model):
    _name = "campus.enrollment"
    _description = "Оюутны хичээлийн дүн"
    _rec_name = "name"
    _order = "offering_id, student_id"

    student_id = fields.Many2one("campus.student", required=True, ondelete="restrict", index=True)
    offering_id = fields.Many2one("campus.offering", required=True, ondelete="restrict", index=True)
    name = fields.Char(compute="_compute_name", store=True, index=True)
    score = fields.Float(string="Баталгаат дүн", default=0, digits=(5, 2), readonly=True)
    grade_revision = fields.Integer(default=0, readonly=True)
    change_ids = fields.One2many("campus.grade.change", "enrollment_id")

    _sql_constraints = [
        ("enrollment_unique", "unique(student_id, offering_id)", "Хичээлийн бүртгэл давхардахгүй."),
        ("score_range", "check(score between 0 and 100)", "Дүн 0–100 байна."),
        ("revision_nonnegative", "check(grade_revision >= 0)", "Хувилбар сөрөг байж болохгүй."),
    ]

    @api.depends("student_id.name", "offering_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s / %s" % (rec.student_id.name or "", rec.offering_id.name or "")

    @api.model_create_multi
    def create(self, vals_list):
        _require_registrar(self.env)
        for vals in vals_list:
            if vals.get("grade_revision", 0) != 0:
                raise AccessError(_("Анхны хувилбар 0 байна."))
        return super().create(vals_list)

    def write(self, vals):
        trusted = self.env.context.get("_campus_grade_authority") is _GRADE_AUTHORITY
        if {"score", "grade_revision"}.intersection(vals) and not trusted:
            raise AccessError(_("Дүнг шууд засахгүй. Дүн өөрчлөх хүсэлт гаргана уу."))
        if {"student_id", "offering_id"}.intersection(vals):
            if any(rec.change_ids for rec in self):
                raise ValidationError(_("Дүнгийн түүхтэй бүртгэлийн оюутан, хичээлийг солихгүй."))
        return super().write(vals)

    def unlink(self):
        if any(rec.change_ids for rec in self):
            raise ValidationError(_("Дүнгийн түүхтэй хичээлийн бүртгэлийг устгахгүй."))
        return super().unlink()

    def _apply_approved_change(self, change):
        self.ensure_one()
        change.ensure_one()
        _require_registrar(self.env)
        if change.enrollment_id != self or change.state != "submitted":
            raise ValidationError(_("Зөвхөн хүлээгдэж буй ижил бүртгэлийн хүсэлтийг батална."))
        if change.requester_id == self.env.user:
            raise AccessError(_("Хүсэлт гаргагч өөрийн хүсэлтийг батлахгүй."))
        # Serialize two simultaneous approvals, then invalidate the cached score.
        self.env.cr.execute("SELECT id FROM campus_enrollment WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset(["score", "grade_revision"])
        if (self.grade_revision != change.old_revision or
                float_compare(self.score, change.old_score, precision_digits=2)):
            raise ValidationError(_("Дүн өөр хүсэлтээр өөрчлөгдсөн. Шинэ хүсэлт гаргана уу."))
        self.with_context(_campus_grade_authority=_GRADE_AUTHORITY).sudo().write({
            "score": change.proposed_score,
            "grade_revision": self.grade_revision + 1,
        })


class CampusGradeChange(models.Model):
    _name = "campus.grade.change"
    _description = "Дүн өөрчлөх хяналттай хүсэлт"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", required=True, readonly=True, copy=False)
    enrollment_id = fields.Many2one("campus.enrollment", required=True, ondelete="restrict", index=True)
    student_id = fields.Many2one(related="enrollment_id.student_id", store=True, readonly=True)
    offering_id = fields.Many2one(related="enrollment_id.offering_id", store=True, readonly=True)
    old_score = fields.Float(digits=(5, 2), readonly=True)
    old_revision = fields.Integer(readonly=True)
    proposed_score = fields.Float(required=True, digits=(5, 2), tracking=True)
    reason = fields.Text(required=True)
    evidence_ref = fields.Char(string="Нотолгооны лавлагаа")
    requester_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict",
                                   default=lambda self: self.env.user)
    state = fields.Selection(
        [("draft", "Ноорог"), ("submitted", "Хянуулахаар илгээсэн"),
         ("approved", "Баталсан"), ("rejected", "Татгалзсан")],
        default="draft", required=True, readonly=True, tracking=True, copy=False,
    )
    submitted_at = fields.Datetime(readonly=True, copy=False)
    approver_id = fields.Many2one("res.users", readonly=True, ondelete="restrict", copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    review_note = fields.Text(string="Хянасан тайлбар")

    _sql_constraints = [
        ("score_range", "check(proposed_score between 0 and 100)", "Шинэ дүн 0–100 байна."),
        ("independent_approval", "check(approver_id is null or requester_id != approver_id)",
         "Хүсэлт гаргагч ба батлагч өөр хүн байна."),
    ]

    @api.onchange("enrollment_id")
    def _onchange_enrollment_snapshot(self):
        for rec in self:
            if rec.enrollment_id:
                rec.old_score = rec.enrollment_id.score
                rec.old_revision = rec.enrollment_id.grade_revision

    @api.constrains("reason")
    def _check_reason(self):
        for rec in self:
            if len((rec.reason or "").strip()) < 10:
                raise ValidationError(_("Дүн өөрчлөх үндэслэлийг 10-аас доошгүй тэмдэгтээр бичнэ."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not (
            self.env.user.has_group("campus_university.group_campus_lecturer") or
            self.env.user.has_group("campus_university.group_campus_registrar")
        ):
            raise AccessError(_("Багш эсвэл сургалтын алба хүсэлт гаргана."))
        clean = []
        for source in vals_list:
            vals = dict(source)
            forbidden = {"approver_id", "approved_at", "submitted_at", "old_score", "old_revision"}
            if forbidden.intersection(vals) or vals.get("state", "draft") != "draft":
                raise AccessError(_("Хүсэлтийн эзэн, төлөв, баталгааны талбарыг систем үүсгэнэ."))
            if vals.get("requester_id", self.env.uid) != self.env.uid:
                raise AccessError(_("Хүсэлтийг өөр хэрэглэгчийн нэрээр үүсгэхгүй."))
            enrollment = self.env["campus.enrollment"].browse(vals.get("enrollment_id")).exists()
            if not enrollment:
                raise ValidationError(_("Хичээлийн бүртгэл сонгоно уу."))
            enrollment.check_access("read")
            if not self.env.su and not self.env.user.has_group("campus_university.group_campus_registrar"):
                if enrollment.offering_id.lecturer_id != self.env.user:
                    raise AccessError(_("Зөвхөн өөрийн заадаг хичээлийн дүнд хүсэлт гаргана."))
            if enrollment.offering_id.state == "draft":
                raise UserError(_("Бэлтгэл төлөвтэй хичээлийн дүнд хүсэлт гаргахгүй."))
            vals.update({
                "name": self.env["ir.sequence"].next_by_code("campus.grade.change") or "New",
                "requester_id": self.env.uid,
                "old_score": enrollment.score,
                "old_revision": enrollment.grade_revision,
                "state": "draft",
            })
            clean.append(vals)
        return super().create(clean)

    def write(self, vals):
        trusted = self.env.context.get("_campus_review_authority") is _REVIEW_AUTHORITY
        immutable = {"name", "enrollment_id", "old_score", "old_revision", "requester_id", "student_id", "offering_id"}
        if immutable.intersection(vals):
            raise AccessError(_("Хүсэлтийн үндсэн бүртгэлийг сольж болохгүй."))
        if {"state", "approver_id", "approved_at", "submitted_at"}.intersection(vals) and not trusted:
            raise AccessError(_("Төлөвийг зөвхөн хяналттай үйлдлээр шилжүүлнэ."))
        if {"proposed_score", "reason", "evidence_ref"}.intersection(vals):
            if any(rec.state != "draft" or rec.requester_id != self.env.user for rec in self):
                raise AccessError(_("Зөвхөн эзэн нь ноорог хүсэлтээ засна."))
        if "review_note" in vals:
            _require_registrar(self.env)
            if any(rec.state != "submitted" for rec in self):
                raise AccessError(_("Хянах тайлбарыг зөвхөн хүлээгдэж буй хүсэлтэд бичнэ."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state != "draft" or rec.requester_id != self.env.user for rec in self):
            raise AccessError(_("Зөвхөн өөрийн ноорог хүсэлтийг устгана."))
        return super().unlink()

    def action_submit(self):
        for rec in self:
            rec.check_access("write")
            if rec.state != "draft" or rec.requester_id != self.env.user:
                raise AccessError(_("Зөвхөн өөрийн ноорог хүсэлтийг илгээнэ."))
            if not float_compare(rec.old_score, rec.proposed_score, precision_digits=2):
                raise ValidationError(_("Шинэ дүн хуучин дүнгээс ялгаатай байна."))
            rec.with_context(_campus_review_authority=_REVIEW_AUTHORITY).write({
                "state": "submitted", "submitted_at": fields.Datetime.now(),
            })

    def action_approve(self):
        _require_registrar(self.env)
        for rec in self:
            rec.check_access("write")
            if rec.state != "submitted":
                raise ValidationError(_("Зөвхөн хянуулахаар илгээсэн хүсэлтийг батална."))
            rec.enrollment_id._apply_approved_change(rec)
            rec.with_context(_campus_review_authority=_REVIEW_AUTHORITY).write({
                "state": "approved", "approver_id": self.env.uid, "approved_at": fields.Datetime.now(),
            })

    def action_reject(self):
        _require_registrar(self.env)
        for rec in self:
            rec.check_access("write")
            if rec.state != "submitted" or rec.requester_id == self.env.user:
                raise AccessError(_("Өөр ажилтны илгээсэн хүсэлтэд шийдвэр гаргана."))
            if not (rec.review_note or "").strip():
                raise ValidationError(_("Татгалзсан үндэслэлийг хянасан тайлбарт бичнэ үү."))
            rec.with_context(_campus_review_authority=_REVIEW_AUTHORITY).write({
                "state": "rejected", "approver_id": self.env.uid, "approved_at": fields.Datetime.now(),
            })
