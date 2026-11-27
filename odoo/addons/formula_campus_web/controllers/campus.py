import re
import time

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.osv.expression import AND, OR

from ..models.admission import STATE_LABELS, token_digest


AREAS = (("technology", "Технологи"), ("business", "Бизнес"), ("design", "Дизайн"))
SUMMARY_FIELDS = ["name", "slug", "area", "school", "summary", "degree", "duration"]
DETAIL_FIELDS = SUMMARY_FIELDS + ["curriculum", "outcome"]
EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
OPEN_PROGRAM = [("academic_program_id.active", "=", True)]


class FormulaCampusWebsite(http.Controller):
    def _programs(self, domain=(), *, detail=False, limit=24, accepting=False):
        # The public user has no model ACL. Only explicitly published rows and
        # website-owned fields pass through this narrow projection.
        public = request.env["formula.public.program"].sudo()
        records = public.search(
            AND([[("published", "=", True)], list(domain), OPEN_PROGRAM if accepting else []]),
            limit=limit,
        )
        available = set(records.filtered_domain(OPEN_PROGRAM).ids)
        return [dict(row, accepting=row["id"] in available)
                for row in records.read(DETAIL_FIELDS if detail else SUMMARY_FIELDS)]

    def _render(self, template, title, **values):
        return request.render("formula_campus_web." + template, {
            "title": title + " · Formula University",
            "show_staff_erp": not request.env.user.has_group("campus_university.group_campus_student"),
            **values,
        }, headers=[("Cache-Control", "private, no-store")])

    @http.route("/university", type="http", auth="public", methods=["GET"])
    def home(self, **kw):
        return self._render("home", "Нүүр", programs=self._programs(limit=3))

    @http.route("/university/programs", type="http", auth="public", methods=["GET"])
    def programs(self, q="", area="", **kw):
        q = q.strip()[:80]
        area = area if area in dict(AREAS) else ""
        domain = [("area", "=", area)] if area else []
        if q:
            domain = AND([domain, OR([[("name", "ilike", q)], [("summary", "ilike", q)]])])
        return self._render("programs", "Хөтөлбөрүүд", programs=self._programs(domain),
                            q=q, areas=AREAS, area=area)

    @http.route("/university/programs/<string:slug>", type="http", auth="public", methods=["GET"])
    def program(self, slug, **kw):
        matches = self._programs([("slug", "=", slug)], detail=True, limit=1)
        if not matches:
            return request.not_found()
        return self._render("program", matches[0]["name"], program=matches[0])

    @http.route("/university/admissions", type="http", auth="public", methods=["GET"])
    def admissions(self, program="", **kw):
        return self._render("admissions", "Элсэлт", programs=self._programs(),
                            selected=program, form={}, error="", received=False)

    @http.route("/university/admissions/inquiry", type="http", auth="public", methods=["POST"],
                csrf=True)
    def inquiry(self, **post):
        limits = {"name": 100, "email": 160, "program": 90, "message": 1200}
        form = {key: str(post.get(key, "")).strip()[:limit + 1] for key, limit in limits.items()}
        program = self._programs([("slug", "=", form["program"])], limit=1)
        now = int(time.time())
        last = request.session.get("formula_inquiry_at", 0)
        invalid = any(len(form[key]) > limit for key, limit in limits.items())
        error = ""
        if post.get("website") or now - last < 30:
            error = "Хүсэлт дахин илгээхээс өмнө түр хүлээнэ үү."
        elif invalid or not 2 <= len(form["name"]) <= 100 or not EMAIL_RE.fullmatch(form["email"]):
            error = "Нэр болон цахим шуудангаа зөв оруулна уу."
        elif not program or len(form["message"]) < 12:
            error = "Хөтөлбөрөө сонгож, дор хаяж 12 тэмдэгттэй асуулт бичнэ үү."
        if error:
            return self._render("admissions", "Элсэлт", programs=self._programs(),
                                selected=form["program"], form=form, error=error, received=False)
        request.env["formula.campus.inquiry"].sudo().create({
            "name": form["name"], "email": form["email"], "program_id": program[0]["id"],
            "message": form["message"],
        })
        request.session["formula_inquiry_at"] = now
        request.session["formula_inquiry_received"] = True
        return request.redirect("/university/admissions/received", code=303)

    @http.route("/university/admissions/received", type="http", auth="public", methods=["GET"])
    def received(self, **kw):
        if not request.session.get("formula_inquiry_received"):
            return request.redirect("/university/admissions")
        request.session.pop("formula_inquiry_received", None)
        return self._render("received", "Лавлагаа бүртгэгдлээ")

    def _applications(self):
        return self._programs(accepting=True)

    def _application_page(self, *, form=None, error="", **values):
        return self._render("apply", "Элсэх өргөдөл", programs=self._applications(),
                            form=form or {}, error=error, **values)

    @http.route("/university/admissions/apply", type="http", auth="public", methods=["GET"])
    def apply(self, program="", **kw):
        slug = program[:90]
        if slug and not self._programs([("slug", "=", slug)], accepting=True, limit=1):
            return self._application_page(error="Сонгосон хөтөлбөрийн элсэлт нээгдээгүй байна.")
        return self._application_page(form={"program": slug})

    @http.route("/university/admissions/apply", type="http", auth="public", methods=["POST"], csrf=True)
    def submit_application(self, **post):
        limits = {"name": 100, "email": 160, "program": 90, "motivation": 1200}
        form = {key: str(post.get(key, "")).strip()[:limit + 1] for key, limit in limits.items()}
        if post.get("website") or int(time.time()) - request.session.get("formula_application_at", 0) < 30:
            return self._application_page(form=form, error="Өргөдөл дахин илгээхээс өмнө түр хүлээнэ үү.")
        program = request.env["formula.public.program"].sudo().search(
            [("slug", "=", form["program"]), ("published", "=", True)] + OPEN_PROGRAM,
            limit=1,
        )
        if not program:
            return self._application_page(form=form, error="Өргөдөл авч буй хөтөлбөрөөс сонгоно уу.")
        try:
            reference, token = request.env["formula.campus.admission"].sudo()._submit_public(
                name=form["name"], email=form["email"].lower(), program=program, motivation=form["motivation"],
            )
        except ValidationError as error:
            return self._application_page(form=form, error=str(error))
        request.session["formula_application_at"] = int(time.time())
        request.session["formula_application_receipt"] = (reference, token)
        return request.redirect("/university/admissions/receipt", code=303)

    @http.route("/university/admissions/receipt", type="http", auth="public", methods=["GET"])
    def application_receipt(self, **kw):
        receipt = request.session.pop("formula_application_receipt", None)
        if not receipt:
            return request.redirect("/university/admissions/status")
        return self._render("application_receipt", "Өргөдөл хүлээн авлаа", reference=receipt[0], token=receipt[1])

    @http.route("/university/admissions/status", type="http", auth="public", methods=["GET", "POST"], csrf=True)
    def application_status(self, reference="", code="", **kw):
        result = False
        error = ""
        if request.httprequest.method == "POST":
            reference = reference.strip().upper()
            code = code.strip()
            if re.fullmatch(r"ADM-[0-9]{4}-[0-9]{5,12}", reference) and re.fullmatch(r"[A-Za-z0-9_-]{32}", code):
                entry = request.env["formula.campus.admission"].sudo().search(
                    [("reference", "=", reference), ("token_digest", "=", token_digest(code))], limit=1,
                )
                if entry:
                    result = {
                        "reference": entry.reference, "state": dict(STATE_LABELS)[entry.state],
                        "decision": entry.decision_message if entry.state in ("accepted", "declined") else False,
                        "accepted": entry.state == "accepted",
                    }
            if not result:
                error = "Өргөдлийн дугаар эсвэл шалгах код таарахгүй байна."
        return self._render("application_status", "Өргөдлийн төлөв", result=result, error=error)
