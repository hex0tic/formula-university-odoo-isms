"""Load a fictional Formula Campus cohort through Odoo 18 shell.

Only orgil_isms_stage is allowed. The default run rolls back all ORM changes.
Set FORMULA_CAMPUS_APPLY=1 to commit. On first apply, supply distinct passwords
of at least 16 characters in FORMULA_CAMPUS_STUDENT_PASSWORD and
FORMULA_CAMPUS_TEACHER_PASSWORD. Later runs leave both passwords alone.

Use the staging Odoo container and pass this file on stdin, for example:
    docker exec -i isms-stage-odoo /entrypoint.sh odoo shell \
        -c /etc/odoo/odoo.conf -d orgil_isms_stage --no-http < seed_formula_campus.py

Rerun to fill in attendance for elapsed sessions and schedule upcoming weeks.
The shell imports the fictional roster and baseline grades through the registrar
ORM path. Grade approvals and historical actor timestamps are left empty.
"""

import os
import secrets
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from random import Random
from zoneinfo import ZoneInfo

from odoo import Command


DATABASE = "orgil_isms_stage"
NAMESPACE = "formula_campus_cohort_seed"
LEGACY_PREFIX = "[ДЭМО · ЗОХИОМОЛ] "
TIMEZONE = ZoneInfo("Asia/Ulaanbaatar")
DOMAIN = "formula-campus.example"
STUDENT_LOGIN = f"student@{DOMAIN}"
TEACHER_LOGIN = f"teacher@{DOMAIN}"
NO_MAIL = {
    "no_reset_password": True,
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_create_nosubscribe": True,
    "mail_notify_force_send": False,
}

# Each program has three teaching staff, two completed courses, and three
# current courses. All names are constructed for this fictional cohort.
PROGRAMS = (
    (
        "CY", "Кибер аюулгүй байдал", "Тооцоолол, программ хангамжийн сургууль",
        ("Чимэдийн Саруултөгс", "Наранбаатарын Энхмөрөн", "Гомбосүрэнгийн Тэмүүлэн"),
        ("Мэдээллийн технологийн үндэс", "Үйлдлийн системийн үндэс"),
        ("Компьютерын сүлжээ", "Кибер аюулгүй байдлын удирдлага", "Системийн хамгаалалтын дадлага"),
    ),
    (
        "BA", "Бизнесийн өгөгдлийн шинжилгээ", "Хэрэглээний шинжлэх ухааны сургууль",
        ("Буяндэлгэрийн Мөнхжин", "Даваасүрэнгийн Сайнбилэг", "Цэрэндоржийн Хонгорзул"),
        ("Бизнесийн статистикийн үндэс", "Өгөгдлийн сан ба SQL"),
        ("Бизнесийн үзүүлэлтийн шинжилгээ", "Өгөгдлийн дүрслэл ба тайлагнал", "Борлуулалтын таамаглал"),
    ),
    (
        "DD", "Дижитал бүтээгдэхүүний дизайн", "Дизайн, бүтээлч технологийн сургууль",
        ("Батнасангийн Ариунсанаа", "Эрдэнэбатадын Чинхүслэн", "Лувсанпүрэвийн Нандинзаяа"),
        ("Визуал дизайны үндэс", "Хэрэглэгчийн судалгааны үндэс"),
        ("Харилцан үйлдлийн дизайн", "Интерфейсийн загвар ба прототип", "Хэрэглээний хялбар байдлын туршилт"),
    ),
)
PATRONYMICS = (
    "Алтангэрэлийн", "Баярсайханы", "Даваадоржийн", "Эрдэнэбатын", "Ганболдын", "Жаргалсайханы",
    "Хүрэлбаатарын", "Лхагвасүрэнгийн", "Мөнхбатын", "Нямдоржийн", "Очирбатын", "Пүрэвсүрэнгийн",
    "Сүхбаатарын", "Төмөрбаатарын", "Уламбаярын", "Цогтбаатарын", "Чулуунбаатарын", "Энхбаярын",
    "Баттулгын", "Дэлгэрсайханы", "Гантөмөрийн", "Наранцэцэгийн", "Отгонбаатарын", "Санжаагийн",
)
GIVEN_NAMES = (
    "Ану", "Билгүүн", "Ариунзаяа", "Ган-Эрдэнэ", "Энхжин", "Төгөлдөр",
    "Индра", "Тэмүүжин", "Марал", "Мөнх-Оргил", "Номин", "Эрдэнэсүх",
    "Оюундарь", "Содбилэг", "Уянга", "Түвшинбаяр", "Хулан", "Энхтүшиг",
    "Цэлмэг", "Шинэбаяр", "Мишээл", "Ананд", "Сондор", "Ирээдүй",
)
STUDENTS_PER_PROGRAM = 24
CAPACITY = 30
CREDITS = 3
MEETINGS = (
    ((0, time(9, 0), "lecture"), (3, time(10, 40), "lab")),
    ((1, time(10, 40), "lecture"), (4, time(9, 0), "lab")),
    ((2, time(9, 0), "lecture"), (4, time(10, 40), "seminar")),
)


def monday(day):
    return day - timedelta(days=day.weekday())


def normalize_existing_cohort(orm):
    """Clean labels only on records owned by this script's XML IDs."""
    names = {"res.users", "campus.academic.term", "campus.program", "campus.student",
             "campus.course", "campus.offering"}
    codes = {"campus.academic.term": "code", "campus.program": "code",
             "campus.student": "student_code", "campus.course": "code"}
    models = names | {"campus.session", "campus.grade.change"}
    updated = 0
    data = orm["ir.model.data"].search([("module", "=", NAMESPACE), ("model", "in", sorted(models))])
    for row in data:
        record = orm[row.model].browse(row.res_id).exists()
        if not record:
            continue
        values = {}
        if row.model in names and (record.name or "").startswith(LEGACY_PREFIX):
            name = record.name.removeprefix(LEGACY_PREFIX)
            if row.model == "campus.offering":
                name = name.replace("DEMO-FC-", "FU-", 1)
            values["name"] = name
        key = codes.get(row.model)
        if key and (record[key] or "").startswith("DEMO-FC-"):
            values[key] = record[key].replace("DEMO-FC-", "FU-", 1)
        if row.model == "campus.session" and (record.room or "").startswith(LEGACY_PREFIX):
            values["room"] = record.room.removeprefix(LEGACY_PREFIX)
        if row.model == "campus.grade.change" and row.name == "example_grade_review":
            # An already-submitted request is kept in its original audit trail.
            notes = orm["mail.message"].search([
                ("model", "=", row.model), ("res_id", "=", record.id),
                ("subject", "=", "ДЭМО: Дүн хянуулах хүсэлт"),
            ])
            if notes:
                notes.write({"subject": "Дүн хянуулах хүсэлт"})
                updated += len(notes)
        if values:
            record.write(values)
            updated += 1
    return updated


def demo_account(ensure, orm, role, name, login, allow_login, apply):
    group = orm.ref(f"campus_university.group_campus_{role}")
    model = orm["res.users"]
    key = login.split("@", 1)[0].replace("-", "_")
    password_var = f"FORMULA_CAMPUS_{'STUDENT' if role == 'student' else 'TEACHER'}_PASSWORD"
    values = {
        "name": name,
        "email": login,
        "tz": TIMEZONE.key,
        "active": allow_login,
        "company_id": orm.company.id,
        "company_ids": [Command.set(orm.company.ids)],
        "groups_id": [Command.set(group.ids)],
        "notification_type": "email" if role == "student" else "inbox",
    }
    if allow_login and not orm.ref(f"{NAMESPACE}.{key}", raise_if_not_found=False):
        # Report a collision before asking for a password. Keep passwords out of
        # logs and let Odoo store its normal password hash.
        if model.with_context(active_test=False).search_count([("login", "=", login)]):
            raise RuntimeError(f"Login already belongs to another record: {login}")
        password = os.environ.get(password_var, "") or ("" if apply else secrets.token_urlsafe(24))
        if len(password) < 16:
            raise RuntimeError(f"Set {password_var} to at least 16 characters for the new demo login.")
        values["password"] = password
    user = ensure("res.users", key, {"login": login}, values)
    if user.active != allow_login or not user.has_group(f"campus_university.group_campus_{role}"):
        raise RuntimeError(f"Existing demo account {login} has unexpected status or role. Review it manually.")
    return user


def current_term(orm, ensure, today):
    # The portal uses the newest open term for everyone. Reuse it when it
    # covers today so the demo does not displace an active staging catalog.
    active = orm["campus.academic.term"].search(
        [("state", "=", "open")], order="date_start desc", limit=1,
    )
    if active and active.date_start <= today <= active.date_end:
        return active
    if active and active.date_start > today:
        raise RuntimeError(f"The portal's open term {active.code} starts in the future. Review its dates.")

    start = monday(today) - timedelta(weeks=3)
    if active:
        # Keep past and future demo terms disjoint. This also puts this term
        # ahead of the stale open term in the portal's sort order.
        start = max(start, active.date_end + timedelta(days=1))
    end = monday(start) + timedelta(weeks=12, days=6)
    key = start.strftime("%Y%m%d")
    term = ensure("campus.academic.term", f"term_{key}", {"code": f"FU-{key}"}, {
        "name": f"Одоогийн сургалтын улирал · {start:%Y.%m.%d}",
        "date_start": start,
        "date_end": end,
        "registration_start": start - timedelta(weeks=1),
        "registration_end": start + timedelta(days=13),
        "add_drop_end": start + timedelta(days=20),
        "state": "open",
    })
    if term.state != "open" or not term.date_start <= today <= term.date_end:
        raise RuntimeError(f"Existing demo term {term.code} is unavailable. Review its status and dates.")
    return term


def historical_term(ensure, today, current):
    # The dates are fixed by the first run. A stable key keeps the same
    # transcript history when the current term rolls over.
    end = monday(min(today, current.date_start)) - timedelta(weeks=8, days=1)
    start = end - timedelta(weeks=11, days=6)
    return ensure("campus.academic.term", "term_history", {"code": "FU-HISTORY"}, {
        "name": "Өмнөх сургалтын улирал",
        "date_start": start,
        "date_end": end,
        "registration_start": start - timedelta(weeks=1),
        "registration_end": start + timedelta(days=6),
        "add_drop_end": start + timedelta(days=13),
        "state": "closed",
    })


def seed_sessions(orm, ensure, offering, key, room, meetings, first, last):
    model = orm["campus.session"]
    # Include sessions the seed already scheduled, even if a gap between runs
    # puts them outside the rolling window by the time attendance is due.
    owned = orm["ir.model.data"].search([
        ("module", "=", NAMESPACE), ("model", "=", model._name),
        ("res_id", "in", offering.session_ids.ids),
    ])
    sessions = model.browse(owned.mapped("res_id"))
    week = monday(first)
    while week <= last:
        for weekday, hour, kind in meetings:
            day = week + timedelta(days=weekday)
            if not first <= day <= last:
                continue
            local_start = datetime.combine(day, hour, TIMEZONE)
            start = local_start.astimezone(timezone.utc).replace(tzinfo=None)
            end = start + (timedelta(minutes=90) if len(meetings) == 2 else timedelta(minutes=180))
            session = ensure("campus.session", f"{key}_{day:%Y%m%d}_{kind}", {
                "offering_id": offering.id, "start": start,
            }, {
                "end": end, "room": room, "kind": kind,
            }, verify=("offering_id",), reuse_match=True)
            sessions |= session
        week += timedelta(weeks=1)
    return sessions


def seed_enrollments(orm, offering, students, policy, historical, created):
    model = orm["campus.enrollment"]
    roster = model.search([("offering_id", "=", offering.id), ("student_id", "in", students.ids)])
    missing = students - roster.student_id
    if not missing:
        return roster
    if not historical and offering.state != "open":
        raise RuntimeError(f"Cannot add students to the changed offering {offering.name}.")

    # Existing and historical rosters are imported via the registrar create
    # path, which accepts initial scores and enforces capacity. The self
    # registration method is for a currently open add/drop window.
    if not historical:
        # Protect against changes made in the UI between runs. The synthetic
        # course grid itself contains no student time conflicts or prerequisites.
        if any(not student.active or student.status != "active" for student in missing):
            raise RuntimeError(f"Review inactive students before importing the roster for {offering.name}.")
        enrolled = model.search([("student_id", "in", missing.ids), ("reg_state", "=", "enrolled")])
        term_enrolled = enrolled.filtered(lambda row: row.offering_id.term_id == offering.term_id)
        credits = Counter()
        for row in term_enrolled:
            credits[row.student_id.id] += row.credits
        if any(credits[student.id] + offering.course_id.credits > policy.max_credits_per_term
               for student in missing):
            raise RuntimeError(f"Adding students to {offering.name} would exceed the term credit limit.")
        other_sessions = enrolled.offering_id.session_ids
        for session in offering.session_ids:
            if any(other.start < session.end and other.end > session.start for other in other_sessions):
                raise RuntimeError(f"Adding students to {offering.name} would create a timetable conflict.")
        if offering.course_id.prerequisite_ids:
            raise RuntimeError(f"Review the prerequisites added to {offering.course_id.code} before importing.")

    values = []
    for student in missing:
        value = {"student_id": student.id, "offering_id": offering.id}
        if historical:
            # Stable spread with occasional low marks and high achievers.
            rng = Random(f"{student.student_code}:{offering.course_id.code}:grade")
            value["score"] = round(max(43, min(99, rng.gauss(79, 11))), 1)
        values.append(value)
    new_roster = model.create(values)
    if historical:
        new_roster.action_complete()
    created[model._name] += len(new_roster)
    return roster | new_roster


def seed_attendance(orm, sessions, roster, now, created):
    model = orm["campus.attendance"]
    elapsed = sessions.filtered(lambda session: session.end <= now)
    eligible = roster.filtered(lambda row: row.reg_state in ("enrolled", "completed"))
    existing = model.search([("session_id", "in", elapsed.ids), ("enrollment_id", "in", eligible.ids)])
    recorded = {(row.session_id.id, row.enrollment_id.id) for row in existing}
    values = []
    for session in elapsed:
        for enrollment in eligible:
            if (session.id, enrollment.id) in recorded:
                continue
            rng = Random(f"{enrollment.student_id.student_code}:{session.offering_id.name}:{session.start}")
            draw = rng.randrange(100)
            status = "present"
            if draw < 5:
                status = "absent"
            elif draw < 8:
                status = "excused"
            elif draw < 15:
                status = "late"
            values.append({"session_id": session.id, "enrollment_id": enrollment.id, "status": status})
    if values:
        created[model._name] += len(model.create(values))


def seed(orm, apply):
    # Do not let simultaneous runs race to claim the same keys. The lock
    # is scoped to this transaction and released on commit or rollback.
    orm.cr.execute("SELECT pg_try_advisory_xact_lock(%s, %s)", [1717760611, 420196])
    if not orm.cr.fetchone()[0]:
        raise RuntimeError("Another Formula Campus seed is running. Retry after it finishes.")
    for module in ("campus_university", "campus_academic_plus", "campus_portal"):
        if not orm["ir.module.module"].search_count([("name", "=", module), ("state", "=", "installed")]):
            raise RuntimeError(f"Install {module} on {DATABASE} before running this script.")
    student_password = os.environ.get("FORMULA_CAMPUS_STUDENT_PASSWORD")
    if student_password and student_password == os.environ.get("FORMULA_CAMPUS_TEACHER_PASSWORD"):
        raise RuntimeError("Give the two demo logins distinct passwords.")

    created = Counter()
    data = orm["ir.model.data"]
    new_offerings = set()
    cleaned = normalize_existing_cohort(orm)

    def ensure(model, key, identity, values, *, verify=None, reuse_match=False, on_create=None):
        # XML IDs prove ownership before linking to records on subsequent runs.
        # An exact match for a session on a demo offering can be kept as-is.
        xmlid = f"{NAMESPACE}.{key}"
        model_obj = orm[model]
        metadata = data.search([("module", "=", NAMESPACE), ("name", "=", key)], limit=1)
        if metadata:
            record = model_obj.browse(metadata.res_id).exists() if metadata.model == model else model_obj.browse()
            if not record:
                raise RuntimeError(f"{xmlid} points to a missing or unexpected record.")
            for field in identity if verify is None else verify:
                actual = record[field]
                if record._fields[field].type == "many2one":
                    actual = actual.id
                if actual != identity[field]:
                    raise RuntimeError(f"{xmlid} no longer matches its expected {field}.")
            return record
        match = model_obj.with_context(active_test=False).search(
            [(field, "=", value) for field, value in identity.items()], limit=2,
        )
        if match:
            if reuse_match and len(match) == 1:
                return match
            raise RuntimeError(f"Refusing to adopt an existing or ambiguous {model} for {xmlid}.")
        record = model_obj.create({**identity, **values})
        data.create({"module": NAMESPACE, "name": key, "model": model, "res_id": record.id, "noupdate": True})
        created[model] += 1
        if on_create:
            on_create(record)
        return record

    def open_offering(offering):
        offering.action_open()
        new_offerings.add(offering.id)

    now_local = datetime.now(TIMEZONE)
    today = now_local.date()
    week = monday(today)
    now = now_local.astimezone(timezone.utc).replace(tzinfo=None)
    policy = orm["campus.academic.policy"]._get_active_policy()
    if not policy.scale_ids or not policy._grade_for_score(0):
        raise RuntimeError("The active academic policy needs a complete grade scale.")
    current = current_term(orm, ensure, today)
    history = historical_term(ensure, today, current)
    student_user = demo_account(
        ensure, orm, "student", f"{PATRONYMICS[0]} {GIVEN_NAMES[0]}", STUDENT_LOGIN, True, apply,
    )
    review_enrollment = orm["campus.enrollment"]

    for number, (code, name, department, teacher_names, completed, ongoing) in enumerate(PROGRAMS):
        scope = code.lower()
        teachers = []
        for index, teacher_name in enumerate(teacher_names):
            demo_login = number == index == 0
            address = TEACHER_LOGIN if demo_login else f"lecturer-{scope}-{index + 1}@{DOMAIN}"
            teachers.append(demo_account(ensure, orm, "lecturer", teacher_name, address, demo_login, apply))
        program = ensure("campus.program", f"program_{scope}", {"code": f"FU-{code}"}, {
            "name": name, "department": department, "required_credits": 120,
            "owner_id": teachers[0].id,
        })
        students = orm["campus.student"].browse()
        for index in range(STUDENTS_PER_PROGRAM):
            demo_login = number == index == 0
            student_key = f"{scope}_{index + 1:02}"
            student_code = f"FU-{code}-{index + 1:02}"
            student_name = f"{PATRONYMICS[index]} {GIVEN_NAMES[(index + number * 7) % STUDENTS_PER_PROGRAM]}"
            email = STUDENT_LOGIN if demo_login else f"student-{scope}-{index + 1:02}@{DOMAIN}"
            student = ensure("campus.student", f"student_{student_key}", {"student_code": student_code}, {
                "name": student_name, "institutional_email": email,
                "program_id": program.id, "user_id": student_user.id if demo_login else False,
            })
            if student.program_id != program or student.user_id.id != (student_user.id if demo_login else False):
                raise RuntimeError(f"Existing demo student {student_code} has unexpected account or program links.")
            students |= student

        for term, titles, historical in ((history, completed, True), (current, ongoing, False)):
            for index, title in enumerate(titles):
                level = 100 if historical else 200
                course_key = f"{scope}_{level + index + 1}"
                course_code = f"FU-{code}-{level + index + 1}"
                course = ensure("campus.course", f"course_{course_key}", {"code": course_code}, {
                    "name": title, "credits": CREDITS, "program_id": program.id,
                })
                offering_key = f"offering_{course_key}_{term.id}"
                offering = ensure("campus.offering", offering_key, {
                    "name": f"{course_code} · {title} · {term.code}",
                    "course_id": course.id, "term_id": term.id, "lecturer_id": teachers[index].id,
                }, {"semester": term.code, "capacity": CAPACITY}, verify=("course_id", "term_id", "lecturer_id"),
                    on_create=open_offering)
                if historical:
                    first, last = term.date_start, term.date_end
                    meetings = (MEETINGS[index][0],)
                else:
                    first = max(term.date_start, week - timedelta(weeks=3))
                    last = min(term.date_end, week + timedelta(weeks=2, days=6))
                    meetings = MEETINGS[index]
                room = f"Сургалтын байр {number + 1} · {level + index + 1}"
                sessions = seed_sessions(orm, ensure, offering, offering_key, room, meetings, first, last)
                roster = seed_enrollments(orm, offering, students, policy, historical, created)
                if number == index == 0 and historical:
                    review_enrollment = roster.filtered(lambda row: row.student_id.user_id == student_user)
                if historical and offering.id in new_offerings:
                    offering.action_lock()
                seed_attendance(orm, sessions, roster, now, created)

    request_key = "example_grade_review"
    if not data.search_count([("module", "=", NAMESPACE), ("name", "=", request_key)]):
        review_enrollment.ensure_one()
        lecturer = review_enrollment.offering_id.lecturer_id
        score = review_enrollment.score
        proposed = min(100, score + 3) if score < 97 else score - 2
        reason = "Лабораторийн ажлын үнэлгээний хуудсыг дахин тулгаж хянах хүсэлт."
        result = orm["campus.portal.teacher"].with_user(lecturer).request_grade_change(
            review_enrollment.id, proposed, reason, "FORMULA-CAMPUS-DEMO-REVIEW",
        )
        request_record = orm["campus.grade.change"].browse(result["id"])
        request_record.message_post(
            body="Үнэлгээний тайлбарыг сургалтын албанд шилжүүллээ.",
            subject="Дүн хянуулах хүсэлт",
            subtype_xmlid="mail.mt_comment",
            author_id=lecturer.partner_id.id,
        )
        data.create({"module": NAMESPACE, "name": request_key, "model": request_record._name,
                     "res_id": request_record.id, "noupdate": True})
        created[request_record._name] += 1
    return created, current.code, history.code, week, cleaned


def run(env):
    if env.cr.dbname != DATABASE:
        raise RuntimeError(f"Formula Campus seed is allowed only on {DATABASE}; got {env.cr.dbname!r}.")
    mode = os.environ.get("FORMULA_CAMPUS_APPLY", "0")
    if mode not in ("0", "1"):
        raise RuntimeError("FORMULA_CAMPUS_APPLY must be 0 (preview) or 1 (commit).")
    orm = env(context={**NO_MAIL, "tz": TIMEZONE.key, "allowed_company_ids": env.company.ids})
    try:
        created, current, history, week, cleaned = seed(orm, mode == "1")
        if mode == "1":
            env.cr.commit()
        else:
            env.cr.rollback()
    except BaseException:
        env.cr.rollback()
        raise
    print(f"Formula Campus {('committed' if mode == '1' else 'preview rolled back')} on {DATABASE}.")
    print(f"Terms: {current} (current), {history} (completed). Schedule week: {week:%Y-%m-%d}.")
    print(f"Previous display labels normalized: {cleaned}")
    print("Created: " + (", ".join(f"{model}={count}" for model, count in sorted(created.items())) or "0"))
    print(f"Demo logins: {STUDENT_LOGIN}, {TEACHER_LOGIN}")


if __name__ == "__main__":
    run(env)
