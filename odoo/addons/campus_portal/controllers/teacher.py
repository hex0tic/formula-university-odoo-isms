# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from ..models.campus_portal_common import user_error_text
from ..models.portal_teacher import LECTURER_GROUP

ROOT = "/campus/teacher"
SERVICE = "campus.portal.teacher"
PRIVATE_HEADERS = [("Cache-Control", "private, no-store")]
FLASH_KEY = "campus_teacher_flash"


class CampusPortalTeacher(http.Controller):
    def _account_required(self):
        if not request.env.user.has_group(LECTURER_GROUP):
            return request.render("campus_portal.teacher_account_required", status=403, headers=PRIVATE_HEADERS)

    def _page(self, template, page, status=200, error=None, **values):
        return request.render(f"campus_portal.{template}", {
            "teacher_page": page,
            "teacher_flash": request.session.pop(FLASH_KEY, None),
            "teacher_error": error,
            **values,
        }, status=status, headers=PRIVATE_HEADERS)

    @http.route(ROOT, type="http", auth="user", website=True, methods=["GET"])
    def teacher_dashboard(self, **kw):
        if (denied := self._account_required()) is not None:
            return denied
        dashboard = request.env[SERVICE].get_dashboard()
        return self._page("teacher_dashboard", "dashboard", dashboard=dashboard,
                          seat_count=sum(item["seats_taken"] for item in dashboard["offerings"]))

    @http.route(ROOT + "/offerings/<int:offering_id>", type="http", auth="user", website=True, methods=["GET"])
    def teacher_offering(self, offering_id, **kw):
        if (denied := self._account_required()) is not None:
            return denied
        service = request.env[SERVICE]
        try:
            roster = service.get_roster(offering_id)
            sessions = service._session_list(offering_id)
        except AccessError:
            return request.not_found()
        return self._page("teacher_offering", "offering", roster=roster, sessions=sessions)

    @http.route(ROOT + "/notifications", type="http", auth="user", website=True, methods=["GET"])
    def teacher_notifications(self, **kw):
        if (denied := self._account_required()) is not None:
            return denied
        return self._page("teacher_notifications", "notifications",
                          notifications=request.env[SERVICE].get_notifications())

    @http.route(ROOT + "/sessions/<int:session_id>", type="http", auth="user", website=True,
                methods=["GET", "POST"], csrf=True)
    def teacher_attendance(self, session_id, **kw):
        if (denied := self._account_required()) is not None:
            return denied
        service = request.env[SERVICE]
        try:
            sheet = service._attendance_sheet(session_id)
        except AccessError:
            return request.not_found()
        if request.httprequest.method == "GET":
            return self._page("teacher_attendance", "attendance", sheet=sheet)

        fields = [(key, value) for key, value in request.httprequest.form.items(multi=True)
                  if key.startswith("attendance_")]
        submitted = dict(fields)
        expected = {f"attendance_{row['enrollment_id']}" for row in sheet["rows"]}
        try:
            if len(fields) != len(submitted) or submitted.keys() != expected:
                raise UserError(_("Оюутны жагсаалтыг шалгаад ирцээ дахин хадгална уу."))
            rows = [{"enrollment_id": row["enrollment_id"], "status": submitted[f"attendance_{row['enrollment_id']}"]}
                    for row in sheet["rows"]]
            with request.env.cr.savepoint():
                service.save_attendance(session_id, rows)
        except AccessError:
            return request.not_found()
        except UserError as error:
            allowed = {status["key"] for status in sheet["statuses"]}
            for row in sheet["rows"]:
                selection = submitted.get(f"attendance_{row['enrollment_id']}")
                if selection in allowed:
                    row["status"] = selection
            return self._page("teacher_attendance", "attendance", status=400, sheet=sheet,
                              error=user_error_text(error))
        request.session[FLASH_KEY] = _("Ирцийг хадгаллаа.")
        return request.redirect(f"{ROOT}/sessions/{session_id}", code=303)

    @http.route(ROOT + "/grades/<int:enrollment_id>", type="http", auth="user", website=True,
                methods=["GET", "POST"], csrf=True)
    def teacher_grade_request(self, enrollment_id, **kw):
        if (denied := self._account_required()) is not None:
            return denied
        service = request.env[SERVICE]
        try:
            enrollment = service._grade_request_details(enrollment_id)
        except AccessError:
            return request.not_found()
        if request.httprequest.method == "GET":
            return self._page("teacher_grade_request", "grade", enrollment=enrollment, form={})

        form = {key: request.httprequest.form.get(key, "") for key in ("score", "reason", "evidence")}
        try:
            # A failed submission must roll back the draft created by the service.
            with request.env.cr.savepoint():
                result = service.request_grade_change(enrollment_id, form["score"], form["reason"], form["evidence"])
        except AccessError:
            return request.not_found()
        except UserError as error:
            return self._page("teacher_grade_request", "grade", status=400, enrollment=enrollment, form=form,
                              error=user_error_text(error))
        request.session[FLASH_KEY] = _("%s хүсэлтийг хянуулахаар илгээлээ.", result["name"])
        return request.redirect(f"{ROOT}/offerings/{enrollment['offering_id']}#roster", code=303)
