from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import request


class FormAssistant(http.Controller):
    @http.route("/formula/form/brief", type="json", auth="user", methods=["POST"])
    def brief(self):
        return request.env["formula.assistant"]._initial()

    @http.route("/formula/form/settings", type="json", auth="user", methods=["POST"])
    def settings(self, hidden=None, size=None, seen=None):
        return request.env["formula.assistant"]._preferences(hidden, size, seen)

    @http.route("/formula/form/chat", type="json", auth="user", methods=["POST"])
    def chat(self, question=None):
        if not isinstance(question, str) or not question.strip() or len(question) > 300:
            raise ValidationError(_("1–300 тэмдэгттэй асуулт бичнэ үү."))
        return request.env["formula.assistant"]._answer(question.strip())
