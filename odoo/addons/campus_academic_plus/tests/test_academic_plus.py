from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "campus_academic_plus")
class TestCampusAcademicPlus(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.users = {}
        for login, group in [
            ("lecturer", "group_campus_lecturer"),
            ("other_lecturer", "group_campus_lecturer"),
            ("registrar", "group_campus_registrar"),
            ("auditor", "group_campus_auditor"),
            ("student_a", "group_campus_student"),
            ("student_b", "group_campus_student"),
            ("student_c", "group_campus_student"),
        ]:
            cls.users[login] = Users.create({
                "name": "ACP test " + login,
                "login": "acp.test." + login,
                "groups_id": [Command.set([cls.env.ref("campus_university." + group).id])],
            })
        cls.program = cls.env["campus.program"].create({
            "code": "ACP-PROG", "name": "ACP test program", "department": "ACP test dept",
            "required_credits": 10,
        })
        cls.students = {}
        for key, letter in [("student_a", "A"), ("student_b", "B"), ("student_c", "C")]:
            cls.students[key] = cls.env["campus.student"].create({
                "student_code": "ACP-S" + letter, "name": "ACP student " + letter,
                "user_id": cls.users[key].id, "program_id": cls.program.id,
            })
        cls.course_base = cls.env["campus.course"].create({
            "code": "ACP-101", "name": "Base", "credits": 3, "program_id": cls.program.id,
        })
        cls.course_other = cls.env["campus.course"].create({
            "code": "ACP-102", "name": "Other", "credits": 4, "program_id": cls.program.id,
        })
        cls.course_adv = cls.env["campus.course"].create({
            "code": "ACP-201", "name": "Advanced", "credits": 3, "program_id": cls.program.id,
            "prerequisite_ids": [Command.set([cls.course_base.id])],
        })
        cls.today = fields.Date.context_today(cls.env.user)
        cls.term = cls._make_term("ACP-T1", cls.today - timedelta(days=5), cls.today + timedelta(days=10),
                                  cls.today + timedelta(days=20))
        cls.off_base = cls._make_offering(cls.course_base, cls.users["lecturer"], cls.term)
        cls.off_other = cls._make_offering(cls.course_other, cls.users["other_lecturer"], cls.term)
        cls.off_adv = cls._make_offering(cls.course_adv, cls.users["lecturer"], cls.term)

    @classmethod
    def _make_term(cls, code, reg_start, reg_end, add_drop_end, date_start=None, date_end=None):
        return cls.env["campus.academic.term"].create({
            "name": "Term " + code, "code": code,
            "date_start": date_start or cls.today - timedelta(days=60),
            "date_end": date_end or cls.today + timedelta(days=120),
            "registration_start": reg_start, "registration_end": reg_end,
            "add_drop_end": add_drop_end, "state": "open",
        })

    @classmethod
    def _make_offering(cls, course, lecturer, term, capacity=10):
        return cls.env["campus.offering"].create({
            "name": "Offering " + course.code + " " + term.code, "course_id": course.id,
            "semester": term.code, "lecturer_id": lecturer.id, "state": "open",
            "term_id": term.id, "capacity": capacity,
        })

    def _register(self, user_key, offering, student_key=None):
        student = self.students[student_key or user_key]
        return offering.with_user(self.users[user_key]).register_student(student)

    def _enroll_direct(self, student_key, offering, score=0, reg_state="enrolled"):
        return self.env["campus.enrollment"].create({
            "student_id": self.students[student_key].id, "offering_id": offering.id,
            "score": score, "reg_state": reg_state,
        })

    def _session(self, offering, start, end, room=False):
        return self.env["campus.session"].create({
            "offering_id": offering.id, "start": start, "end": end, "room": room, "kind": "lecture",
        })

    # Registration -------------------------------------------------------

    def test_registration_happy_path(self):
        enrollment = self._register("student_a", self.off_base)
        self.assertEqual(enrollment.reg_state, "enrolled")
        self.assertEqual(enrollment.registered_by_id, self.users["student_a"])
        self.assertEqual(enrollment.student_id, self.students["student_a"])
        self.assertEqual(self.off_base.seats_taken, 1)
        self.assertEqual(self.off_base.seats_left, 9)

    def test_capacity_full(self):
        small = self._make_offering(self.course_other, self.users["other_lecturer"], self.term, capacity=1)
        self._register("student_a", small)
        with self.assertRaises(UserError):
            self._register("student_b", small)
        self.assertEqual(small.seats_taken, 1)
        self.assertEqual(small.seats_left, 0)

    def test_open_offering_requires_capacity(self):
        with self.assertRaises(ValidationError):
            self._make_offering(self.course_other, self.users["other_lecturer"], self.term, capacity=0)

    def test_prerequisite_missing_and_failing_grade(self):
        with self.assertRaises(UserError):
            self._register("student_a", self.off_adv)
        self._enroll_direct("student_a", self.off_base, score=40, reg_state="completed")
        with self.assertRaises(UserError):
            self._register("student_a", self.off_adv)
        self._enroll_direct("student_b", self.off_base, score=72, reg_state="completed")
        enrollment = self._register("student_b", self.off_adv)
        self.assertEqual(enrollment.reg_state, "enrolled")

    def test_outside_registration_window(self):
        past_term = self._make_term("ACP-T0", self.today - timedelta(days=30), self.today - timedelta(days=20),
                                    self.today - timedelta(days=10), date_start=self.today - timedelta(days=60),
                                    date_end=self.today - timedelta(days=5))
        past_off = self._make_offering(self.course_other, self.users["other_lecturer"], past_term)
        with self.assertRaises(UserError):
            self._register("student_a", past_off)

    def test_credit_limit_per_term(self):
        heavies = [self.env["campus.course"].create({
            "code": "ACP-30%d" % i, "name": "Heavy %d" % i, "credits": 6, "program_id": self.program.id,
        }) for i in range(1, 4)]
        for course in heavies:
            self._register("student_a", self._make_offering(course, self.users["lecturer"], self.term))
        # 18 credits used; a 3-credit course reaches exactly 21 and is allowed.
        self._register("student_a", self.off_base)
        with self.assertRaises(UserError):
            self._register("student_a", self.off_other)

    def test_timetable_clash(self):
        self._session(self.off_base, datetime(2030, 1, 7, 10, 0), datetime(2030, 1, 7, 11, 0), room="ACP-R1")
        self._session(self.off_other, datetime(2030, 1, 7, 10, 30), datetime(2030, 1, 7, 11, 30), room="ACP-R2")
        self._register("student_a", self.off_base)
        with self.assertRaises(UserError):
            self._register("student_a", self.off_other)

    def test_duplicate_registration(self):
        self._register("student_a", self.off_base)
        with self.assertRaises(UserError):
            self._register("student_a", self.off_base)
        self.assertEqual(self.off_base.seats_taken, 1)

    def test_student_cannot_register_someone_else(self):
        with self.assertRaises(AccessError):
            self._register("student_a", self.off_base, student_key="student_b")
        self.assertEqual(self.off_base.seats_taken, 0)

    def test_registrar_can_register_any_student(self):
        enrollment = self._register("registrar", self.off_base, student_key="student_c")
        self.assertEqual(enrollment.student_id, self.students["student_c"])
        self.assertEqual(enrollment.registered_by_id, self.users["registrar"])

    def test_drop_within_and_after_add_drop(self):
        enrollment = self._register("student_a", self.off_base)
        with self.assertRaises(AccessError):
            enrollment.with_user(self.users["student_b"]).action_drop()
        with self.assertRaises(AccessError):
            enrollment.with_user(self.users["lecturer"]).action_drop()
        enrollment.with_user(self.users["student_a"]).action_drop()
        enrollment.invalidate_recordset()
        self.assertEqual(enrollment.reg_state, "dropped")
        self.assertEqual(enrollment.dropped_by_id, self.users["student_a"])
        self.assertTrue(self.env["campus.enrollment"].search([("id", "=", enrollment.id)]))
        self.assertEqual(self.off_base.seats_taken, 0)
        again = self._register("student_a", self.off_base)
        self.assertEqual(again, enrollment)
        self.assertEqual(again.reg_state, "enrolled")

        self.term.write({
            "registration_start": self.today - timedelta(days=30),
            "registration_end": self.today - timedelta(days=20),
            "add_drop_end": self.today - timedelta(days=10),
        })
        with self.assertRaises(UserError):
            again.with_user(self.users["student_a"]).action_drop()

    # Sessions and attendance -------------------------------------------

    def test_session_room_and_lecturer_overlap(self):
        self._session(self.off_base, datetime(2030, 2, 4, 9, 0), datetime(2030, 2, 4, 10, 0), room="ACP-R9")
        with self.assertRaises(ValidationError):
            self._session(self.off_other, datetime(2030, 2, 4, 9, 30), datetime(2030, 2, 4, 10, 30), room="ACP-R9")
        with self.assertRaises(ValidationError):
            self._session(self.off_adv, datetime(2030, 2, 4, 9, 30), datetime(2030, 2, 4, 10, 30), room="ACP-R10")

    def test_attendance_only_by_own_lecturer(self):
        session = self._session(self.off_base, datetime(2030, 3, 4, 9, 0), datetime(2030, 3, 4, 10, 0))
        enrollment = self._register("student_a", self.off_base)
        att = self.env["campus.attendance"]
        with self.assertRaises(AccessError):
            att.with_user(self.users["other_lecturer"]).record(session, enrollment, "present")
        with self.assertRaises(AccessError):
            att.with_user(self.users["student_a"]).record(session, enrollment, "present")
        record = att.with_user(self.users["lecturer"]).record(session, enrollment, "present")
        self.assertEqual(record.recorded_by, self.users["lecturer"])
        self.assertTrue(record.recorded_at)
        again = att.with_user(self.users["registrar"]).record(session, enrollment, "late")
        self.assertEqual(again, record)
        self.assertEqual(again.status, "late")

    def test_attendance_rate(self):
        enrollment = self._register("student_a", self.off_base)
        statuses = ["present", "late", "absent", "excused"]
        for day, status in enumerate(statuses, start=1):
            session = self._session(self.off_base, datetime(2030, 4, day, 9, 0), datetime(2030, 4, day, 10, 0))
            self.env["campus.attendance"].with_user(self.users["lecturer"]).record(session, enrollment, status)
        enrollment.invalidate_recordset()
        # present + late over (present + late + absent); excused is excluded from the denominator.
        self.assertAlmostEqual(enrollment.attendance_rate, 66.67, places=2)

    # Grades, GPA, graduation ------------------------------------------

    def test_letter_grade_and_weighted_gpa(self):
        course_heavy = self.env["campus.course"].create({
            "code": "ACP-390", "name": "Heavy fail", "credits": 6, "program_id": self.program.id,
        })
        e_base = self._enroll_direct("student_a", self.off_base, score=95, reg_state="completed")
        e_other = self._enroll_direct("student_a", self.off_other, score=75, reg_state="completed")
        e_fail = self._enroll_direct("student_a", self._make_offering(course_heavy, self.users["lecturer"], self.term),
                                     score=40, reg_state="completed")
        self.assertEqual(e_base.letter_grade, "A")
        self.assertEqual(e_other.letter_grade, "C")
        self.assertEqual(e_fail.letter_grade, "F")
        self.assertEqual(e_fail.grade_point, 0.0)
        student = self.students["student_a"].with_user(self.users["student_a"])
        # (4.0 * 3 + 2.0 * 4 + 0.0 * 6) / 13 = 1.54; the failed course adds credits to GPA but not to earned credits.
        self.assertAlmostEqual(student.gpa, 1.54, places=2)
        self.assertEqual(student.credits_earned, 7)

    def test_in_progress_enrollment_has_no_letter_grade(self):
        enrollment = self._enroll_direct("student_b", self.off_base, score=0)
        self.assertFalse(enrollment.letter_grade)
        self.assertEqual(enrollment.grade_point, 0.0)

    def test_graduation_eligibility_and_missing_text(self):
        self._enroll_direct("student_a", self.off_base, score=80, reg_state="completed")
        self._enroll_direct("student_a", self.off_other, score=75, reg_state="completed")
        student = self.students["student_a"]
        self.assertFalse(student.graduation_eligible)
        self.assertIn("7 / 10", student.graduation_missing)
        self.assertIn("3", student.graduation_missing)
        course_extra = self.env["campus.course"].create({
            "code": "ACP-391", "name": "Extra", "credits": 6, "program_id": self.program.id,
        })
        self._enroll_direct("student_a", self._make_offering(course_extra, self.users["lecturer"], self.term),
                            score=70, reg_state="completed")
        student.invalidate_recordset()
        self.assertEqual(student.credits_earned, 13)
        self.assertTrue(student.graduation_eligible)

    def test_transcript_only_own(self):
        self._enroll_direct("student_a", self.off_base, score=80, reg_state="completed")
        action = self.students["student_a"].with_user(self.users["student_a"]).action_transcript()
        self.assertEqual(action["type"], "ir.actions.report")
        self.assertEqual(action["report_name"], "campus_academic_plus.report_transcript_document")
        with self.assertRaises(AccessError):
            self.students["student_a"].with_user(self.users["student_b"]).action_transcript()
        with self.assertRaises(AccessError):
            self.students["student_a"].with_user(self.users["lecturer"]).action_transcript()
        registrar_action = self.students["student_a"].with_user(self.users["registrar"]).action_transcript()
        self.assertEqual(registrar_action["type"], "ir.actions.report")

    def test_completion_is_registrar_only(self):
        enrollment = self._register("student_a", self.off_base)
        with self.assertRaises(AccessError):
            enrollment.with_user(self.users["student_a"]).action_complete()
        with self.assertRaises(AccessError):
            enrollment.with_user(self.users["lecturer"]).action_complete()
        enrollment.with_user(self.users["registrar"]).action_complete()
        self.assertEqual(enrollment.reg_state, "completed")

    # Record rules and write protection --------------------------------

    def test_record_rules_isolate_students_and_lecturers(self):
        e_b = self._register("student_b", self.off_base)
        session = self._session(self.off_base, datetime(2030, 5, 6, 9, 0), datetime(2030, 5, 6, 10, 0))
        self.env["campus.attendance"].with_user(self.users["lecturer"]).record(session, e_b, "present")
        Enrollment = self.env["campus.enrollment"]
        self.assertFalse(Enrollment.with_user(self.users["student_a"]).search([("id", "=", e_b.id)]))
        self.assertFalse(self.env["campus.attendance"].with_user(self.users["student_a"]).search([]))
        self.assertTrue(self.env["campus.attendance"].with_user(self.users["student_b"]).search([]))
        self.assertFalse(self.env["campus.session"].with_user(self.users["other_lecturer"]).search(
            [("offering_id", "=", self.off_base.id)]))
        self.assertTrue(self.env["campus.session"].with_user(self.users["lecturer"]).search(
            [("offering_id", "=", self.off_base.id)]))
        self.assertTrue(self.env["campus.attendance"].with_user(self.users["registrar"]).search([]))
        self.assertTrue(self.env["campus.attendance"].with_user(self.users["auditor"]).search([]))

    def test_score_and_status_not_writable_by_student_or_lecturer(self):
        enrollment = self._enroll_direct("student_a", self.off_base, score=50)
        with self.assertRaises(AccessError):
            enrollment.with_user(self.users["student_a"]).write({"score": 100})
        with self.assertRaises(AccessError):
            enrollment.with_user(self.users["lecturer"]).write({"score": 100})
        with self.assertRaises(AccessError):
            enrollment.with_user(self.users["student_a"]).write({"reg_state": "completed"})
        with self.assertRaises(AccessError):
            enrollment.with_user(self.users["lecturer"]).write({"reg_state": "completed"})
        enrollment.invalidate_recordset()
        self.assertEqual(enrollment.score, 50)
        self.assertEqual(enrollment.reg_state, "enrolled")

    def test_single_active_policy(self):
        policy = self.env["campus.academic.policy"].search([("active", "=", True)])
        self.assertEqual(len(policy), 1)
        with self.assertRaises(ValidationError):
            self.env["campus.academic.policy"].create({"name": "Second active"})
