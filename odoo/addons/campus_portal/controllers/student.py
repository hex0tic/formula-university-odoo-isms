# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
from odoo import _, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import content_disposition, request

from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.campus_portal_common import user_error_text

SERVICE = "campus.portal.student"
REPORT_TRANSCRIPT = "campus_academic_plus.action_report_transcript"


class CampusPortalStudent(CustomerPortal):
    """Student self-service pages under /my/campus.

    Every route is auth='user'. POST routes keep Odoo's CSRF check (csrf=True is the default for
    http POST). No route accepts a student id: the student is always the current user's own
    campus.student, and record ids in URLs are checked against that student's own records.
    """

    # ------------------------------------------------------------ home tile
    @http.route()
    def home(self, **kw):
        response = super().home(**kw)
        if response.is_qweb:
            # /my/counters must only return keys with a counter element.
            response.qcontext["campus_has_student"] = bool(request.env[SERVICE]._own_student())
        return response

    # ------------------------------------------------------------ rendering helpers
    def _campus_render(self, template, page, **values):
        values.update(self._prepare_portal_layout_values())
        values.setdefault("overview", False)
        values.update({
            "page_name": "campus",
            "campus_page": page,
            "campus_flash": request.session.pop("campus_flash", None),
        })
        return request.render(template, values)

    @staticmethod
    def _flash(kind, text):
        request.session["campus_flash"] = {"type": kind, "text": text}

    # ------------------------------------------------------------ pages
    @http.route(["/my/campus"], type="http", auth="user", website=True)
    def campus_overview(self, **kw):
        overview = request.env[SERVICE].get_overview()
        return self._campus_render("campus_portal.page_overview", "overview", overview=overview)

    @http.route(["/my/campus/grades"], type="http", auth="user", website=True)
    def campus_grades(self, **kw):
        rows = request.env[SERVICE].get_enrollments()
        return self._campus_render("campus_portal.page_grades", "grades", rows=rows,
                                   has_student=bool(request.env[SERVICE]._own_student()))

    @http.route(["/my/campus/schedule"], type="http", auth="user", website=True)
    def campus_schedule(self, week=None, **kw):
        data = request.env[SERVICE].get_schedule(week)
        return self._campus_render("campus_portal.page_schedule", "schedule", data=data,
                                   has_student=bool(request.env[SERVICE]._own_student()))

    @http.route(["/my/campus/attendance"], type="http", auth="user", website=True)
    def campus_attendance(self, **kw):
        rows = request.env[SERVICE].get_attendance()
        return self._campus_render("campus_portal.page_attendance", "attendance", rows=rows,
                                   has_student=bool(request.env[SERVICE]._own_student()))

    @http.route(["/my/campus/register"], type="http", auth="user", website=True)
    def campus_register(self, **kw):
        catalog = request.env[SERVICE].get_registration_catalog()
        return self._campus_render("campus_portal.page_register", "register", catalog=catalog)

    @http.route(["/my/campus/requests"], type="http", auth="user", website=True)
    def campus_requests(self, **kw):
        rows = request.env[SERVICE].get_requests()
        return self._campus_render("campus_portal.page_requests", "requests", rows=rows,
                                   has_student=bool(request.env[SERVICE]._own_student()))

    @http.route(["/my/campus/notifications"], type="http", auth="user", website=True)
    def campus_notifications(self, **kw):
        rows = request.env[SERVICE].get_notifications()
        return self._campus_render("campus_portal.page_notifications", "notifications", rows=rows,
                                   has_student=bool(request.env[SERVICE]._own_student()))

    # ------------------------------------------------------------ actions (POST, CSRF protected)
    @http.route(["/my/campus/register/<int:offering_id>"], type="http", auth="user",
                methods=["POST"], website=True)
    def campus_register_post(self, offering_id, **post):
        try:
            result = request.env[SERVICE].register_offering(offering_id)
            self._flash("success", _("%s хичээлд бүртгүүллээ.", result.get("offering", "")))
        except (AccessError, UserError, ValidationError) as error:
            self._flash("danger", user_error_text(error))
        return request.redirect("/my/campus/register")

    @http.route(["/my/campus/drop/<int:enrollment_id>"], type="http", auth="user",
                methods=["POST"], website=True)
    def campus_drop_post(self, enrollment_id, **post):
        student = request.env[SERVICE]._own_student()
        if not student:
            return request.not_found()
        # Ownership is re-checked inside drop_own_enrollment; an id that is not one of the
        # current student's enrollments returns 404 without revealing whether it exists.
        owned = request.env[SERVICE]._own_enrollments(student).filtered(lambda e: e.id == enrollment_id)
        if not owned:
            return request.not_found()
        try:
            request.env[SERVICE].drop_own_enrollment(enrollment_id)
            self._flash("success", _("Хичээлийн бүртгэлийг хаслаа."))
        except (AccessError, UserError, ValidationError) as error:
            self._flash("danger", user_error_text(error))
        return request.redirect("/my/campus/grades")

    # ------------------------------------------------------------ transcript (own only)
    @http.route(["/my/campus/transcript.pdf"], type="http", auth="user", website=True)
    def campus_transcript(self, **kw):
        student = request.env[SERVICE]._own_student()
        if not student:
            return request.not_found()
        # The academic transcript report runs in the user environment; the student id comes from the
        # ownership lookup, never from the request. The report reads only rows the user may read.
        pdf, _fmt = request.env["ir.actions.report"]._render_qweb_pdf(
            REPORT_TRANSCRIPT, res_ids=[student.id])
        filename = "transcript-%s.pdf" % (student.student_code or student.id)
        return request.make_response(pdf, headers=[
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", content_disposition(filename)),
            ("Content-Length", len(pdf)),
            ("Cache-Control", "no-store"),
        ])
