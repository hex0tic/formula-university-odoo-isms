from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .common import is_registrar


class CampusSession(models.Model):
    _name = "campus.session"
    _description = "Хичээлийн цаг"
    _order = "start, id"

    name = fields.Char(compute="_compute_name", store=True)
    offering_id = fields.Many2one("campus.offering", string="Хичээл", required=True,
                                  ondelete="restrict", index=True)
    term_id = fields.Many2one(related="offering_id.term_id", string="Улирал", readonly=True)
    lecturer_id = fields.Many2one(related="offering_id.lecturer_id", string="Багш", readonly=True)
    start = fields.Datetime(string="Эхлэх", required=True, index=True)
    end = fields.Datetime(string="Дуусах", required=True)
    room = fields.Char(string="Танхим")
    kind = fields.Selection(
        [("lecture", "Лекц"), ("lab", "Лаборатори"), ("seminar", "Семинар")],
        string="Төрөл", default="lecture", required=True,
    )
    attendance_ids = fields.One2many("campus.attendance", "session_id", string="Ирц")

    @api.depends("offering_id.name", "start")
    def _compute_name(self):
        for rec in self:
            when = fields.Datetime.to_string(rec.start)[:16] if rec.start else ""
            rec.name = "%s %s" % (rec.offering_id.name or "", when)

    @api.constrains("start", "end", "room", "offering_id")
    def _check_time_clashes(self):
        Session = self.env["campus.session"].sudo()
        for rec in self:
            if rec.end <= rec.start:
                raise ValidationError(_("Хичээлийн дуусах цаг эхлэх цагаас хойш байна."))
            base = [("id", "!=", rec.id), ("start", "<", rec.end), ("end", ">", rec.start)]
            if rec.room:
                clash = Session.search(base + [("room", "=", rec.room)], limit=1)
                if clash:
                    raise ValidationError(_("Танхим давхцаж байна: %s.") % clash.name)
            lecturer = rec.sudo().offering_id.lecturer_id
            if lecturer:
                clash = Session.search(base + [("offering_id.lecturer_id", "=", lecturer.id)], limit=1)
                if clash:
                    raise ValidationError(_("Багш давхцаж байна: %s.") % clash.name)


class CampusAttendance(models.Model):
    _name = "campus.attendance"
    _description = "Ирц"
    _order = "session_id, enrollment_id"

    session_id = fields.Many2one("campus.session", string="Цаг", required=True,
                                 ondelete="restrict", index=True)
    enrollment_id = fields.Many2one("campus.enrollment", string="Бүртгэл", required=True,
                                    ondelete="restrict", index=True)
    student_id = fields.Many2one(related="enrollment_id.student_id", string="Оюутан",
                                 store=True, readonly=True, index=True)
    status = fields.Selection(
        [("present", "Ирсэн"), ("absent", "Тасалсан"), ("late", "Хоцорсон"), ("excused", "Чөлөөтэй")],
        string="Төлөв", required=True,
    )
    recorded_by = fields.Many2one("res.users", string="Бүртгэсэн", readonly=True, copy=False,
                                  ondelete="restrict")
    recorded_at = fields.Datetime(string="Бүртгэсэн огноо", readonly=True, copy=False)

    _sql_constraints = [
        ("session_enrollment_unique", "unique(session_id, enrollment_id)",
         "Нэг оюутны нэг цагийн ирц давхардахгүй."),
    ]

    @api.constrains("session_id", "enrollment_id")
    def _check_same_offering(self):
        for rec in self:
            if rec.enrollment_id.sudo().offering_id != rec.session_id.sudo().offering_id:
                raise ValidationError(_("Ирцийн бүртгэл энэ хичээлийн оюутанд хамаарахгүй."))

    def _check_can_record(self, session):
        """Only the offering's lecturer or the registrar records attendance."""
        if is_registrar(self.env):
            return
        if session.sudo().offering_id.lecturer_id != self.env.user:
            raise AccessError(_("Зөвхөн энэ хичээлийг заадаг багш эсвэл сургалтын алба ирц бүртгэнэ."))

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        clean = []
        for vals in vals_list:
            session = self.env["campus.session"].browse(vals["session_id"])
            session.check_access("read")
            self._check_can_record(session)
            enrollment = self.env["campus.enrollment"].browse(vals["enrollment_id"])
            enrollment.check_access("read")
            if enrollment.reg_state == "dropped":
                raise UserError(_("Хасагдсан бүртгэлд ирц бүртгэхгүй."))
            clean.append(dict(vals, recorded_by=self.env.uid, recorded_at=now))
        return super().create(clean)

    def write(self, vals):
        if {"session_id", "enrollment_id"}.intersection(vals):
            raise ValidationError(_("Ирцийн цаг эсвэл оюутныг солихгүй. Шинээр бүртгэнэ."))
        if "status" in vals:
            for rec in self:
                self._check_can_record(rec.session_id)
            vals = dict(vals, recorded_by=self.env.uid, recorded_at=fields.Datetime.now())
        return super().write(vals)

    @api.model
    def record(self, session, enrollment, status):
        """Create or update the attendance status of one enrollment in one session."""
        # Re-browse in the caller's environment so ACL and record rules apply to this call.
        session = self.env["campus.session"].browse(session.id)
        enrollment = self.env["campus.enrollment"].browse(enrollment.id)
        session.ensure_one()
        enrollment.ensure_one()
        existing = self.search([("session_id", "=", session.id), ("enrollment_id", "=", enrollment.id)],
                               limit=1)
        if existing:
            existing.write({"status": status})
            return existing
        return self.create({"session_id": session.id, "enrollment_id": enrollment.id, "status": status})
