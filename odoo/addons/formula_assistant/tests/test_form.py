from datetime import timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestFormAssistant(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env(context={**cls.env.context, "no_reset_password": True, "tracking_disable": True})
        cls.first = new_test_user(
            env, "form_test_first", groups="base.group_user,project.group_project_user")
        cls.second = new_test_user(
            env, "form_test_second", groups="base.group_user,project.group_project_user")
        cls.portal = new_test_user(env, "form_test_portal", groups="base.group_portal")
        cls.assistant = cls.env["formula.assistant"]
        cls.project = cls.env["project.project"].create({"name": "Form daily test"})

    def test_accounts_have_independent_preferences_and_seen_date(self):
        first = self.assistant.with_user(self.first)
        second = self.assistant.with_user(self.second)
        self.assertTrue(first._initial()["greet"])
        self.assertTrue(first._preferences(hidden=True, size="large")["hidden"])
        self.assertFalse(first._initial()["brief"])
        self.assertEqual(first._preferences()["size"], "large")
        self.assertTrue(second._initial()["greet"])
        self.assertEqual(second._preferences()["size"], "normal")
        first._preferences(hidden=False, seen=True)
        self.assertFalse(first._initial()["greet"])
        with self.assertRaises(ValidationError):
            first._preferences(size="xlarge")

    def test_daily_chat_returns_only_owned_open_due_tasks(self):
        assistant = self.assistant.with_user(self.first)
        _, start, end = assistant._clock()
        task_model = self.env["project.task"]
        for title, owner, deadline, state in (
            ("Form own due", self.first, start + timedelta(hours=1), "01_in_progress"),
            ("Form other user's due", self.second, start + timedelta(hours=1), "01_in_progress"),
            ("Form past closed", self.first, start - timedelta(days=1), "1_done"),
            ("Form future", self.first, end, "01_in_progress"),
        ):
            task_model.create({
                "name": title, "project_id": self.project.id, "date_deadline": deadline,
                "user_ids": [Command.set(owner.ids)], "state": state,
            })
        result = assistant._answer("Өнөөдрийн ажил")
        labels = [row["text"] for row in result["items"]]
        self.assertTrue(any("Form own due" in row for row in labels))
        self.assertTrue(all("Form other" not in row and "past closed" not in row and "Form future" not in row
                            for row in labels))
        portal = self.assistant.with_user(self.portal)
        self.assertFalse(portal._answer("Өнөөдрийн ажил")["items"])
        self.assertFalse(portal._answer("Хичээлийн хуваарь")["items"])
        self.assertIn("Form", portal._answer("Сайн уу!")["text"])
