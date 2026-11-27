from odoo import http
from odoo.http import request


CATEGORIES = (
    ("phishing", "Сэжигтэй имэйл, холбоос"),
    ("malware", "Хортой програм"),
    ("account_compromise", "Бүртгэлд өөр хүн нэвтэрсэн"),
    ("unauthorized_access", "Зөвшөөрөлгүй хандалт"),
    ("data_leak", "Мэдээлэл задарсан"),
    ("integrity", "Дүн эсвэл бүртгэл өөрчлөгдсөн"),
    ("dos", "Үйлчилгээ тасалдсан"),
    ("physical", "Төхөөрөмж алдагдсан"),
    ("other", "Бусад"),
)
STATUS = {
    "incident": "Илгээсэн", "report": "Хүлээн авсан", "investigate": "Шалгаж буй",
    "resolve": "Шийдвэрлэсэн", "close": "Хаасан",
}


class CampusIncidentPortal(http.Controller):
    def _reporter_role(self):
        user = request.env.user
        if user.has_group("campus_university.group_campus_lecturer"):
            return "faculty"
        if request.env["campus.portal.student"]._own_student():
            return "student"
        return False

    def _page(self, role, values=None, error=None, status=200):
        # Render only a small projection for this authenticated reporter. No
        # attachments, internal notes, assignments or other reports enter the page.
        reports = request.env["isms.incident"].sudo().search_read(
            [("reporter_id", "=", request.env.uid), ("reporter_type", "in", ("student", "faculty"))],
            ["code", "name", "state"], order="id desc", limit=20,
        )
        return request.render("campus_isms_bridge.portal_incident", {
            "reports": reports,
            "states": STATUS,
            "categories": CATEGORIES,
            "values": values or {},
            "error": error,
            "receipt": request.session.pop("campus_incident_receipt", None),
            "portal_url": "/campus/teacher" if role == "faculty" else "/my/campus",
        }, status=status, headers=[("Cache-Control", "private, no-store")])

    @http.route("/my/campus/incidents", type="http", auth="user", website=True, methods=["GET"])
    def incident_form(self, **kw):
        role = self._reporter_role()
        if not role:
            return request.not_found()
        return self._page(role)

    @http.route("/my/campus/incidents", type="http", auth="user", website=True, methods=["POST"], csrf=True)
    def submit_incident(self, **post):
        role = self._reporter_role()
        if not role:
            return request.not_found()

        limits = {"name": 120, "description": 4000, "category": 32}
        values = {key: str(post.get(key) or "").strip()[:size + 1] for key, size in limits.items()}
        if not (
            4 <= len(values["name"]) <= limits["name"]
            and 12 <= len(values["description"]) <= limits["description"]
            and values["category"] in dict(CATEGORIES)
        ):
            return self._page(
                role, values=values, status=400,
                error="Гарчиг, ангилал, тайлбараа шалгана уу. Тайлбар дор хаяж 12 тэмдэгттэй байна.",
            )

        # Build the values here; the caller cannot set severity, owners, state or reporter.
        # sudo bypasses the model ACL while retaining the request UID in the audit.
        incident = request.env["isms.incident"].sudo().create({
            **values, "reporter_id": request.env.uid, "reporter_type": role,
        })
        incident.action_report()
        request.session["campus_incident_receipt"] = incident.code
        return request.redirect("/my/campus/incidents", code=303)
