"""SEC-04 security regression tests.

Every test runs as a real low-privilege user through ``with_user`` (no sudo, no superuser
context). Fixtures are created once as superuser in setUpClass. Each test states the attack
it simulates in its docstring. A failing test is a real finding and its assertion is kept.
"""
import ast
import logging
import os

import odoo
from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError

# Odoo refuses a whole export with UserError when the user lacks export rights; AccessError is its subclass
DENIED = (AccessError, UserError)
from odoo.tests import TransactionCase, new_test_user, tagged

_logger = logging.getLogger(__name__)
PWD = "Sec-Test-Pass-2026"
CUSTOM_ADDON_MARKER = "extra-addons"


def _export_values(recordset, fields):
    """Return exported cell values, or raise AccessError if the server refuses the export."""
    result = recordset.export_data(fields)
    return [str(cell) for row in result["datas"] for cell in row]


@tagged("post_install", "-at_install", "university_security_tests")
class TestSecurityRegressions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        mk = lambda login, groups: new_test_user(env, login, password=PWD, groups=groups)  # noqa: E731
        cls.normal = mk("sec_normal", "base.group_user")
        cls.student_a = mk("sec_student_a", "campus_university.group_campus_student")
        cls.student_b = mk("sec_student_b", "campus_university.group_campus_student")
        cls.lecturer_a = mk("sec_lecturer_a", "campus_university.group_campus_lecturer")
        cls.lecturer_b = mk("sec_lecturer_b", "campus_university.group_campus_lecturer")
        cls.registrar = mk("sec_registrar", "campus_university.group_campus_registrar")
        cls.reporter_a = mk("sec_reporter_a", "university_isms.group_isms_reporter")
        cls.reporter_b = mk("sec_reporter_b", "university_isms.group_isms_reporter")
        cls.owner_a = mk("sec_owner_a", "university_isms.group_isms_asset_owner")
        cls.owner_b = mk("sec_owner_b", "university_isms.group_isms_asset_owner")
        cls.analyst = mk("sec_analyst", "university_isms.group_isms_analyst")
        cls.ciso = mk("sec_ciso", "university_isms.group_isms_manager")
        cls.auditor = mk("sec_auditor", "university_isms.group_isms_auditor")
        cls.erp_manager = mk("sec_erp_manager", "base.group_erp_manager")

        # Campus fixtures (created as superuser; these are setup, not attacks)
        cls.program = env["campus.program"].create({"code": "SEC-PRG", "name": "Sec", "department": "Sec"})
        cls.course = env["campus.course"].create({"code": "SEC-100", "name": "Sec course",
                                                  "program_id": cls.program.id})
        cls.offering_a = env["campus.offering"].create({"name": "Sec A", "course_id": cls.course.id,
                                                        "lecturer_id": cls.lecturer_a.id, "state": "open"})
        cls.offering_b = env["campus.offering"].create({"name": "Sec B", "course_id": cls.course.id,
                                                        "lecturer_id": cls.lecturer_b.id, "state": "open"})
        cls.stu_a = env["campus.student"].create({"student_code": "SEC-S1", "name": "Student Alpha",
                                                  "program_id": cls.program.id, "user_id": cls.student_a.id})
        cls.stu_b = env["campus.student"].create({"student_code": "SEC-S2", "name": "Student Bravo",
                                                  "program_id": cls.program.id, "user_id": cls.student_b.id})
        cls.enr_a = env["campus.enrollment"].create({"student_id": cls.stu_a.id, "offering_id": cls.offering_a.id,
                                                     "score": 55.0})
        cls.enr_b = env["campus.enrollment"].create({"student_id": cls.stu_b.id, "offering_id": cls.offering_b.id,
                                                     "score": 61.0})

        # ISMS fixtures
        cls.asset_a = env["isms.asset"].create({"name": "Asset Alpha SEC", "owner_id": cls.owner_a.id})
        cls.asset_b = env["isms.asset"].create({"name": "Asset Bravo SEC", "owner_id": cls.owner_b.id})
        cls.threat = env.ref("university_isms.threat_t_01")
        cls.vuln = env.ref("university_isms.vuln_v_01")
        cls.incident_b = env["isms.incident"].with_user(cls.reporter_b).create({
            "name": "Bravo incident SEC-IDOR", "category": "phishing", "severity": "high"})

    # ------------------------------------------------------------------ helpers
    def _stored_password_hash(self, user):
        self.env.cr.execute("SELECT password FROM res_users WHERE id = %s", [user.id])
        return self.env.cr.fetchone()[0] or ""

    def _incident_in_state(self, state, reporter):
        inc = self.env["isms.incident"].with_user(reporter).create({"name": "State fixture %s" % state})
        inc.sudo().write({"state": state, "root_cause": "rc", "resolution": "res",
                          "lessons_learned": "ll", "reported_at": False})
        return inc

    # ---------------------------------------------------- privilege escalation
    def test_01_user_cannot_grant_self_admin_group(self):
        """Attack: a plain user adds himself to base.group_system (Settings > Administrator)
        through a JSON-RPC write on res.users groups_id."""
        admin_group = self.env.ref("base.group_system")
        with self.assertRaises(AccessError):
            self.normal.with_user(self.normal).write({"groups_id": [Command.link(admin_group.id)]})
        self.assertFalse(self.normal.sudo().has_group("base.group_system"))

    def test_02_user_cannot_change_other_users_groups(self):
        """Attack: a campus student grants a CISO group to another account (IDOR on res.users)."""
        manager_group = self.env.ref("university_isms.group_isms_manager")
        with self.assertRaises(AccessError):
            self.reporter_a.with_user(self.student_a).write({"groups_id": [Command.link(manager_group.id)]})
        self.assertFalse(self.reporter_a.sudo().has_group("university_isms.group_isms_manager"))

    def test_03_user_cannot_create_users(self):
        """Attack: a plain user creates a new account with a privileged group (account injection)."""
        admin_group = self.env.ref("base.group_system")
        with self.assertRaises(AccessError):
            self.env["res.users"].with_user(self.normal).create({
                "name": "Injected", "login": "sec_injected", "groups_id": [Command.set([admin_group.id])]})
        self.assertFalse(self.env["res.users"].sudo().search([("login", "=", "sec_injected")]))

    def test_04_user_cannot_write_acl_or_record_rules(self):
        """Attack: a plain user inserts an ir.model.access row or edits an ir.rule to widen access."""
        model = self.env["ir.model"].search([("model", "=", "isms.incident")], limit=1)
        with self.assertRaises(AccessError):
            self.env["ir.model.access"].with_user(self.normal).create({
                "name": "sec injected", "model_id": model.id, "group_id": self.normal.groups_id[:1].id,
                "perm_read": True, "perm_write": True, "perm_create": True, "perm_unlink": True})
        rule = self.env.ref("university_isms.rule_incident_reporter")
        with self.assertRaises(AccessError):
            rule.with_user(self.normal).write({"active": False})
        self.assertTrue(rule.sudo().active)

    def test_05_user_cannot_apply_access_review(self):
        """Attack: a non-manager calls access.review action_apply_groups to grant himself rights,
        and opens the review screen of another user (res.users action_open_access_review)."""
        review = self.env["access.review"].create({"user_id": self.reporter_a.id})  # setup as superuser
        with self.assertRaises(AccessError):
            self.env["access.review"].with_user(self.normal).create({"user_id": self.normal.id})
        with self.assertRaises(AccessError):
            review.with_user(self.normal).action_apply_groups()
        with self.assertRaises(AccessError):
            self.reporter_a.with_user(self.normal).action_open_access_review()
        self.assertFalse(self.normal.sudo().has_group("university_isms.group_isms_manager"))

    # ------------------------------------------------------------------- IDOR
    def test_06_student_cannot_read_other_students_grade(self):
        """Attack: student A reads enrollment id of student B and its confirmed score (IDOR)."""
        with self.assertRaises(AccessError):
            self.enr_b.with_user(self.student_a).score
        self.assertEqual(self.env["campus.enrollment"].with_user(self.student_a).search(
            [("id", "=", self.enr_b.id)]).ids, [])

    def test_07_lecturer_cannot_read_other_roster(self):
        """Attack: lecturer A enumerates enrollments and students of offering B (roster IDOR)."""
        self.assertEqual(self.env["campus.offering"].with_user(self.lecturer_a).search(
            [("id", "=", self.offering_b.id)]).ids, [])
        self.assertEqual(self.env["campus.enrollment"].with_user(self.lecturer_a).search(
            [("offering_id", "=", self.offering_b.id)]).ids, [])
        with self.assertRaises(AccessError):
            self.offering_b.with_user(self.lecturer_a).name

    def test_08_reporter_cannot_read_other_incident(self):
        """Attack: reporter A reads incident code/name of reporter B by guessing its id (IDOR)."""
        self.assertEqual(self.env["isms.incident"].with_user(self.reporter_a).search(
            [("id", "=", self.incident_b.id)]).ids, [])
        with self.assertRaises(AccessError):
            self.incident_b.with_user(self.reporter_a).name

    def test_09_owner_cannot_write_other_owners_asset(self):
        """Attack: asset owner A renames or re-owns asset B (IDOR on write)."""
        with self.assertRaises(AccessError):
            self.asset_b.with_user(self.owner_a).write({"name": "hijacked"})
        with self.assertRaises(AccessError):
            self.asset_b.with_user(self.owner_a).write({"owner_id": self.owner_a.id})
        self.assertEqual(self.asset_b.sudo().name, "Asset Bravo SEC")

    def test_10_search_read_group_export_name_search_do_not_leak(self):
        """Attack: a student uses search_count, read_group, export_data and name_search
        to learn the existence, score or name of another student's records (side channels)."""
        student = self.env["campus.enrollment"].with_user(self.student_a)
        self.assertEqual(student.search_count([]), 1, "count must cover only own enrollment")
        groups = student._read_group([], groupby=[], aggregates=["score:sum", "__count"])
        self.assertEqual(groups[0][1], 1, "read_group count leaks other rows")
        self.assertAlmostEqual(groups[0][0], 55.0, places=2, msg="read_group sum leaks other scores")
        try:
            values = _export_values(self.env["campus.enrollment"].with_user(self.student_a)
                                    .browse(self.enr_b.id), ["score"])
        except DENIED:
            values = []
        self.assertNotIn("61.0", values, "export_data leaks another student's score")
        names = self.env["campus.student"].with_user(self.student_a).name_search("Bravo")
        self.assertEqual(names, [], "name_search leaks another student's name")
        inc_names = self.env["isms.incident"].with_user(self.reporter_a).name_search("SEC-IDOR")
        self.assertEqual(inc_names, [], "incident name_search leaks another reporter's incident")

    # ------------------------------------------------ self-approval, stale revision
    def test_11_requester_cannot_approve_own_grade_change(self):
        """Attack: a registrar who requested a grade change approves it (self-approval)."""
        change = self.env["campus.grade.change"].with_user(self.registrar).create({
            "enrollment_id": self.enr_a.id, "proposed_score": 70.0,
            "reason": "Self-approval attack fixture reason"})
        change.with_user(self.registrar).action_submit()
        with self.assertRaises(AccessError):
            change.with_user(self.registrar).action_approve()
        self.assertEqual(self.enr_a.sudo().score, 55.0)

    def test_12_lecturer_cannot_approve_grade_change(self):
        """Attack: the lecturer who requested a grade change approves it to bypass the registrar."""
        change = self.env["campus.grade.change"].with_user(self.lecturer_a).create({
            "enrollment_id": self.enr_a.id, "proposed_score": 72.0,
            "reason": "Lecturer self-approval attack fixture"})
        change.with_user(self.lecturer_a).action_submit()
        with self.assertRaises(AccessError):
            change.with_user(self.lecturer_a).action_approve()
        self.assertEqual(change.sudo().state, "submitted")

    def test_13_stale_revision_rejected(self):
        """Attack: two grade changes are prepared on the same score; after the first is applied,
        the second (stale old_revision and old_score) must not overwrite the newer grade."""
        Change = self.env["campus.grade.change"].with_user(self.lecturer_a)
        first = Change.create({"enrollment_id": self.enr_a.id, "proposed_score": 80.0,
                               "reason": "First stale revision fixture"})
        second = Change.create({"enrollment_id": self.enr_a.id, "proposed_score": 40.0,
                                "reason": "Second stale revision fixture"})
        first.with_user(self.lecturer_a).action_submit()
        second.with_user(self.lecturer_a).action_submit()
        first.with_user(self.registrar).action_approve()
        self.assertEqual(self.enr_a.sudo().grade_revision, 1)
        with self.assertRaises(ValidationError):
            second.with_user(self.registrar).action_approve()
        self.assertEqual(self.enr_a.sudo().score, 80.0)

    def test_14_direct_score_write_bypasses_nothing(self):
        """Attack: lecturer, registrar, or a forged context flag writes score or grade_revision
        directly on the enrollment, skipping the grade-change approval."""
        with self.assertRaises(AccessError):
            self.enr_a.with_user(self.lecturer_a).write({"score": 100.0})
        with self.assertRaises(AccessError):
            self.enr_a.with_user(self.registrar).write({"score": 100.0})
        with self.assertRaises(AccessError):
            self.enr_a.with_user(self.registrar).write({"grade_revision": 9})
        with self.assertRaises(AccessError):
            self.enr_a.with_user(self.lecturer_a).with_context(
                _campus_grade_authority=True).write({"score": 100.0})
        with self.assertRaises(AccessError):
            self.enr_a.with_user(self.student_a).write({"score": 100.0})
        self.assertEqual(self.enr_a.sudo().score, 55.0)

    # --------------------------------------------- ISMS workflow self-approval
    def test_15_incident_close_by_non_ciso_refused(self):
        """Attack: an analyst or the reporter closes a resolved incident (close needs CISO)."""
        inc = self._incident_in_state("resolve", self.reporter_a)
        with self.assertRaises(AccessError):
            inc.with_user(self.analyst).action_close()
        with self.assertRaises(AccessError):
            inc.with_user(self.analyst).write({"state": "close"})
        with self.assertRaises(UserError):
            inc.with_user(self.reporter_a).write({"state": "close"})
        self.assertEqual(inc.sudo().state, "resolve")

    def test_16_policy_approve_by_non_ciso_refused(self):
        """Attack: the analyst who submitted a policy also approves it (self-approval)."""
        policy = self.env["isms.policy"].with_user(self.analyst).create({"name": "SEC policy fixture"})
        policy.with_user(self.analyst).action_submit()
        with self.assertRaises(AccessError):
            policy.with_user(self.analyst).action_approve()
        with self.assertRaises(AccessError):
            policy.with_user(self.auditor).action_approve()
        self.assertNotEqual(policy.sudo().state, "approved")

    def test_17_risk_accept_by_non_ciso_refused(self):
        """Attack: an analyst or the asset owner accepts a risk, or forges accepted_by_id."""
        risk = self.env["isms.risk"].with_user(self.analyst).create({
            "name": "SEC risk fixture", "asset_ids": [Command.set(self.asset_a.ids)],
            "threat_id": self.threat.id, "vulnerability_id": self.vuln.id,
            "likelihood": "3", "impact": "3"})
        risk.sudo().write({"state": "evaluate"})
        with self.assertRaises(AccessError):
            risk.with_user(self.analyst).action_accept_risk()
        with self.assertRaises(AccessError):
            risk.with_user(self.owner_a).action_accept_risk()
        with self.assertRaises(UserError):
            risk.with_user(self.analyst).write({"accepted_by_id": self.analyst.id})
        self.assertFalse(risk.sudo().accepted_by_id)

    # ----------------------------------------- direct write/unlink, timestamps
    def test_18_protected_incident_timestamps_not_writable(self):
        """Attack: a reporter or analyst back-dates reported_at, resolved_at or closed_at via RPC,
        and forges the internal workflow token through the context."""
        inc = self.env["isms.incident"].with_user(self.reporter_a).create({"name": "Timestamp fixture"})
        before = inc.sudo().reported_at
        with self.assertRaises(AccessError):
            inc.with_user(self.reporter_a).write({"reported_at": "2020-01-01 00:00:00"})
        with self.assertRaises(AccessError):
            inc.with_user(self.analyst).write({"resolved_at": "2020-01-01 00:00:00"})
        with self.assertRaises(AccessError):
            inc.with_user(self.ciso).write({"closed_at": "2020-01-01 00:00:00"})
        with self.assertRaises(AccessError):
            inc.with_user(self.reporter_a).with_context(isms_transition=True).write(
                {"reported_at": "2020-01-01 00:00:00"})
        self.assertEqual(inc.sudo().reported_at, before, "protected timestamp changed")

    def test_19_incident_unlink_refused_for_reporter_and_analyst(self):
        """Attack: a reporter or analyst deletes an incident record to erase evidence."""
        inc = self.env["isms.incident"].with_user(self.reporter_a).create({"name": "Unlink fixture"})
        with self.assertRaises(AccessError):
            inc.with_user(self.reporter_a).unlink()
        with self.assertRaises(AccessError):
            inc.with_user(self.analyst).unlink()
        self.assertTrue(inc.exists())

    def test_20_audit_log_write_and_unlink_refused(self):
        """Attack: a CISO, an auditor, or an admin-equivalent superuser edits or deletes audit rows
        to hide an action (ORM-level immutability; DB-level tamper evidence is NOT covered here)."""
        self.assertTrue(self.env["isms.audit.log"].sudo().search_count([]) > 0)
        log = self.env["isms.audit.log"].sudo().search([], limit=1)
        for user in (self.ciso, self.auditor):
            with self.assertRaises(UserError):
                log.with_user(user).write({"changes": "rewritten"})
            with self.assertRaises(UserError):
                log.with_user(user).unlink()
        with self.assertRaises(UserError):
            log.sudo().write({"changes": "rewritten"})
        with self.assertRaises(UserError):
            log.sudo().unlink()

    # ------------------------------------------------- CSRF and route review
    def _source_route_inventory(self):
        """Parse every custom addon source file (AST, no import) and collect each http.route call."""
        inventory = []
        for name in odoo.modules.get_modules():
            path = odoo.modules.module.get_module_path(name) or ""
            if CUSTOM_ADDON_MARKER not in path:
                continue
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", "static")]
                for fname in files:
                    if not fname.endswith(".py"):
                        continue
                    fpath = os.path.join(root, fname)
                    with open(fpath, encoding="utf-8") as fh:
                        tree = ast.parse(fh.read(), fpath)
                    for node in ast.walk(tree):
                        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                                and node.func.attr == "route"):
                            continue
                        kw = {k.arg: (k.value.value if isinstance(k.value, ast.Constant) else None)
                              for k in node.keywords if k.arg}
                        methods = None
                        for k in node.keywords:
                            if k.arg == "methods" and isinstance(k.value, (ast.List, ast.Tuple)):
                                methods = [e.value for e in k.value.elts if isinstance(e, ast.Constant)]
                        inventory.append({
                            "module": name, "file": os.path.relpath(fpath, path),
                            "line": node.lineno, "type": kw.get("type", "http"),
                            "auth": kw.get("auth", "user"), "csrf": kw.get("csrf", True),
                            "methods": methods, "website": kw.get("website", False),
                        })
        return inventory

    def test_21_custom_http_routes_keep_csrf_enabled(self):
        """Attack: cross-site request forgery against a state-changing route that disables the
        CSRF token (csrf=False) while accepting POST with auth='user' or auth='public'.
        Inventory: every http.route call in the custom addons (AST scan of the source), and the
        routes of installed modules from the Odoo routing generator."""
        inventory = self._source_route_inventory()
        self.assertTrue(inventory, "route inventory is empty: the scan did not find any http.route")
        for entry in inventory:
            _logger.info("SEC-04 route %(module)s %(file)s:%(line)s type=%(type)s auth=%(auth)s "
                         "csrf=%(csrf)s methods=%(methods)s", entry)
        findings = [e for e in inventory
                    if e["type"] == "http" and e["csrf"] is False and e["auth"] in ("user", "public")
                    and (e["methods"] is None or "POST" in e["methods"])]
        self.assertEqual(findings, [], "http routes with csrf=False that accept POST: %s" % findings)

    # ---------------------------------------------------------- sensitive exports
    def test_22_export_of_users_hides_password_and_totp(self):
        """Attack: a normal user exports res.users rows (export_data or read) to collect password
        hashes and TOTP seeds of other accounts (sensitive-data export)."""
        fields = ["login", "password"]
        if "totp_secret" in self.env["res.users"]._fields:
            fields.append("totp_secret")
            self.env.cr.execute("UPDATE res_users SET totp_secret = %s WHERE id = %s",
                                ["SECTESTSEED", self.owner_b.id])
        secrets = [self._stored_password_hash(u) for u in (self.owner_b, self.reporter_b)]
        secrets = [s for s in secrets if s]
        self.assertTrue(secrets, "fixture passwords must be hashed in res_users")
        targets = self.env["res.users"].with_user(self.normal).browse([self.owner_b.id, self.reporter_b.id])
        try:
            exported = _export_values(targets, fields)
        except DENIED:
            exported = []
        for value in exported:
            for secret in secrets + (["SECTESTSEED"] if "totp_secret" in fields else []):
                self.assertNotIn(secret, value, "export leaks a credential field")
        self.assertNotIn("SECTESTSEED", str(exported), "export leaks TOTP seed")
        try:
            read_rows = self.owner_b.with_user(self.normal).read(fields)
        except AccessError:
            read_rows = []
        self.assertNotIn(secrets[0], str(read_rows), "read() leaks password hash to a normal user")
