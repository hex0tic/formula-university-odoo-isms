from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIsmsHelpdeskBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.users = {}
        for role in ["reporter", "analyst", "manager", "auditor"]:
            cls.users[role] = cls.env["res.users"].with_context(no_reset_password=True).create({
                "name": "Helpdesk test " + role, "login": "helpdesk.test." + role,
                "groups_id": [Command.set([cls.env.ref("university_isms.group_isms_" + role).id])],
            })
        cls.other = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Other reporter", "login": "helpdesk.test.other.reporter",
            "groups_id": [Command.set([cls.env.ref("university_isms.group_isms_reporter").id])],
        })

    def _incident(self):
        return self.env["isms.incident"].with_user(self.users["reporter"]).create({
            "name": "Synthetic suspicious grade-change request", "category": "integrity",
            "description": "Test case only.", "severity": "high",
        })

    def test_isms_board_has_exactly_five_workflow_columns(self):
        stages = self.env["helpdesk.ticket"].with_context(isms_helpdesk_only=True)._read_group_stage_ids(
            self.env["helpdesk.ticket.stage"], [])
        expected = self.env["helpdesk.ticket.stage"].browse([
            self.env.ref("university_isms_helpdesk.stage_" + state).id
            for state in ("incident", "report", "investigate", "resolve", "close")
        ])
        self.assertEqual(stages, expected)

    def test_incident_creates_one_real_helpdesk_ticket(self):
        incident = self._incident()
        tickets = self.env["helpdesk.ticket"].sudo().search([("isms_incident_id", "=", incident.id)])
        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets.stage_id, self.env.ref("university_isms_helpdesk.stage_incident"))
        incident.action_report()
        self.assertEqual(tickets.stage_id, self.env.ref("university_isms_helpdesk.stage_report"))
        self.assertEqual(tickets.partner_id, self.users["reporter"].partner_id)

    def test_helpdesk_stage_cannot_skip_isms_workflow(self):
        incident = self._incident()
        ticket = incident.sudo().helpdesk_ticket_ids.with_user(self.users["analyst"])
        with self.assertRaises(UserError):
            ticket.write({"stage_id": self.env.ref("university_isms_helpdesk.stage_close").id})
        self.assertEqual(incident.state, "incident")
        self.assertEqual(ticket.stage_id, self.env.ref("university_isms_helpdesk.stage_incident"))

    def test_all_five_stages_execute_through_helpdesk(self):
        incident = self._incident()
        ticket = incident.sudo().helpdesk_ticket_ids.with_user(self.users["analyst"])
        for state in ["report", "investigate"]:
            ticket.write({"stage_id": self.env.ref("university_isms_helpdesk.stage_" + state).id})
            self.assertEqual(incident.state, state)
        incident.with_user(self.users["analyst"]).write({
            "root_cause": "Хуурамч хүсэлт, баталгаагүй сувгийн ашиглалт.",
            "resolution": "Хүсэлтийг тусгаарлаж, протоколыг давхар баталгаажуулсан.",
            "lessons_learned": "Зөвшөөрлийг зөвхөн системийн тусдаа эрхтэй ажилтан өгнө.",
        })
        ticket.write({"stage_id": self.env.ref("university_isms_helpdesk.stage_resolve").id})
        with self.assertRaises(AccessError):
            ticket.write({"stage_id": self.env.ref("university_isms_helpdesk.stage_close").id})
        ticket.with_user(self.users["manager"]).write({
            "stage_id": self.env.ref("university_isms_helpdesk.stage_close").id,
        })
        self.assertEqual(incident.state, "close")
        self.assertTrue(incident.closed_at)
        self.assertTrue(ticket.closed)

    def test_reporter_isolation_and_auditor_read_only(self):
        incident = self._incident()
        ticket = incident.sudo().helpdesk_ticket_ids
        self.assertTrue(ticket.with_user(self.users["reporter"]).read(["name"]))
        with self.assertRaises(AccessError):
            ticket.with_user(self.other).read(["name"])
        self.assertTrue(ticket.with_user(self.users["auditor"]).read(["name"]))
        with self.assertRaises(AccessError):
            ticket.with_user(self.users["auditor"]).write({"name": "tamper"})

    def test_cannot_detach_or_destroy_incident_ticket(self):
        incident = self._incident()
        ticket = incident.sudo().helpdesk_ticket_ids.with_user(self.users["manager"])
        for values in [{"isms_incident_id": False}, {"active": False}, {"team_id": False}]:
            with self.assertRaises(AccessError):
                ticket.with_context(_isms_helpdesk_sync=True).write(values)
        with self.assertRaises(AccessError):
            ticket.unlink()
