"""Run inside Odoo shell with env and CAMPUS_DEMO_CREDENTIALS supplied.

Only fictional academic data is created. Stable XML IDs make repeat runs safe.
Passwords are supplied by the local runner, never committed in source code.
"""
from odoo import Command


def seed(env, credentials):
    def upsert(model, code, values):
        xmlid = "campus_university." + code
        record = env.ref(xmlid, raise_if_not_found=False)
        if record:
            # Preserve historical grades and existing demo decisions on rerun.
            if model != "campus.enrollment":
                record.write(values)
            return record
        record = env[model].sudo().create(values)
        env["ir.model.data"].sudo().create({
            "module": "campus_university", "name": code,
            "model": model, "res_id": record.id, "noupdate": True,
        })
        return record

    users = {}
    for role, label in [
        ("student", "Оюутан — Демо Анар"), ("other_student", "Оюутан — Демо Номин"),
        ("lecturer", "Багш — Демо Саруул"), ("other_lecturer", "Багш — Демо Төгөлдөр"),
        ("registrar", "Сургалтын алба — Демо Уянга"),
        ("reviewer", "Батлах ажилтан — Демо Энхжин"),
        ("auditor", "Академик аудитор — Демо Билгүүн"),
    ]:
        group_role = {"other_student": "student", "other_lecturer": "lecturer", "reviewer": "registrar"}.get(role, role)
        account = credentials[role]
        users[role] = upsert("res.users", "campus_demo_" + role, {
            "name": label, "login": account["login"], "password": account["password"],
            "email": account["login"], "lang": "mn_MN", "tz": "Asia/Ulaanbaatar",
            "notification_type": "inbox",
            "groups_id": [Command.set([env.ref("campus_university.group_campus_" + group_role).id])],
        })
    program = upsert("campus.program", "case_program_sec", {
        "code": "SEC", "name": "Мэдээллийн аюулгүй байдал",
        "department": "Инженер, тоон технологийн сургууль", "owner_id": users["registrar"].id,
    })
    course = upsert("campus.course", "case_course_governance", {
        "code": "ORG-338", "name": "Мэдээллийн аюулгүй байдлын засаглал ба менежмент",
        "credits": 3, "program_id": program.id,
    })
    second_course = upsert("campus.course", "case_course_lab", {
        "code": "ORG-342", "name": "Кибер-физик лабораторийн аюулгүй байдал",
        "credits": 3, "program_id": program.id,
    })
    offering = upsert("campus.offering", "case_offering_governance", {
        "name": "ORG-338 / 2026-A / Семестрийн хаалт", "course_id": course.id,
        "semester": "2026-A", "lecturer_id": users["lecturer"].id, "state": "locked",
    })
    other_offering = upsert("campus.offering", "case_offering_lab", {
        "name": "ORG-342 / 2026-A / Хамтарсан лаборатори", "course_id": second_course.id,
        "semester": "2026-A", "lecturer_id": users["other_lecturer"].id, "state": "open",
    })
    first = upsert("campus.student", "case_student_anar", {
        "student_code": "DEMO-26001", "name": "Демо Анар", "user_id": users["student"].id,
        "program_id": program.id, "institutional_email": "demo.anar@orgil.example",
    })
    second = upsert("campus.student", "case_student_nomin", {
        "student_code": "DEMO-26002", "name": "Демо Номин", "user_id": users["other_student"].id,
        "program_id": program.id, "institutional_email": "demo.nomin@orgil.example",
    })
    third = upsert("campus.student", "case_student_ireedui", {
        "student_code": "DEMO-26003", "name": "Демо Ирээдүй",
        "program_id": program.id, "institutional_email": "demo.ireedui@orgil.example",
    })
    enrollments = [
        upsert("campus.enrollment", "case_enrollment_anar", {
            "student_id": first.id, "offering_id": offering.id, "score": 72,
        }),
        upsert("campus.enrollment", "case_enrollment_nomin", {
            "student_id": second.id, "offering_id": other_offering.id, "score": 81,
        }),
        upsert("campus.enrollment", "case_enrollment_ireedui", {
            "student_id": third.id, "offering_id": offering.id, "score": 68,
        }),
    ]
    env.cr.commit()
    print("CAMPUS_SEED_OK users=%d programs=1 courses=2 offerings=2 students=3 enrollments=%d" % (
        len(users), len(enrollments),
    ))


seed(env, CAMPUS_DEMO_CREDENTIALS)
