# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
"""Lecturer portal service layer for the website and backend Owl client action.

Every method runs in the caller's own environment (no sudo). Record rules already limit
offerings, enrollments and grade requests to the lecturer's own teaching assignments; the
methods also check ownership explicitly so the result never depends on a rule alone.
Grade changes are created and submitted only through campus.grade.change; the enrollment
score is never written here.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import html2plaintext

from .campus_portal_common import ATTENDANCE_LABELS, ATTENDANCE_STATUSES, MAX_ROWS, open_term, selection_label

LECTURER_GROUP = "campus_university.group_campus_lecturer"


class CampusPortalTeacher(models.AbstractModel):
    _name = "campus.portal.teacher"
    _description = "Багшийн портал"

    @api.model
    def _require_lecturer(self):
        if not self.env.user.has_group(LECTURER_GROUP):
            raise AccessError(_("Зөвхөн сургалтын багш энэ хэсгийг ашиглана."))

    @api.model
    def _own_offering(self, offering_id):
        """Offering the current lecturer teaches, or AccessError. Never returns another lecturer's record."""
        self._require_lecturer()
        offering = self.env["campus.offering"].search(
            [("id", "=", offering_id), ("lecturer_id", "=", self.env.uid)], limit=1)
        if not offering:
            raise AccessError(_("Энэ хичээл танд хамаарахгүй."))
        return offering

    @api.model
    def _own_session(self, session_id):
        self._require_lecturer()
        session = self.env["campus.session"].search([("id", "=", session_id)], limit=1)
        if not session or session.offering_id.lecturer_id != self.env.user:
            raise AccessError(_("Энэ хичээлийн цагт ирц бүртгэх эрхгүй."))
        return session

    def _own_enrollment(self, enrollment_id):
        self._require_lecturer()
        enrollment = self.env["campus.enrollment"].search([("id", "=", enrollment_id)], limit=1)
        if not enrollment or enrollment.offering_id.lecturer_id != self.env.user:
            raise AccessError(_("Зөвхөн өөрийн заадаг хичээлийн дүнд хүсэлт гаргана."))
        return enrollment

    def _local_text(self, value):
        if not value:
            return ""
        return fields.Datetime.context_timestamp(self, value).strftime("%Y-%m-%d %H:%M")

    # ------------------------------------------------------------ dashboard
    @api.model
    def get_dashboard(self):
        self._require_lecturer()
        term = open_term(self.env)
        domain = [("lecturer_id", "=", self.env.uid)]
        if term:
            domain.append(("term_id", "=", term.id))
        offerings = self.env["campus.offering"].search(domain, order="name", limit=MAX_ROWS)
        pending = self.env["campus.grade.change"].search_count(
            [("requester_id", "=", self.env.uid), ("state", "=", "submitted")])
        return {
            "lecturer": self.env.user.name,
            "term": {"id": term.id, "name": term.name} if term else False,
            "pending_count": pending,
            "offerings": [{
                "id": offering.id,
                "name": offering.name,
                "course_code": offering.course_id.code,
                "semester": offering.semester,
                "state": offering.state,
                "state_label": selection_label(offering, "state"),
                "seats_taken": offering.seats_taken,
                "capacity": offering.capacity,
            } for offering in offerings],
        }

    # ------------------------------------------------------------ roster
    @api.model
    def get_roster(self, offering_id):
        offering = self._own_offering(offering_id)
        enrollments = offering.enrollment_ids.sorted(lambda e: e.student_id.name or "")[:MAX_ROWS]
        requests = self.env["campus.grade.change"].search([
            ("enrollment_id", "in", enrollments.ids),
            ("requester_id", "=", self.env.uid),
        ], order="create_date desc, id desc")
        latest = {}
        for change in requests:
            latest.setdefault(change.enrollment_id.id, change)
        return {
            "offering": {"id": offering.id, "name": offering.name, "state": offering.state},
            "rows": [{
                "enrollment_id": enrollment.id,
                "student_code": enrollment.student_id.student_code,
                "student_name": enrollment.student_id.name,
                "reg_state": enrollment.reg_state,
                "reg_state_label": selection_label(enrollment, "reg_state"),
                "score": enrollment.score,
                "grade_revision": enrollment.grade_revision,
                "request_id": latest[enrollment.id].id if enrollment.id in latest else False,
                "request_name": latest[enrollment.id].name if enrollment.id in latest else "",
                "request_state": latest[enrollment.id].state if enrollment.id in latest else "",
                "request_state_label": selection_label(latest[enrollment.id], "state")
                if enrollment.id in latest else "",
            } for enrollment in enrollments],
        }

    # ------------------------------------------------------------ attendance
    def _sessions(self, offering):
        return self.env["campus.session"].search(
            [("offering_id", "=", offering.id)], order="start, id", limit=MAX_ROWS)

    def _session_summary(self, session):
        return {
            "id": session.id,
            "start": self._local_text(session.start),
            "end": self._local_text(session.end),
            "room": session.room or "",
            "kind": selection_label(session, "kind"),
        }

    def _attendance_rows(self, session, enrollments, statuses):
        return [{
            "enrollment_id": enrollment.id,
            "student_code": enrollment.student_id.student_code,
            "student_name": enrollment.student_id.name,
            "status": statuses.get((session.id, enrollment.id), "present"),
            "recorded": (session.id, enrollment.id) in statuses,
        } for enrollment in enrollments]

    def _attendance_statuses(self):
        return [{"key": key, "label": ATTENDANCE_LABELS[key]} for key in ATTENDANCE_STATUSES]

    def _attendance_enrollments(self, offering):
        return offering.enrollment_ids.filtered(lambda e: e.reg_state == "enrolled").sorted(
            lambda e: e.student_id.name or "")

    def _session_list(self, offering_id):
        offering = self._own_offering(offering_id)
        return [self._session_summary(session) for session in self._sessions(offering)]

    def _attendance_sheet(self, session_id):
        session = self._own_session(session_id)
        offering = session.offering_id
        enrollments = self._attendance_enrollments(offering)
        records = self.env["campus.attendance"].search([
            ("session_id", "=", session.id), ("enrollment_id", "in", enrollments.ids),
        ])
        statuses = {(record.session_id.id, record.enrollment_id.id): record.status for record in records}
        return {
            "offering": {"id": offering.id, "name": offering.name},
            "session": self._session_summary(session),
            "rows": self._attendance_rows(session, enrollments, statuses),
            "statuses": self._attendance_statuses(),
        }

    @api.model
    def get_sessions(self, offering_id):
        offering = self._own_offering(offering_id)
        sessions = self._sessions(offering)
        records = self.env["campus.attendance"].search(
            [("session_id", "in", sessions.ids)], limit=MAX_ROWS * 50)
        statuses = {(record.session_id.id, record.enrollment_id.id): record.status for record in records}
        enrollments = self._attendance_enrollments(offering)
        return {
            "sessions": [dict(self._session_summary(session),
                              rows=self._attendance_rows(session, enrollments, statuses))
                         for session in sessions],
            "statuses": self._attendance_statuses(),
        }

    @api.model
    def save_attendance(self, session_id, rows):
        """Record attendance for one of the lecturer's own sessions.

        ``rows`` is a list of ``{"enrollment_id": int, "status": str}``. Enrollment ids must belong
        to the session's offering; statuses must be one of ATTENDANCE_STATUSES.
        """
        session = self._own_session(session_id)
        valid = set(session.offering_id.enrollment_ids.ids)
        clean = []
        for row in rows or []:
            enrollment_id = int(row.get("enrollment_id", 0))
            status = row.get("status")
            if enrollment_id not in valid:
                raise AccessError(_("Оюутны бүртгэл энэ хичээлд хамаарахгүй."))
            if status not in ATTENDANCE_STATUSES:
                raise ValidationError(_("Ирцийн төлөв буруу байна."))
            clean.append({"enrollment_id": enrollment_id, "status": status})
        if not clean:
            raise UserError(_("Ирц бүртгэх оюутан алга."))
        Attendance = self.env["campus.attendance"]
        for row in clean:
            enrollment = self.env["campus.enrollment"].browse(row["enrollment_id"])
            # campus.attendance.record runs the lecturer/registrar and offering checks in this environment.
            Attendance.record(session, enrollment, row["status"])
        return {"session_id": session.id, "saved": len(clean)}

    # ------------------------------------------------------------ grade entry
    def _grade_request_details(self, enrollment_id):
        enrollment = self._own_enrollment(enrollment_id)
        return {
            "id": enrollment.id,
            "offering_id": enrollment.offering_id.id,
            "offering": enrollment.offering_id.name,
            "student": enrollment.student_id.name,
            "student_code": enrollment.student_id.student_code,
            "score": enrollment.score,
        }

    @api.model
    def request_grade_change(self, enrollment_id, proposed_score, reason, evidence_ref=False):
        """Create and submit a grade-change request. The registrar approves; the score stays unchanged."""
        enrollment = self._own_enrollment(enrollment_id)
        try:
            score = float(proposed_score)
        except (TypeError, ValueError):
            raise ValidationError(_("Шинэ дүн тоо байх ёстой."))
        if not 0 <= score <= 100:
            raise ValidationError(_("Шинэ дүн 0–100 байна."))
        change = self.env["campus.grade.change"].create({
            "enrollment_id": enrollment.id,
            "proposed_score": score,
            "reason": (reason or "").strip(),
            "evidence_ref": (evidence_ref or "").strip() or False,
        })
        change.action_submit()
        return {"id": change.id, "name": change.name, "state": change.state,
                "state_label": selection_label(change, "state")}

    # ------------------------------------------------------------ notifications
    @api.model
    def get_notifications(self, limit=30):
        self._require_lecturer()
        offering_ids = self.env["campus.offering"].search([("lecturer_id", "=", self.env.uid)]).ids
        request_ids = self.env["campus.grade.change"].search([("requester_id", "=", self.env.uid)]).ids
        clauses = [[("model", "=", "campus.offering"), ("res_id", "in", offering_ids)]] if offering_ids else []
        if request_ids:
            clauses.append([("model", "=", "campus.grade.change"), ("res_id", "in", request_ids)])
        if not clauses:
            return []
        domain = expression.AND([
            expression.OR(clauses),
            [("message_type", "in", ("comment", "notification")), ("is_internal", "=", False)],
        ])
        messages = self.env["mail.message"].search(domain, order="date desc, id desc",
                                                   limit=max(1, min(int(limit), 100)))
        return [{
            "id": message.id,
            "date": self._local_text(message.date),
            "source": message.model,
            "subject": message.subject or "",
            "body": html2plaintext(message.body or "").strip()[:500],
        } for message in messages]
