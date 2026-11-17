from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


_SYNC_AUTHORITY = object()
_STATES = ("incident", "report", "investigate", "resolve", "close")


class IsmsHelpdeskIncident(models.Model):
    _inherit = "isms.incident"

    helpdesk_ticket_ids = fields.One2many("helpdesk.ticket", "isms_incident_id", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_helpdesk_tickets()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"state", "name", "severity", "assignee_id", "reporter_id"}.intersection(vals):
            self._sync_helpdesk_tickets()
        return result

    def _sync_helpdesk_tickets(self):
        team = self.env.ref("university_isms_helpdesk.team_security")
        Ticket = self.env["helpdesk.ticket"].with_context(_isms_helpdesk_sync=_SYNC_AUTHORITY).sudo()
        priority = {"low": "0", "medium": "1", "high": "2", "critical": "3"}
        for rec in self:
            # The caller has already passed incident create/write permissions.
            # Sudo is confined to copying a minimal service-ticket description.
            source = rec.sudo()
            stage = self.env.ref("university_isms_helpdesk.stage_" + source.state)
            values = {
                "name": "%s — %s" % (source.code, source.name),
                "stage_id": stage.id,
                "team_id": team.id,
                "partner_id": source.reporter_id.partner_id.id,
                "priority": priority[source.severity],
                "user_id": source.assignee_id.id if source.assignee_id in team.user_ids else False,
            }
            ticket = Ticket.search([("isms_incident_id", "=", source.id)], limit=1)
            if ticket:
                ticket.write(values)
            else:
                values.update({
                    "isms_incident_id": source.id,
                    "description": "<p>%s</p><p>%s</p>" % (
                        escape(source.code),
                        escape(_("МАБ-ын дэлгэрэнгүй мэдээллийг эрхийн хяналттай ISMS бүртгэлээс үзнэ үү.")),
                    ),
                })
                Ticket.create(values)

    def action_open_helpdesk(self):
        self.ensure_one()
        self.check_access("read")
        ticket = self.env["helpdesk.ticket"].search([("isms_incident_id", "=", self.id)], limit=1)
        if not ticket:
            raise UserError(_("Хандах эрхтэй Helpdesk тасалбар олдсонгүй."))
        return {"type": "ir.actions.act_window", "name": _("Community Helpdesk"),
                "res_model": "helpdesk.ticket", "view_mode": "form", "res_id": ticket.id}


class IsmsHelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        if self.env.context.get("isms_helpdesk_only"):
            return self.env["helpdesk.ticket.stage"].browse([
                self.env.ref("university_isms_helpdesk.stage_" + state).id
                for state in _STATES
            ])
        return super()._read_group_stage_ids(stages, domain)

    isms_incident_id = fields.Many2one("isms.incident", string="ISMS incident", readonly=True,
                                      ondelete="restrict", index=True, copy=False)

    _sql_constraints = [
        ("isms_incident_unique", "unique(isms_incident_id)", "Нэг зөрчил нэг Helpdesk тасалбартай байна."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        trusted = self.env.context.get("_isms_helpdesk_sync") is _SYNC_AUTHORITY
        if not trusted and any(vals.get("isms_incident_id") for vals in vals_list):
            raise AccessError(_("Зөрчилтэй холбох тасалбарыг ISMS workflow үүсгэнэ."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("_isms_helpdesk_sync") is _SYNC_AUTHORITY:
            return super().write(vals)
        if "isms_incident_id" in vals:
            raise AccessError(_("ISMS холбоосыг гараар өөрчлөхгүй."))
        linked = self.filtered("isms_incident_id")
        if linked and {"team_id", "active", "company_id", "partner_id"}.intersection(vals):
            raise AccessError(_("ISMS тасалбарын хариуцлага ба харагдах хүрээг ISMS бүртгэлээс удирдана."))
        if "stage_id" not in vals or not linked:
            return super().write(vals)
        stage_ids = {self.env.ref("university_isms_helpdesk.stage_" + state).id: state for state in _STATES}
        target = stage_ids.get(vals["stage_id"])
        if not target:
            raise UserError(_("ISMS тасалбар зөвхөн таван баталгаатай үе шат ашиглана."))
        for ticket in linked:
            ticket.check_access("write")
            incident = ticket.isms_incident_id
            incident.check_access("write")
            # Incident.write validates transition, actor, required resolution,
            # notification decision and CISO closure. The reverse sync updates us.
            incident.write({"state": target})
        other_values = {key: value for key, value in vals.items() if key != "stage_id"}
        if other_values:
            super(IsmsHelpdeskTicket, linked).write(other_values)
        ordinary = self - linked
        if ordinary:
            super(IsmsHelpdeskTicket, ordinary).write(vals)
        return True

    def unlink(self):
        if self.filtered("isms_incident_id"):
            raise AccessError(_("ISMS нотолгоотой тасалбарыг устгахгүй."))
        return super().unlink()

    def action_open_isms_incident(self):
        self.ensure_one()
        self.check_access("read")
        self.isms_incident_id.check_access("read")
        return {"type": "ir.actions.act_window", "name": _("ISMS incident"),
                "res_model": "isms.incident", "view_mode": "form", "res_id": self.isms_incident_id.id}
