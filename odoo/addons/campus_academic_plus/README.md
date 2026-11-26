# Formula Campus — Academic Plus

Odoo 18 Community addon on top of `campus_university`. It adds academic terms,
registration with server-side checks, sessions (timetable), attendance,
grade letters, GPA, credits, graduation eligibility and a PDF transcript.

## Configuration

Menu **Formula Campus > Академик бодлого** (registrar only) holds the single active
policy: pass score (default 60), maximum credits per term (default 21), minimum
graduation GPA (default 0, meaning no GPA requirement) and grade scale lines
(A 90, B 80, C 70, D 60, F 0 with grade points 4.0 / 3.0 / 2.0 / 1.0 / 0.0).
These are configurable assumptions, not official university policy.

## Rules enforced on the server

- Registration (`campus.offering.register_student`): the student may register only
  themself; a registrar may register anyone. Checks: active student, term
  registration window, offering open, no duplicate active enrollment, seats left,
  prerequisites completed with score at or above the pass score, term credit limit,
  and no timetable clash with the student's other active offerings. A dropped
  enrollment is reactivated instead of duplicated.
- Drop (`campus.enrollment.action_drop`): the student or a registrar, only up to the
  term add/drop end date. Records are marked `dropped`, never deleted.
- Completion (`action_complete`): registrar only. Letter grade and grade point are
  computed only for completed enrollments; GPA and earned credits use completed ones.
- Attendance (`campus.attendance.record`): the offering's lecturer or a registrar only.
  Attendance rate = (present + late) / (all non-excused records).
- Transcript (`campus.student.action_transcript`): the student for own record, or a registrar.
- Sessions reject overlaps per room and per lecturer.
- Score and grade-change rules from `campus_university` are unchanged.

## Access

Students read only their own enrollments, attendance and transcript data, and open
offerings for registration. Lecturers read sessions and attendance of their own
offerings. Registrars manage terms, sessions, attendance and policy. The auditor
reads everything in read-only mode. GPA, credits and graduation fields are visible
only to students (own), registrars and auditors.
