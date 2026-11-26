# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

STYLE_PATH = "formula_grade_studio/static/src/grade_studio/grade_studio.scss"
REASON = "Шалгалтын баталгаажсан протоколын нийлбэрийг залруулах шаардлагатай."


@tagged("post_install", "-at_install", "formula_grade_studio")
class TestGradeStudio(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.users = {}
        specs = [
            ("lecturer", [("campus_university", "group_campus_lecturer")]),
            ("other_lecturer", [("campus_university", "group_campus_lecturer")]),
            ("registrar", [("campus_university", "group_campus_registrar")]),
            ("second_registrar", [("campus_university", "group_campus_registrar")]),
            ("student", [("campus_university", "group_campus_student")]),
            ("auditor", [("campus_university", "group_campus_auditor")]),
            ("isms_auditor", [("campus_university", "group_campus_auditor"),
                              ("university_isms", "group_isms_auditor")]),
        ]
        for login, refs in specs:
            cls.users[login] = cls.env["res.users"].with_context(no_reset_password=True).create({
                "name": "Studio test " + login,
                "login": "gs.test." + login,
                "groups_id": [Command.set([cls.env.ref("%s.%s" % ref).id for ref in refs])],
            })
        cls.program = cls.env["campus.program"].create({
            "code": "GS-PRG", "name": "Studio test program", "department": "Test faculty",
        })
        cls.course = cls.env["campus.course"].create({
            "code": "GS-338", "name": "Studio test course", "credits": 3, "program_id": cls.program.id,
        })
        cls.offering = cls.env["campus.offering"].create({
            "name": "Studio open semester", "course_id": cls.course.id, "semester": "GS-2026-A",
            "lecturer_id": cls.users["lecturer"].id, "state": "open",
        })
        cls.other_offering = cls.env["campus.offering"].create({
            "name": "Other open semester", "course_id": cls.course.id, "semester": "GS-2026-A",
            "lecturer_id": cls.users["other_lecturer"].id, "state": "open",
        })
        cls.students = cls.env["campus.student"].create([
            {"student_code": "GS-001", "name": "Studio Anar", "user_id": cls.users["student"].id,
             "program_id": cls.program.id},
            {"student_code": "GS-002", "name": "Studio Nomin", "program_id": cls.program.id},
        ])
        cls.enrollment = cls.env["campus.enrollment"].sudo().create({
            "student_id": cls.students[0].id, "offering_id": cls.offering.id, "score": 72,
        })
        cls.other_enrollment = cls.env["campus.enrollment"].sudo().create({
            "student_id": cls.students[1].id, "offering_id": cls.other_offering.id, "score": 81,
        })

    # ------------------------------------------------------------- helpers
    def _request(self, user="lecturer", score=85, enrollment=None, submit=True):
        change = self.env["campus.grade.change"].with_user(self.users[user]).create({
            "enrollment_id": (enrollment or self.enrollment).id,
            "proposed_score": score,
            "reason": REASON,
            "evidence_ref": "GS-MINUTES",
        })
        if submit:
            change.action_submit()
        return change

    def _queue(self, user, flt="all"):
        return self.env["formula.grade.studio"].with_user(self.users[user]).get_queue({"filter": flt})

    def _detail(self, user, change):
        return self.env["formula.grade.studio"].with_user(self.users[user]).get_request(change.id)

    def _actions(self, user, change):
        return self._detail(user, change)["actions"]

    def _flush_tracking(self):
        # Odoo 18 writes tracking messages in a precommit hook (normally run at commit).
        # Running the hooks lets this single test transaction read the chatter, as Odoo's own
        # mail tests do. Production requests commit, so the studio always sees these messages.
        self.env.flush_all()
        self.env.cr.precommit.run()

    def _reject_with_note(self, change, user="registrar"):
        reviewer = change.with_user(self.users[user])
        reviewer.write({"review_note": "Протоколын эх баримт хангалтгүй тул татгалзав."})
        reviewer.action_reject()

    # --------------------------------------------------- visibility by role
    def test_lecturer_sees_only_own_requests(self):
        own = self._request(user="lecturer")
        other = self._request(user="other_lecturer", score=90, enrollment=self.other_enrollment)
        ids = [item["id"] for item in self._queue("lecturer")["items"]]
        self.assertIn(own.id, ids)
        self.assertNotIn(other.id, ids)
        with self.assertRaises(AccessError):
            self._detail("lecturer", other)

    def test_registrar_sees_every_request(self):
        own = self._request(user="lecturer")
        other = self._request(user="other_lecturer", score=90, enrollment=self.other_enrollment)
        result = self._queue("registrar")
        self.assertFalse(result["access_denied"])
        ids = [item["id"] for item in result["items"]]
        self.assertCountEqual(ids, [own.id, other.id])
        self.assertEqual(result["counts"]["all"], 2)

    def test_student_gets_no_studio_data(self):
        self._request(user="lecturer")
        result = self._queue("student")
        self.assertTrue(result["access_denied"])
        self.assertEqual(result["items"], [])
        change = self.env["campus.grade.change"].sudo().search([], limit=1)
        with self.assertRaises(AccessError):
            self._detail("student", change)

    def test_auditor_reads_queue_but_cannot_decide(self):
        change = self._request(user="lecturer")
        self.assertIn(change.id, [item["id"] for item in self._queue("auditor")["items"]])
        actions = self._actions("auditor", change)
        self.assertFalse(actions["approve"]["allowed"])
        self.assertFalse(actions["reject"]["allowed"])
        with self.assertRaises(AccessError):
            change.with_user(self.users["auditor"]).action_approve()
        self.assertEqual(self.enrollment.score, 72)

    def test_queue_filters_and_counts(self):
        first = self._request(user="lecturer", score=85)
        second = self._request(user="lecturer", score=90)
        self.assertEqual(self._queue("registrar", "pending")["counts"]["pending"], 2)
        first.with_user(self.users["registrar"]).action_approve()
        registrar_pending = self._queue("registrar", "pending")
        self.assertEqual([item["id"] for item in registrar_pending["items"]], [second.id])
        stale = self._queue("registrar", "stale")
        self.assertEqual([item["id"] for item in stale["items"]], [second.id])
        self.assertEqual(stale["counts"]["stale"], 1)
        mine = self._queue("lecturer", "mine")
        self.assertCountEqual([item["id"] for item in mine["items"]], [first.id, second.id])
        with self.assertRaises(UserError):
            self.env["formula.grade.studio"].with_user(self.users["registrar"]).get_queue({"filter": "bogus"})

    # ----------------------------------------------------- server authority
    def test_requester_cannot_approve_own_request(self):
        change = self._request(user="registrar")
        self.assertFalse(self._actions("registrar", change)["approve"]["allowed"])
        with self.assertRaises(AccessError):
            change.with_user(self.users["registrar"]).action_approve()
        self.assertEqual(change.state, "submitted")
        self.assertEqual(self.enrollment.score, 72)

    def test_stale_revision_is_flagged_and_approval_rejected(self):
        first = self._request(user="lecturer", score=85)
        second = self._request(user="lecturer", score=90)
        first.with_user(self.users["registrar"]).action_approve()
        detail = self._detail("registrar", second)
        self.assertTrue(detail["stale"])
        self.assertIn("revision", detail["stale_reasons"])
        self.assertIn("score", detail["stale_reasons"])
        self.assertFalse(detail["actions"]["approve"]["allowed"])
        with self.assertRaises(ValidationError):
            second.with_user(self.users["registrar"]).action_approve()
        self.enrollment.invalidate_recordset()
        self.assertEqual(self.enrollment.score, 85)
        self.assertEqual(self.enrollment.grade_revision, 1)
        self.assertEqual(second.state, "submitted")

    def test_approval_updates_score_once_and_increments_revision(self):
        change = self._request(user="lecturer", score=85)
        change.with_user(self.users["registrar"]).action_approve()
        self.enrollment.invalidate_recordset()
        self.assertEqual(self.enrollment.score, 85)
        self.assertEqual(self.enrollment.grade_revision, 1)
        self.assertEqual(change.state, "approved")
        self.assertEqual(change.approver_id, self.users["registrar"])
        self.assertFalse(self._actions("registrar", change)["approve"]["allowed"])
        # Double approval (second click or replayed RPC) must fail cleanly and change nothing.
        with self.assertRaises(ValidationError):
            change.with_user(self.users["registrar"]).action_approve()
        self.enrollment.invalidate_recordset()
        self.assertEqual(self.enrollment.score, 85)
        self.assertEqual(self.enrollment.grade_revision, 1)

    def test_direct_grade_writes_are_blocked_for_every_role(self):
        for login in ("lecturer", "registrar", "auditor"):
            with self.assertRaises(AccessError):
                self.enrollment.with_user(self.users[login]).write({"score": 99})
            with self.assertRaises(AccessError):
                self.enrollment.with_user(self.users[login]).write({"grade_revision": 5})
        self.enrollment.invalidate_recordset()
        self.assertEqual(self.enrollment.score, 72)
        self.assertEqual(self.enrollment.grade_revision, 0)

    def test_allowed_actions_match_server_behaviour(self):
        # Both requests are created against the same snapshot (72, revision 0) before any approval.
        fresh = self._request(user="lecturer", score=85)
        stale = self._request(user="lecturer", score=90)

        # Registrar, not the requester, fresh submitted request: approve and reject allowed.
        actions = self._actions("registrar", fresh)
        self.assertTrue(actions["approve"]["allowed"])
        self.assertTrue(actions["reject"]["allowed"])
        self.assertTrue(actions["reject"]["requires_note"])
        fresh.with_user(self.users["registrar"]).action_approve()

        # Now the second request is stale: studio refuses approve, server refuses it too.
        # Reject stays allowed on both sides because action_reject does not check staleness.
        self.assertTrue(self._detail("registrar", stale)["stale"])
        actions = self._actions("registrar", stale)
        self.assertFalse(actions["approve"]["allowed"])
        self.assertTrue(actions["reject"]["allowed"])
        with self.assertRaises(ValidationError):
            stale.with_user(self.users["registrar"]).action_approve()
        self._reject_with_note(stale)
        self.assertEqual(stale.state, "rejected")

        # Lecturer on own submitted request: nothing decidable, server refuses approval.
        own = self._request(user="lecturer", score=88)
        actions = self._actions("lecturer", own)
        self.assertFalse(actions["approve"]["allowed"])
        self.assertFalse(actions["reject"]["allowed"])
        with self.assertRaises(AccessError):
            own.with_user(self.users["lecturer"]).action_approve()

        # Draft owned by the lecturer: submit allowed, approve refused until it is submitted.
        draft = self._request(user="lecturer", score=91, submit=False)
        actions = self._actions("lecturer", draft)
        self.assertTrue(actions["submit"]["allowed"])
        self.assertFalse(actions["approve"]["allowed"])
        with self.assertRaises(ValidationError):
            draft.with_user(self.users["registrar"]).action_approve()
        draft.action_submit()
        self.assertEqual(draft.state, "submitted")

    def test_requester_cannot_reject_own_request(self):
        change = self._request(user="registrar")
        self.assertFalse(self._actions("registrar", change)["reject"]["allowed"])
        change.with_user(self.users["registrar"]).write({"review_note": "Өөрөө татгалзах оролдлого."})
        with self.assertRaises(AccessError):
            change.with_user(self.users["registrar"]).action_reject()
        self.assertEqual(change.state, "submitted")

    def test_reject_needs_reason_and_leaves_grade_untouched(self):
        change = self._request(user="lecturer", score=85)
        reviewer = change.with_user(self.users["registrar"])
        self.assertTrue(self._actions("registrar", change)["reject"]["requires_note"])
        with self.assertRaises(ValidationError):
            reviewer.action_reject()
        self._reject_with_note(change)
        self.assertEqual(change.state, "rejected")
        self.enrollment.invalidate_recordset()
        self.assertEqual(self.enrollment.score, 72)
        self.assertEqual(self.enrollment.grade_revision, 0)

    # -------------------------------------------------------- history/audit
    def test_history_and_isms_visibility_follow_roles(self):
        change = self._request(user="lecturer", score=85)
        self._flush_tracking()
        change.with_user(self.users["registrar"]).action_approve()
        self._flush_tracking()
        detail = self._detail("registrar", change)
        tracking = [entry for entry in detail["history"] if entry["type"] == "tracking"]
        # The approval's state change must be visible with its label. The submit step is not
        # asserted: Odoo 18 posts tracking in a precommit hook, which this single test
        # transaction only partly reproduces (see _flush_tracking).
        self.assertIn("Баталсан", [entry["new"] for entry in tracking], detail["history"])
        self.assertFalse(detail["isms"]["visible"])
        self.assertEqual(detail["isms"]["entries"], [])

        isms = self._detail("isms_auditor", change)
        self.assertTrue(isms["isms"]["visible"])
        self.assertTrue(isms["isms"]["entries"])
        self.assertTrue(any(entry["model"] for entry in isms["isms"]["entries"]))

    def test_detail_hides_review_note_from_non_registrars(self):
        change = self._request(user="lecturer", score=85)
        self._reject_with_note(change)
        self.assertEqual(self._detail("lecturer", change)["review_note"], "")
        self.assertIn("Протоколын", self._detail("registrar", change)["review_note"])

    # ----------------------------------------------------------- wiring
    def test_menu_is_limited_to_academic_roles(self):
        menu = self.env.ref("formula_grade_studio.menu_formula_grade_studio")
        expected = {self.env.ref("campus_university.group_campus_%s" % role).id
                    for role in ("lecturer", "registrar", "auditor")}
        self.assertEqual(set(menu.groups_id.ids), expected)
        self.assertNotIn(self.env.ref("campus_university.group_campus_student").id, menu.groups_id.ids)
        self.assertEqual(menu.parent_id, self.env.ref("campus_university.menu_campus_root"))

    def test_backend_bundle_compiles_without_scss_errors(self):
        asset = self.env["ir.asset"]
        paths = [entry[0].lstrip("/") for entry in asset._get_asset_paths(
            "web.assets_backend", asset._get_asset_params())]
        self.assertIn(STYLE_PATH, paths)
        bundle = self.env["ir.qweb"]._get_asset_bundle("web.assets_backend", css=True, js=False)
        # preprocess_css always compiles; css() could return a cached attachment and hide errors.
        bundle.preprocess_css()
        self.assertFalse(bundle.css_errors, "SCSS compile errors: %s" % bundle.css_errors)


    def test_reject_with_note_is_atomic(self):
        """A failed rejection (requester rejecting own request) must not leave the note behind."""
        # Registrar is the requester: the note write is allowed, the self-rejection is not.
        req = self._request(user="registrar")
        Studio = self.env["formula.grade.studio"].with_user(self.users["registrar"])
        with self.assertRaises(UserError):
            with self.env.cr.savepoint():
                Studio.reject_with_note(req.id, "Өөрийн хүсэлтийг татгалзах оролдлого")
        req.invalidate_recordset()
        self.assertFalse((req.review_note or "").strip())
        self.assertEqual(req.state, "submitted")

    def test_public_methods_are_model_level(self):
        """The client calls these through orm.call without record ids."""
        Studio = type(self.env["formula.grade.studio"])
        for name in ("get_queue", "get_request", "reject_with_note"):
            self.assertEqual(getattr(getattr(Studio, name), "_api", None), "model", name)
