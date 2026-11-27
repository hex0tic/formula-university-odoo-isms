# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
"""Student self-service service layer.

Ownership model
---------------
* Every read runs in the caller's own environment (no sudo). The campus record rules
  (campus_university and campus_academic_plus) restrict students to their own student,
  enrollments, attendance, grade requests, and sessions of enrolled offerings.
* The only student lookup is ``campus.student`` with ``user_id = current uid``. Users
  without the Campus Student group get no student. Campus Student is a portal role.
* Nothing is trusted from the URL or from a client-supplied student id.
* State changes (registration, drop) call the academic model methods
  (``campus.offering.register_student``, ``campus.enrollment.action_drop``) in the user
  environment. Those methods enforce the academic rules server-side and must not be called
  through sudo, because ``is_registrar()`` treats sudo as a registrar.
"""
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.osv import expression
from odoo.tools import html2plaintext

from .campus_portal_common import (
    MAX_ROWS, in_window, local_date, local_time_label, open_term, parse_date,
    selection_label, week_monday,
)

COMPLETED = "completed"


def _drop_open(today, term):
    """Add/drop closes on the term's add_drop_end date (inclusive)."""
    return bool(term) and bool(term.add_drop_end) and today <= term.add_drop_end


class CampusPortalStudent(models.AbstractModel):
    _name = "campus.portal.student"
    _description = "Оюутны өөрийн мэдээллийн портал"

    # ------------------------------------------------------------ ownership
    @api.model
    def _own_student(self):
        """campus.student of the current user (user environment), or an empty recordset."""
        user = self.env.user
        if user._is_public() or not user.has_group("campus_university.group_campus_student"):
            return self.env["campus.student"]
        return self.env["campus.student"].search(
            [("user_id", "=", user.id), ("active", "=", True)], limit=1)

    @api.model
    def _own_enrollments(self, student):
        """Enrollments of the given student, read in the user environment (rules apply)."""
        if not student:
            return self.env["campus.enrollment"]
        return self.env["campus.enrollment"].search(
            [("student_id", "=", student.id)], order="offering_id")

    def _session_rows(self, offering_ids, extra_domain, limit=None):
        if not offering_ids:
            return self.env["campus.session"]
        return self.env["campus.session"].search(
            [("offering_id", "in", offering_ids)] + extra_domain,
            order="start, id", limit=limit,
        )

    def _session_card(self, session):
        return {
            "date": local_date(self, session.start).isoformat(),
            "start": local_time_label(self, session.start),
            "end": local_time_label(self, session.end) if session.end else "",
            "course_code": session.offering_id.course_id.code,
            "title": session.offering_id.course_id.name,
            "room": session.room or "",
            "kind": selection_label(session, "kind"),
        }

    def _student_agenda(self, enrolled):
        now = fields.Datetime.now()
        today = local_date(self, now)
        offering_ids = enrolled.mapped("offering_id").ids
        # Pad the UTC query for all timezones, then compare exact local calendar dates.
        start = datetime.combine(today - timedelta(days=1), time.min)
        end = datetime.combine(today + timedelta(days=2), time.min)
        sessions = self._session_rows(offering_ids, [("start", ">=", start), ("start", "<", end)])
        todays_sessions = sessions.filtered(lambda session: local_date(self, session.start) == today)
        next_session = self._session_rows(offering_ids, [("start", ">=", now)], limit=1)
        return {
            "today": today.isoformat(),
            "today_count": len(todays_sessions),
            "today_sessions": [self._session_card(session) for session in todays_sessions[:3]],
            "next_session": self._session_card(next_session) if next_session else False,
        }

    # ------------------------------------------------------------ overview
    @api.model
    def get_overview(self):
        student = self._own_student()
        if not student:
            return {"has_student": False}
        missing = student.graduation_missing
        if isinstance(missing, str):
            missing = [line.strip() for line in missing.splitlines() if line.strip()]
        enrollments = self._own_enrollments(student)
        enrolled = enrollments.filtered(lambda e: e.reg_state == "enrolled")
        completed = enrollments.filtered(lambda e: e.reg_state == COMPLETED)
        pending_count = self.env["campus.grade.change"].search_count([
            ("enrollment_id", "in", enrollments.ids), ("state", "=", "submitted"),
        ]) if enrollments else 0
        return {
            "has_student": True,
            "student": {
                "name": student.name,
                "code": student.student_code,
                "program": student.program_id.name,
                "status": selection_label(student, "status"),
            },
            "gpa": student.gpa,
            "credits_earned": student.credits_earned,
            "graduation_eligible": bool(student.graduation_eligible),
            "graduation_missing": list(missing or []),
            "enrolled_count": len(enrolled),
            "completed_count": len(completed),
            "transcript_ready": bool(completed),
            "pending_count": pending_count,
            "agenda": self._student_agenda(enrolled),
        }

    # ------------------------------------------------------------ enrollments
    @api.model
    def get_enrollments(self):
        student = self._own_student()
        today = fields.Date.context_today(self)
        rows = []
        for enrollment in self._own_enrollments(student)[:MAX_ROWS]:
            offering = enrollment.offering_id
            term = offering.term_id
            completed = enrollment.reg_state == COMPLETED
            rows.append({
                "id": enrollment.id,
                "offering": offering.name,
                "course_code": offering.course_id.code,
                "course": offering.course_id.name,
                "credits": offering.course_id.credits,
                "term": term.name if term else "",
                "reg_state": enrollment.reg_state,
                "reg_state_label": selection_label(enrollment, "reg_state"),
                # Score is shown once it is approved (completed) or non-zero; letter and grade point only when completed.
                "score": enrollment.score if (completed or enrollment.score) else False,
                "letter_grade": enrollment.letter_grade if completed else False,
                "grade_point": enrollment.grade_point if completed else False,
                "can_drop": enrollment.reg_state == "enrolled" and _drop_open(today, term),
            })
        return rows

    # ------------------------------------------------------------ schedule
    @api.model
    def get_schedule(self, week_start=None):
        """Week view: sessions of the student's enrolled offerings, grouped by local day."""
        today = fields.Date.context_today(self)
        start_day = week_monday(parse_date(week_start) or today)
        end_day = start_day + timedelta(days=6)
        days = [{
            "date": (start_day + timedelta(days=i)).isoformat(),
            "label": (start_day + timedelta(days=i)).strftime("%d.%m"),
            "is_today": start_day + timedelta(days=i) == today,
            "sessions": [],
        } for i in range(7)]
        result = {
            "week_start": start_day.isoformat(),
            "week_end": end_day.isoformat(),
            "is_current_week": start_day == week_monday(today),
            "prev_week": (start_day - timedelta(days=7)).isoformat(),
            "next_week": (start_day + timedelta(days=7)).isoformat(),
            "days": days,
        }
        student = self._own_student()
        if not student:
            return result
        offering_ids = self._own_enrollments(student).filtered(
            lambda e: e.reg_state == "enrolled").mapped("offering_id").ids
        # UTC window padded by one day on each side; the exact local-date filter follows.
        lo = datetime.combine(start_day - timedelta(days=1), time.min)
        hi = datetime.combine(end_day + timedelta(days=2), time.min)
        sessions = self._session_rows(offering_ids, [
            ("start", ">=", lo),
            ("start", "<", hi),
        ], limit=MAX_ROWS)
        for session in sessions:
            day = local_date(self, session.start)
            if day < start_day or day > end_day:
                continue
            days[(day - start_day).days]["sessions"].append(self._session_card(session))
        return result

    # ------------------------------------------------------------ attendance
    @api.model
    def get_attendance(self):
        enrollments = self._own_enrollments(self._own_student())
        if not enrollments:
            return []
        records = self.env["campus.attendance"].search([("enrollment_id", "in", enrollments.ids)])
        counts = {}
        for record in records:
            bucket = counts.setdefault(record.enrollment_id.id, {"present": 0, "absent": 0, "late": 0, "excused": 0})
            if record.status in bucket:
                bucket[record.status] += 1
        rows = []
        for enrollment in enrollments[:MAX_ROWS]:
            bucket = counts.get(enrollment.id, {"present": 0, "absent": 0, "late": 0, "excused": 0})
            total = sum(bucket.values())
            attended = bucket["present"] + bucket["late"]
            rows.append({
                "offering": enrollment.offering_id.name,
                "course_code": enrollment.offering_id.course_id.code,
                "total": total,
                "present": bucket["present"],
                "late": bucket["late"],
                "absent": bucket["absent"],
                "excused": bucket["excused"],
                "rate": round(100.0 * attended / total, 1) if total else False,
            })
        return rows

    # ------------------------------------------------------------ registration
    @api.model
    def get_registration_catalog(self):
        """Open offerings of the open term (readable by students through rule_offering_open_student)."""
        student = self._own_student()
        result = {"has_student": bool(student), "term": False, "window_open": False, "offerings": []}
        if not student:
            return result
        term = open_term(self.env)
        if not term:
            return result
        today = fields.Date.context_today(self)
        window_open = in_window(today, term.registration_start, term.registration_end)
        result["term"] = {
            "id": term.id,
            "name": term.name,
            "registration_end": fields.Date.to_string(term.registration_end) if term.registration_end else "",
        }
        result["window_open"] = window_open
        taken = set(self._own_enrollments(student).filtered(
            lambda e: e.reg_state in ("enrolled", COMPLETED)).mapped("offering_id").ids)
        offerings = self.env["campus.offering"].search(
            [("term_id", "=", term.id), ("state", "=", "open")], order="name", limit=MAX_ROWS)
        for offering in offerings:
            registered = offering.id in taken
            result["offerings"].append({
                "id": offering.id,
                "name": offering.name,
                "course_code": offering.course_id.code,
                "course": offering.course_id.name,
                "credits": offering.course_id.credits,
                "lecturer": offering.lecturer_id.name,
                "capacity": offering.capacity,
                "seats_left": offering.seats_left,
                "registered": registered,
                "can_register": bool(window_open and not registered and offering.seats_left > 0),
            })
        return result

    @api.model
    def register_offering(self, offering_id):
        """Register the current user's own student record for an open offering.

        ``campus.offering.register_student`` enforces ownership, capacity, prerequisites, the
        credit limit and the schedule clash rule. This method adds the open-term and
        registration-window checks shown in the catalogue, and runs in the user environment.
        """
        student = self._own_student()
        if not student:
            raise AccessError(_("Танд оюутны бүртгэл холбогдоогүй байна."))
        term = open_term(self.env)
        offering = self.env["campus.offering"].browse(offering_id).exists()
        if not offering:
            raise UserError(_("Хичээл олдсонгүй."))
        if not term or offering.term_id != term or offering.state != "open":
            raise UserError(_("Энэ хичээлд бүртгүүлэх боломжгүй байна."))
        today = fields.Date.context_today(self)
        if not in_window(today, term.registration_start, term.registration_end):
            raise UserError(_("Бүртгэлийн хугацаа дууссан эсвэл эхлээгүй байна."))
        enrollment = offering.register_student(student)
        return {"id": enrollment.id, "offering": offering.name}

    # ------------------------------------------------------------ drop
    @api.model
    def drop_own_enrollment(self, enrollment_id):
        """Drop an enrollment that belongs to the current student, inside the add/drop window."""
        student = self._own_student()
        enrollment = self._own_enrollments(student).filtered(lambda e: e.id == enrollment_id)
        if not enrollment:
            raise UserError(_("Бүртгэл олдсонгүй."))
        term = enrollment.offering_id.term_id
        if not _drop_open(fields.Date.context_today(self), term):
            raise UserError(_("Хичээл хасах хугацаа дууссан байна."))
        enrollment.action_drop()  # enforces ownership and the add/drop window again
        return {"id": enrollment.id, "reg_state": enrollment.reg_state}

    # ------------------------------------------------------------ requests
    @api.model
    def get_requests(self):
        """Grade-change decisions on the student's own enrollments (read-only for the student)."""
        enrollment_ids = self._own_enrollments(self._own_student()).ids
        if not enrollment_ids:
            return []
        changes = self.env["campus.grade.change"].search(
            [("enrollment_id", "in", enrollment_ids)], order="create_date desc", limit=MAX_ROWS)
        rows = []
        for change in changes:
            rows.append({
                "id": change.id,
                "name": change.name,
                "offering": change.offering_id.name,
                "state": change.state,
                "state_label": selection_label(change, "state"),
                "submitted_at": self._local_text(change.submitted_at),
                "decided_at": self._local_text(change.approved_at),
            })
        return rows

    # ------------------------------------------------------------ notifications
    @api.model
    def get_notifications(self, limit=30):
        """Mail messages on the student's own record, enrollments and grade requests."""
        student = self._own_student()
        if not student:
            return []
        enrollment_ids = self._own_enrollments(student).ids
        change_ids = []
        if enrollment_ids:
            change_ids = self.env["campus.grade.change"].search(
                [("enrollment_id", "in", enrollment_ids)]).ids
        clauses = [[("model", "=", "campus.student"), ("res_id", "=", student.id)]]
        if enrollment_ids:
            clauses.append([("model", "=", "campus.enrollment"), ("res_id", "in", enrollment_ids)])
        if change_ids:
            clauses.append([("model", "=", "campus.grade.change"), ("res_id", "in", change_ids)])
        domain = expression.AND([
            expression.OR(clauses),
            [("message_type", "in", ("comment", "notification")), ("is_internal", "=", False)],
        ])
        messages = self.env["mail.message"].search(
            domain, order="date desc, id desc", limit=max(1, min(int(limit), 100)))
        return [{
            "id": message.id,
            "date": self._local_text(message.date),
            "source": message.model,
            "subject": message.subject or "",
            "body": html2plaintext(message.body or "").strip()[:500],
        } for message in messages]

    @api.model
    def _local_text(self, value):
        if not value:
            return ""
        return fields.Datetime.context_timestamp(self, value).strftime("%Y-%m-%d %H:%M")
