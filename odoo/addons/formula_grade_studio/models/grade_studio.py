# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext
from odoo.tools.float_utils import float_compare

GRADE_MODEL = "campus.grade.change"
ENROLLMENT_MODEL = "campus.enrollment"
LECTURER_GROUP = "campus_university.group_campus_lecturer"
REGISTRAR_GROUP = "campus_university.group_campus_registrar"
AUDITOR_GROUP = "campus_university.group_campus_auditor"
STAFF_GROUPS = (LECTURER_GROUP, REGISTRAR_GROUP, AUDITOR_GROUP)
FILTERS = ("pending", "mine", "stale", "all")
QUEUE_LIMIT = 200
HISTORY_LIMIT = 100
ISMS_LOG_LIMIT = 50
QUEUE_ORDER = "create_date desc, id desc"


class FormulaGradeStudio(models.AbstractModel):
    """Read-only service behind the Grade Change Approval Studio client action.

    Every read runs with the caller's own ORM access rights (no sudo). The
    ``actions`` returned here are informational: the model methods
    ``action_submit``, ``action_approve`` and ``action_reject`` remain the only
    authority and re-validate everything on the server.
    """

    _name = "formula.grade.studio"
    _description = "Grade Change Approval Studio service"

    # ------------------------------------------------------------ public API
    @api.model
    def get_queue(self, options=None):
        options = options or {}
        flt = options.get("filter") or "pending"
        if flt not in FILTERS:
            raise UserError(_("Шүүлтүүрийн утга буруу байна."))
        empty_counts = {"pending": 0, "mine": 0, "stale": 0, "all": 0}
        if not self._studio_can_open():
            return {"access_denied": True, "filter": flt, "counts": empty_counts,
                    "items": [], "truncated": False}

        change = self.env[GRADE_MODEL]
        pending = change.search([("state", "=", "submitted")], order=QUEUE_ORDER)
        freshness = {rec.id: self._freshness(rec) for rec in pending}
        stale_pending = pending.filtered(lambda rec: freshness[rec.id]["stale"])
        counts = {
            "pending": len(pending),
            "stale": len(stale_pending),
            "mine": change.search_count([("requester_id", "=", self.env.uid)]),
            "all": change.search_count([]),
        }

        truncated = False
        if flt == "pending":
            records = pending
        elif flt == "stale":
            records = stale_pending
        elif flt == "mine":
            records = change.search([("requester_id", "=", self.env.uid)],
                                    order=QUEUE_ORDER, limit=QUEUE_LIMIT + 1)
        else:
            records = change.search([], order=QUEUE_ORDER, limit=QUEUE_LIMIT + 1)
        if len(records) > QUEUE_LIMIT:
            truncated = True
            records = records[:QUEUE_LIMIT]

        items = []
        for rec in records:
            fresh = freshness.get(rec.id) or self._freshness(rec)
            items.append(self._row(rec, fresh))
        return {"access_denied": False, "filter": flt, "counts": counts,
                "items": items, "truncated": truncated}

    @api.model
    def reject_with_note(self, request_id, note):
        """Write the review note and reject in one transaction, as the current user.

        Both steps go through the grade-change model's own write and action_reject,
        so its registrar, self-approval and state checks stay authoritative.
        """
        rec = self.env["campus.grade.change"].browse(int(request_id)).exists()
        if not rec:
            raise UserError(_("Хүсэлт олдсонгүй."))
        if not (note or "").strip():
            raise UserError(_("Татгалзах шалтгааныг бичнэ үү."))
        rec.write({"review_note": note})
        rec.action_reject()
        return True

    @api.model
    def get_request(self, request_id):
        if not self._studio_can_open():
            raise AccessError(_("Энэ хэсгийг харах эрх байхгүй."))
        rec = self.env[GRADE_MODEL].browse(int(request_id)).exists()
        if not rec:
            raise UserError(_("Хүсэлт олдсонгүй."))
        rec.check_access("read")
        fresh = self._freshness(rec)
        data = self._row(rec, fresh)
        is_registrar = self.env.su or self.env.user.has_group(REGISTRAR_GROUP)
        data.update({
            "reason": rec.reason or "",
            "evidence_ref": rec.evidence_ref or "",
            "evidence_count": self.env["ir.attachment"].search_count(
                [("res_model", "=", GRADE_MODEL), ("res_id", "=", rec.id)]),
            "review_note": (rec.review_note or "") if is_registrar else "",
            "history": self._history(rec),
            "isms": self._isms_entries(rec),
        })
        return data

    # --------------------------------------------------------------- helpers
    @api.model
    def _studio_can_open(self):
        return self.env.su or any(self.env.user.has_group(group) for group in STAFF_GROUPS)

    def _freshness(self, rec):
        """Compare the snapshot taken at request time with the live enrollment."""
        try:
            enrollment = rec.enrollment_id
            current_score = enrollment.score
            current_revision = enrollment.grade_revision
        except AccessError:
            return {"visible": False, "current_score": None, "current_revision": None,
                    "stale": True, "reasons": ["unreadable"]}
        reasons = []
        if current_revision != rec.old_revision:
            reasons.append("revision")
        if float_compare(current_score, rec.old_score, precision_digits=2):
            reasons.append("score")
        return {"visible": True, "current_score": current_score,
                "current_revision": current_revision,
                "stale": bool(reasons), "reasons": reasons}

    def _may(self, rec, operation):
        try:
            rec.check_access(operation)
        except AccessError:
            return False
        return True

    def _actions(self, rec, fresh):
        """Informational verdicts mirroring the checks in campus.grade.change."""
        user = self.env.user
        is_registrar = user.has_group(REGISTRAR_GROUP)
        is_requester = rec.requester_id == user
        writable = self._may(rec, "write")

        def verdict(ok, why=""):
            return {"allowed": bool(ok), "reason": "" if ok else why}

        if rec.state != "draft":
            submit = verdict(False, _("Зөвхөн ноорог хүсэлтийг хянуулахаар илгээнэ."))
        elif not is_requester:
            submit = verdict(False, _("Зөвхөн хүсэлт гаргагч хүсэлтээ илгээнэ."))
        elif not writable:
            submit = verdict(False, _("Энэ хүсэлтийг илгээх эрх байхгүй."))
        elif not float_compare(rec.old_score, rec.proposed_score, precision_digits=2):
            submit = verdict(False, _("Шинэ дүн хуучин дүнтэй ижил байна."))
        else:
            submit = verdict(True)

        if not is_registrar:
            approve = verdict(False, _("Батлах эрх зөвхөн сургалтын албанд байна."))
        elif rec.state != "submitted":
            approve = verdict(False, _("Хянуулахаар илгээгдээгүй хүсэлтийг батлахгүй."))
        elif is_requester:
            approve = verdict(False, _("Хүсэлт гаргагч өөрийн хүсэлтийг батлахгүй."))
        elif not writable:
            approve = verdict(False, _("Энэ хүсэлтийг батлах эрх байхгүй."))
        elif fresh["stale"]:
            approve = verdict(False, _("Дүн эсвэл хувилбар өөрчлөгдсөн тул хүсэлт хуучирсан. Шинэ хүсэлт гаргана уу."))
        else:
            approve = verdict(True)

        if not is_registrar:
            reject = verdict(False, _("Татгалзах эрх зөвхөн сургалтын албанд байна."))
        elif rec.state != "submitted":
            reject = verdict(False, _("Хянуулахаар илгээгдээгүй хүсэлтийг татгалзахгүй."))
        elif is_requester:
            reject = verdict(False, _("Хүсэлт гаргагч өөрийн хүсэлтийг татгалзахгүй."))
        elif not writable:
            reject = verdict(False, _("Энэ хүсэлтийг татгалзах эрх байхгүй."))
        else:
            reject = verdict(True)
        reject["requires_note"] = True
        return {"submit": submit, "approve": approve, "reject": reject}

    def _row(self, rec, fresh):
        offering = rec.offering_id
        state_labels = dict(rec._fields["state"]._description_selection(self.env))
        return {
            "id": rec.id,
            "name": rec.name or "",
            "state": rec.state,
            "state_label": state_labels.get(rec.state, rec.state),
            "student": {"id": rec.student_id.id, "name": rec.student_id.name or "",
                        "code": rec.student_id.student_code or ""},
            "offering": {"id": offering.id, "name": offering.name or "",
                         "semester": offering.semester or "",
                         "course": offering.course_id.name or "",
                         "lecturer": offering.lecturer_id.name or ""},
            "requester": {"id": rec.requester_id.id, "name": rec.requester_id.name or ""},
            "approver": ({"id": rec.approver_id.id, "name": rec.approver_id.name or ""}
                         if rec.approver_id else None),
            "old_score": rec.old_score,
            "proposed_score": rec.proposed_score,
            "delta": round(rec.proposed_score - rec.old_score, 2),
            "old_revision": rec.old_revision,
            "current_revision": fresh["current_revision"],
            "current_score": fresh["current_score"],
            "enrollment_visible": fresh["visible"],
            "stale": fresh["stale"],
            "stale_reasons": fresh["reasons"],
            "submitted_at": fields.Datetime.to_string(rec.submitted_at) if rec.submitted_at else False,
            "approved_at": fields.Datetime.to_string(rec.approved_at) if rec.approved_at else False,
            "created_at": fields.Datetime.to_string(rec.create_date) if rec.create_date else False,
            "actions": self._actions(rec, fresh),
        }

    def _history(self, rec):
        messages = self.env["mail.message"].search(
            [("model", "=", GRADE_MODEL), ("res_id", "=", rec.id)],
            order="date asc, id asc", limit=HISTORY_LIMIT)
        entries = []
        for msg in messages:
            author = msg.author_id.name or ""
            date = fields.Datetime.to_string(msg.date) if msg.date else False
            for value in msg.tracking_value_ids:
                # Field metadata (ir.model.fields) is not readable by campus roles, so it is
                # looked up with sudo for the label and type only. Old/new values are read
                # with the caller's own rights, and only for fields without a group restriction
                # (the same rule mail uses for tracking summaries).
                field_meta = value.sudo().field_id
                if not field_meta or not self._tracked_field_is_public(field_meta):
                    continue
                is_float = field_meta.ttype in ("float", "monetary")
                entries.append({
                    "type": "tracking", "date": date, "author": author,
                    "field": field_meta.field_description or "",
                    "old": value.old_value_float if is_float else (value.old_value_char or ""),
                    "new": value.new_value_float if is_float else (value.new_value_char or ""),
                })
            if msg.message_type == "comment" and msg.body:
                text = html2plaintext(msg.body or "").strip()
                if text:
                    entries.append({"type": "note", "date": date, "author": author,
                                    "text": text[:2000]})
        return entries

    def _tracked_field_is_public(self, field_meta):
        model = self.env.get(field_meta.model)
        model_field = model._fields.get(field_meta.name) if model is not None else None
        return bool(model_field) and not model_field.groups

    def _isms_entries(self, rec):
        log_model = self.env["isms.audit.log"]
        if not log_model.check_access_rights("read", raise_exception=False):
            return {"visible": False, "entries": []}
        domain = ["|",
                  "&", ("model", "=", GRADE_MODEL), ("res_id", "=", rec.id),
                  "&", ("model", "=", ENROLLMENT_MODEL), ("res_id", "=", rec.enrollment_id.id)]
        logs = log_model.search(domain, order="timestamp desc, id desc", limit=ISMS_LOG_LIMIT)
        entries = [{
            "timestamp": fields.Datetime.to_string(log.timestamp) if log.timestamp else False,
            "user": log.user_id.name or log.login or "",
            "action": log.action,
            "model": log.model_name or log.model or "",
            "changes": log.changes or "",
        } for log in logs]
        return {"visible": True, "entries": entries}
