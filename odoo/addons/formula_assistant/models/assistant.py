from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResUsers(models.Model):
    _inherit = "res.users"

    form_assistant_hidden = fields.Boolean(groups="base.group_system", copy=False)
    form_assistant_size = fields.Selection(
        [("small", "Жижиг"), ("normal", "Дунд"), ("large", "Том")],
        default="normal", groups="base.group_system", copy=False,
    )
    form_assistant_last_brief = fields.Date(groups="base.group_system", copy=False)


class FormulaAssistant(models.AbstractModel):
    _name = "formula.assistant"
    _description = "Form personal assistant"

    @api.model
    def _clock(self):
        tz = ZoneInfo(self.env.user.tz or "Asia/Ulaanbaatar")
        today = datetime.now(tz).date()
        start = datetime.combine(today, time.min, tzinfo=tz)
        utc = ZoneInfo("UTC")
        return (today, start.astimezone(utc).replace(tzinfo=None),
                (start + timedelta(days=1)).astimezone(utc).replace(tzinfo=None))

    @api.model
    def _preferences(self, hidden=None, size=None, seen=None):
        vals = {}
        today = self._clock()[0]
        if hidden is not None:
            if type(hidden) is not bool:
                raise ValidationError(_("Харагдацын тохиргоо буруу байна."))
            vals["form_assistant_hidden"] = hidden
        if size is not None:
            if size not in ("small", "normal", "large"):
                raise ValidationError(_("Жижиг, дунд, том хэмжээнээс сонгоно уу."))
            vals["form_assistant_size"] = size
        if seen is not None:
            if seen is not True:
                raise ValidationError(_("Сануулгын төлөв буруу байна."))
            vals["form_assistant_last_brief"] = today
        # Sudo is limited to fixed preference fields on the signed-in account.
        user = self.env.user.sudo()
        if vals:
            user.write(vals)
        return {
            "hidden": user.form_assistant_hidden,
            "size": user.form_assistant_size or "normal",
            "greet": user.form_assistant_last_brief != today,
        }

    @api.model
    def _initial(self):
        pref = self._preferences()
        return {
            **pref,
            "name": self.env.user.name,
            "brief": self._briefing() if not pref["hidden"] and pref["greet"] else False,
        }

    @api.model
    def _rows(self, model, domain, order, label, url=None, limit=5):
        if model not in self.env:
            return 0, []
        records = self.env[model]
        if not records.has_access("read"):
            return 0, []
        total = records.search_count(domain)
        items = records.search(domain, order=order, limit=limit) if total else records
        return total, [{"text": label(rec), "url": url(rec) if url else False} for rec in items]

    @api.model
    def _work(self):
        today, _start, end = self._clock()
        uid = self.env.uid
        tasks, task_rows = self._rows(
            "project.task", [
                ("user_ids", "in", [uid]), ("is_closed", "=", False),
                ("date_deadline", "!=", False), ("date_deadline", "<", end),
            ], "date_deadline asc, id", lambda r: r.env._("Даалгавар: %s", r.name),
            lambda r: "/web#model=project.task&id=%d&view_type=form" % r.id,
        )
        acts, activity_rows = self._rows(
            "mail.activity", [("user_id", "=", uid), ("date_deadline", "<=", today)],
            "date_deadline asc, id", lambda r: r.env._("Үйл ажиллагаа: %s", r.activity_type_id.name),
        )
        incs, incident_rows = self._rows(
            "isms.incident", [
                ("assignee_id", "=", uid), ("state", "in", ("incident", "report", "investigate")),
                ("sla_deadline", "!=", False), ("sla_deadline", "<", end),
            ], "sla_deadline asc, id", lambda r: r.env._("Инцидент: %s", r.code),
            lambda r: "/web#model=isms.incident&id=%d&view_type=form" % r.id,
        )
        return tasks + acts + incs, (task_rows + activity_rows + incident_rows)[:5]

    @api.model
    def _classes(self):
        _today, start, end = self._clock()
        tz = self.env.user.tz or "Asia/Ulaanbaatar"
        user = self.env.user
        if user.has_group("campus_university.group_campus_student"):
            portal = self.env["campus.portal.student"].with_context(tz=tz)
            student = portal._own_student()
            if student:
                enrolled = portal._own_enrollments(student).filtered(lambda r: r.reg_state == "enrolled")
                agenda = portal._student_agenda(enrolled)
                return agenda["today_count"], [
                    {"text": "%s · %s" % (row["start"], row["title"]), "url": "/my/campus/schedule"}
                    for row in agenda["today_sessions"]
                ]
        if user.has_group("campus_university.group_campus_lecturer"):
            return self._rows(
                "campus.session", [
                    ("offering_id.lecturer_id", "=", user.id), ("start", ">=", start),
                    ("start", "<", end),
                ], "start asc, id",
                lambda r: "%s · %s" % (
                    fields.Datetime.context_timestamp(self.with_context(tz=tz), r.start).strftime("%H:%M"),
                    r.offering_id.course_id.name,
                ), lambda r: "/campus/teacher", limit=3,
            )
        return 0, []

    @api.model
    def _briefing(self):
        work, items = self._work() if not self.env.user.share else (0, [])
        classes, class_items = self._classes()
        highlights = []
        if work:
            highlights.append(_("Өнөөдөр дуусах эсвэл хугацаа хэтэрсэн %s ажил байна.", work))
        if classes:
            highlights.append(_("Өнөөдөр %s хичээлтэй.", classes))
        return {
            "text": " ".join(highlights) or _("Өнөөдөр танд сануулах ажил, хичээл алга."),
            "items": (class_items + items)[:5],
        }

    @api.model
    def _answer(self, question):
        query = " ".join(question.casefold().split())
        if any(word in query for word in ("хуваарь", "хичээл", "schedule", "class")):
            count, items = self._classes()
            return {"text": _("Өнөөдөр %s хичээлтэй.", count) if count else _("Өнөөдөр хичээл бүртгэгдээгүй байна."),
                    "items": items}
        if any(word in query for word in ("өнөөдөр", "өнөөдрийн", "ажил", "даалгавар", "сануул", "today", "task")):
            return self._briefing()
        if query.rstrip("!?., ") in ("сайн уу", "сайн байна уу", "hi", "hello", "hey"):
            return {"text": _("Сайн уу! Би Form. Өнөөдрийн ажил, хичээлийн хуваарийг тань сануулна."), "items": []}
        user = self.env.user
        # Keep the separate Copilot's external provider outside the Form widget.
        if ("formula.isms.copilot" in self.env and not user.share
                and user.has_group("university_isms.group_isms_reporter")
                and any(word in query for word in ("бодлого", "эрсдэл", "инцидент", "хяналт", "ism", "risk", "policy"))):
            copilot = self.env["formula.isms.copilot"]
            keys = copilot._normalize_scope(None)
            blocks, _matched, _tokens = copilot._retrieve(question, keys)
            if blocks:
                return {"text": "\n".join(copilot._compose_local(blocks)[:3]),
                        "items": [{"text": row["display_name"], "url": row["link"]} for row in blocks[:3]]}
        return {"text": _("«Өнөөдрийн ажил» эсвэл «Хичээлийн хуваарь» гэж асуугаарай. "
                          "Би таны бүртгэлд харагдах мэдээллээр хариулна."), "items": []}
