"""Seed Formula University demo records without changing any user groups.

Run with Odoo shell against the coursework database. Repeated runs keep
existing records and skip accounts or entries that are already populated.
"""
import os
from datetime import timedelta

from odoo import Command, fields


PREFIX = '[ДЭМО] '
TODOS = {
    'admin': ('Нөөц хуулбарын хяналтын хуудас шинэчлэх', 'Сүүлчийн сэргээх дасгалын хугацаа, хариуцагч болон шалгах дарааллыг тэмдэглэх.'),
    'dorjsembe': ('Удирдлагын дүн шинжилгээ бэлтгэх', 'Үлдэгдэл эрсдэлүүдийн шийдвэр ба хяналтын нотолгоог нягтлах.'),
    'batdemberel': ('Сэргээх дасгалын зааврыг нягтлах', 'Өгөгдлийн сан ба файлын сангийн сэргээх дараалал, хэмжих хугацааг шалгах.'),
    'badral': ('Хөрөнгө ба эрсдэлийн холбоос нягтлах', 'Сургалтын албаны хөрөнгө тус бүрд эзэмшигч, эрсдэл, холбогдох хяналтыг тулгах.'),
    'erkhembayar': ('Инцидент хүлээн авах хуудсыг бэлтгэх', 'Мэдээлсэн цаг, нөлөөлөл, эхний арга хэмжээг жишээ дээр шалгах.'),
    'telmuun': ('Хөндлөн шалгалтын нотолгоо цэгцлэх', 'Эрхийн ялгаа, тайлангийн эх үүсвэр, дэлгэцийн зургийг шалгах хуудаст тулгах.'),
    'rector': ('МАБ-ын хорооны хэлэлцэх асуудлыг нягтлах', 'Дараагийн хурлын эрсдэл ба нөөцийн шийдвэрийн төслийг унших.'),
    'registrar_approver': ('Дүн батлах хүсэлтийн үндэслэл нягтлах', 'Эх бүртгэл ба хүсэлт гаргагч, батлагчийн үүргийн ялгааг шалгах.'),
    'lecturer_cs': ('Лабораторийн хичээлийн заавар бэлтгэх', 'Хичээлийн өмнө сургалтын өгөгдөл болон жишээ бүртгэлийг нягтлах.'),
    'lab_head': ('Лабораторийн төхөөрөмжийн буцаалтыг тулгах', 'Демо төхөөрөмжийн шошго, байршил, буцаалтын хуудсыг тулгах.'),
    'hr_officer': ('Эрх цуцлах шалгах хуудас нягтлах', 'Ажил хүлээлцэх болон бүртгэл хаах мэдэгдлийн явцыг турших.'),
    'student_demo': ('Мэдээллийн аюулгүй байдлын заавар унших', 'Сургалтын порталд асуудал гарвал мэдээлэх дарааллыг давтах.'),
    'campus.student': ('Хичээлийн дүнгээ тулгах', 'Дүнгийн бүртгэл ба зөвшөөрөгдсөн хүсэлтийн явцыг өөрийн цэснээс шалгах.'),
    'campus.other_student': ('Сүлжээний лабораторийн тэмдэглэлээ бэлтгэх', 'Дасгалын файлаас үнэлгээний шалгуур, өгсөн даалгаврыг тулгах.'),
    'campus.lecturer': ('Үнэлгээний үндэслэлээ нэгтгэх', 'Дүнгийн тайлбар ба үнэлгээний хуудсыг зөвхөн өөрийн хичээл дээр тулгах.'),
    'campus.other_lecturer': ('Лабораторийн үнэлгээний хүсэлтээ нягтлах', 'Хавсаргасан шалгалтын жишээгээр санал болгосон өөрчлөлтийг тайлбарлах.'),
    'campus.registrar': ('Хичээл сонголтын бүртгэл тулгах', 'Хөтөлбөрийн код, хичээлийн бүлэг, бүртгүүлсэн оюутны жагсаалтыг тулгах.'),
    'campus.reviewer': ('Бие даан хянах хүсэлтээ сонгох', 'Шинэ дүнгийн үндэслэлийг эх бүртгэлтэй тулгаж, батлах шатанд оруулахад бэлтгэх.'),
    'campus.auditor': ('Дүнгийн шийдвэрийн мөрийг дагаж шалгах', 'Хүсэлт гаргагч, батлагч, огноог бүртгэлээс уншиж тулгах.'),
}
INCIDENTS = {
    'admin': ('Туршилтын веб хуудсанд алдааны мэдэгдэл гарсан', 'other', 'Демо хуудсыг дахин нээхэд алдаа давтагдсан эсэхийг тэмдэглэх.'),
    'dorjsembe': ('Хяналтын жишээ тайлан буруу хувилбараар нээгдсэн', 'integrity', 'Туршилтын тайлангийн хувилбарыг шалгах.'),
    'batdemberel': ('Туршилтын сэргээх тайлан нээгдэхгүй болсон', 'other', 'Жишээ файлыг сэргээх дасгалын үр дүнтэй тулгах.'),
    'badral': ('Сургалтын бүртгэлийн жишээ мөр давхардсан', 'integrity', 'Зөвхөн демо өгөгдөл бүхий мөрийн дугаарыг тулгах.'),
    'telmuun': ('Хөндлөн шалгалтын жишээ хавсралт дутуу', 'other', 'Демо нотолгооны индекс болон хавсаргасан файлыг тулгах.'),
    'lecturer_cs': ('Дадлагын хичээлийн жишээ холбоос ажиллаагүй', 'other', 'Багшид харагдах туршилтын холбоосыг нягтлах.'),
    'student_demo': ('Оюутны порталын демо мэдэгдэл харагдаагүй', 'other', 'Туршилтын мэдэгдэл харагдах нөхцөлийг тэмдэглэх.'),
    'campus.student': ('Хичээлийн мэдэгдэл хоцорч ирсэн', 'other', 'Хичээлийн цэсэнд мэдэгдлийн огноо ба харагдсан цаг зөрсөн туршилтын жишээ.'),
    'campus.other_student': ('Лабораторийн жишээ материал нээгдэхгүй болсон', 'other', 'Демо даалгаврын холбоос нэг удаа нээгдээгүй.'),
    'campus.lecturer': ('Үнэлгээний хуудсын туршилтын загвар зөрсөн', 'integrity', 'Жишээ файлын баганын толгой өмнөх загвараас өөр байсан. Бодит дүн оруулаагүй.'),
    'campus.other_lecturer': ('Лабораторийн материалын хандалтын алдаа', 'other', 'Демо багшид туршилтын материалыг нээх сонголт харагдаагүй.'),
    'campus.registrar': ('Демо хичээлийн бүлэг давхар харагдсан', 'integrity', 'Хичээл сонголтын туршилтын жагсаалтад ижил гарчигтай хоёр мөр гарсан.'),
    'campus.reviewer': ('Демо нотолгооны файл хоосон нээгдсэн', 'other', 'Дүнгийн хүсэлтийн туршилтын нотолгоо уншигдаагүй.'),
    'campus.auditor': ('Жишээ тайлангийн огноо зөрсөн', 'integrity', 'Демо тайлангийн огноог эх бүртгэлтэй тулгахад зөрүү гарсан.'),
    'erkhembayar': ('Туршилтын хяналтын самбарт төлөв шинэчлэгдээгүй', 'other', 'Демо төлөв өөрчлөгдөх жишээг инцидент хүлээн авах урсгалаар үзүүлнэ.'),
    'rector': ('Хурлын жишээ тайлан нээгдэхгүй болсон', 'other', 'Зохиомол хавсралтыг дахин нээх шалгалт хийх.'),
    'registrar_approver': ('Батлах дэлгэцийн туршилтын тэмдэглэл дутсан', 'other', 'Дүн батлах урсгалын жишээ тайлбар дэлгэцэд бүрэн харагдаагүй.'),
    'lab_head': ('Демо төхөөрөмжийн шошго уншигдаагүй', 'physical', 'Туршилтын төхөөрөмжийн шошго уншихад алдаа гарсан.'),
    'hr_officer': ('Ажил хүлээлцэх демо маягтын төлөв харагдаагүй', 'other', 'Демо маягтын төлөв дахин нээхэд шинэчлэгдээгүй.'),
}
SERVICES = {
    'admin': ('Сургалтын орчны нөөц хуулбарын шалгалт', 'Хугацаа, нөөцийн байршил, сэргээлтийн зааврыг туршилтын орчинд тулгах.'),
    'dorjsembe': ('Удирдлагын тайлангийн хандалтын лавлагаа', 'Тайлан харах эрхийн хүрээ болон ашиглах хувилбарыг нягтлах.'),
    'erkhembayar': ('Үйлчилгээний самбарын төлөвийн лавлагаа', 'Туршилтын төлөвийн зөрүүг ангилж, шалгалтын тэмдэглэл бэлтгэх.'),
    'rector': ('Хорооны хурлын материалын лавлагаа', 'Хорооны хурлын жишээ материалын унших хувилбар бэлэн эсэхийг шалгах.'),
}
PROJECTS = {
    'admin': ('Odoo орчны бэлэн байдал', 'HTTPS нэвтрэх хуудсыг шалгах'),
    'dorjsembe': ('МАБ-ын удирдлагын дүн шинжилгээ', 'Хяналтын нотолгоог нэгтгэх'),
    'erkhembayar': ('Инцидент хариу арга хэмжээний дасгал', 'Инцидент ангилах жишээ боловсруулах'),
    'rector': ('Сургалтын үйлчилгээний үргэлжлэл', 'Хороонд танилцуулах шийдвэрийн төсөл унших'),
}
CTX = dict(tracking_disable=True, mail_create_nosubscribe=True,
           mail_create_nolog=True, mail_notrack=True, mail_activity_quick_update=True,
           mail_notify_force_send=False)


def seed(env):
    companies = env['res.company']
    users = {}
    for login in TODOS:
        account = login + '@orgil.example' if login.startswith('campus.') else login
        user = env['res.users'].search([('login', '=', account), ('active', '=', True),
                                        ('share', '=', False)], limit=1)
        if not user:
            raise ValueError(f'Expected active demo account: {login}')
        users[login] = user
        companies |= user.company_id
    companies.ensure_one()
    company = companies
    orm = env(context={**CTX, 'allowed_company_ids': company.ids, 'lang': 'en_US'})
    created = {}

    def ensure(model, domain, vals):
        records = orm[model]
        record = records.search(domain, limit=1)
        if not record:
            record = records.create(vals)
            created[model] = created.get(model, 0) + 1
        return record

    def named(model, title, **vals):
        name = PREFIX + title
        return ensure(model, [('name', '=', name)], {'name': name, **vals})

    def visible(record, user):
        assert record.with_user(user).search_count([('id', '=', record.id)]) == 1, (
            user.login, record._name, record.id)

    date = fields.Date.context_today(orm['project.task'])
    activity_type = orm.ref('mail.mail_activity_data_todo')
    for login, (title, description) in TODOS.items():
        user = users[login]
        todo = ensure('project.task', [('name', '=', PREFIX + title),
                      ('project_id', '=', False), ('user_ids', 'in', user.ids)], {
            'name': PREFIX + title, 'description': '<p>' + description + '</p>',
            'project_id': False, 'user_ids': [Command.set(user.ids)],
            'date_deadline': date + timedelta(days=7),
        })
        visible(todo, user)
        aid = orm['ir.model']._get_id('project.task')
        activity = ensure('mail.activity', [('res_model_id', '=', aid),
                          ('res_id', '=', todo.id), ('user_id', '=', user.id)], {
            'res_model_id': aid, 'res_id': todo.id, 'user_id': user.id,
            'activity_type_id': activity_type.id, 'summary': PREFIX + 'Дараагийн алхмаа нягтлах',
            'date_deadline': date + timedelta(days=3),
        })
        visible(activity, user)

    for login, (title, task_title) in PROJECTS.items():
        user = users[login]
        if not user.has_group('project.group_project_user'):
            continue
        project = named('project.project', title, company_id=company.id,
                        user_id=user.id, privacy_visibility='followers',
                        description='<p>Formula University-ийн зохиомол ажлын жишээ.</p>')
        if user.partner_id not in project.message_partner_ids:
            project.message_subscribe(partner_ids=user.partner_id.ids)
        stage = ensure('project.task.type', [('name', '=', 'Төлөвлөсөн'),
                       ('project_ids', 'in', project.ids)],
                       {'name': 'Төлөвлөсөн', 'project_ids': [Command.link(project.id)]})
        task = ensure('project.task', [('name', '=', PREFIX + task_title),
                      ('project_id', '=', project.id)], {
            'name': PREFIX + task_title, 'project_id': project.id, 'stage_id': stage.id,
            'user_ids': [Command.set(user.ids)], 'date_deadline': date + timedelta(days=5),
            'description': '<p>Шалгасан зүйл ба дараагийн алхмыг даалгаварт тэмдэглэнэ.</p>',
        })
        visible(project, user)
        visible(task, user)
        outside = users['campus.other_student']
        assert not project.with_user(outside).search_count([('id', '=', project.id)])
        assert not task.with_user(outside).search_count([('id', '=', task.id)])

    tag = named('helpdesk.ticket.tag', 'Сургалтын орчин')
    ticket_category = named('helpdesk.ticket.category', 'Дотоод үйлчилгээний лавлагаа')
    for login, (title, description) in SERVICES.items():
        user = users[login]
        ticket = named('helpdesk.ticket', title, company_id=company.id,
                       partner_id=user.partner_id.id, user_id=user.id,
                       category_id=ticket_category.id, tag_ids=[Command.link(tag.id)],
                       description='<p>' + description + '</p>')
        visible(ticket, user)

    incident_count = 0
    for login, user in users.items():
        incident = orm['isms.incident'].with_user(user).search(
            [('reporter_id', '=', user.id)], limit=1)
        if not incident:
            title, category, description = INCIDENTS[login]
            reporter_type = ('student' if 'student' in login else
                             'faculty' if 'lecturer' in login else 'staff')
            incident = orm['isms.incident']._isms_internal().create({
                'name': PREFIX + title, 'description': 'Зохиомол сургалтын бүртгэл. ' + description,
                'category': category, 'severity': 'low', 'reporter_id': user.id,
                'reporter_type': reporter_type,
            })
            incident_count += 1
        visible(incident, user)
    if incident_count:
        created['isms.incident'] = incident_count

    owner = users['registrar_approver']
    risk = named('isms.risk', 'Дүн батлах үед жишээ нотолгоо буруу хүсэлтэд хавсаргах',
                 owner_id=owner.id, likelihood='2', impact='2',
                 description='Демо үнэлгээ. Хүсэлтийн дугаар ба хавсралтын гарчгийг тулгана.')
    visible(risk, owner)

    student = users['campus.other_student']
    lecturer = users['campus.other_lecturer']
    enrollment = orm['campus.enrollment'].search([
        ('student_id.user_id', '=', student.id), ('offering_id.lecturer_id', '=', lecturer.id),
        ('offering_id.state', '=', 'open')], limit=1)
    enrollment.ensure_one()
    grade = orm['campus.grade.change'].search([('evidence_ref', '=', 'DEMO-ACADEMIC-LAB-REVIEW')], limit=1)
    before = enrollment.score, enrollment.grade_revision
    if not grade:
        grade = orm['campus.grade.change'].with_user(lecturer).create({
            'enrollment_id': enrollment.id, 'proposed_score': min(100, enrollment.score + 2),
            'reason': 'ДЭМО: лабораторийн үнэлгээний шалгуурыг эх жишээтэй тулгаж хянуулах.',
            'evidence_ref': 'DEMO-ACADEMIC-LAB-REVIEW',
        })
        grade.action_submit()
        created['campus.grade.change'] = 1
    for login in ('campus.other_student', 'campus.other_lecturer', 'campus.registrar',
                  'campus.reviewer', 'campus.auditor'):
        visible(grade, users[login])
    assert (enrollment.score, enrollment.grade_revision) == before
    assert not grade.with_user(users['campus.student']).search_count([('id', '=', grade.id)])

    named('project.tags', 'Хяналтын нотолгоо')
    named('hr.job', 'Сургалтын системийн дадлагажигч', company_id=company.id)
    skill_type = named('hr.skill.type', 'Дадлагын чадвар')
    level = ensure('hr.skill.level', [('skill_type_id', '=', skill_type.id),
                   ('name', '=', 'Дадлага')], {
        'name': 'Дадлага', 'level_progress': 50, 'skill_type_id': skill_type.id,
    })
    for login, title in [('dorjsembe', 'Хяналт төлөвлөх'), ('erkhembayar', 'Инцидент ангилах'),
                         ('telmuun', 'Нотолгоо тулгах')]:
        skill = named('hr.skill', title, skill_type_id=skill_type.id)
        employee = users[login].employee_id
        employee.ensure_one()
        ensure('hr.employee.skill', [('employee_id', '=', employee.id), ('skill_id', '=', skill.id)], {
            'employee_id': employee.id, 'skill_id': skill.id, 'skill_type_id': skill_type.id,
            'skill_level_id': level.id,
        })

    for model, title in [('project.task', 'Даалгаврын чанар шалгах төлөвлөгөө'),
                         ('hr.employee', 'Ажил хүлээлцэх дасгалын төлөвлөгөө')]:
        plan = named('mail.activity.plan', title, res_model=model, company_id=company.id)
        ensure('mail.activity.plan.template', [('plan_id', '=', plan.id)], {
            'plan_id': plan.id, 'activity_type_id': activity_type.id,
            'summary': PREFIX + 'Шалгах хуудсыг тулгах', 'responsible_type': 'on_demand',
        })

    warehouse = orm['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
    warehouse.ensure_one()
    new_stock = named('stock.location', 'Сургалтын хэрэгслийн тавиур',
                      usage='internal', company_id=company.id, location_id=warehouse.lot_stock_id.id)
    scrap_location = named('stock.location', 'Сургалтын хэрэгслийн хасалт',
                           usage='inventory', company_id=company.id, scrap_location=True,
                           location_id=orm.ref('stock.stock_location_locations_virtual').id)
    product = ensure('product.product', [('default_code', '=', 'DEMO-FORMULA-LABEL-01')], {
        'name': PREFIX + 'Лабораторийн бүртгэлийн шошго', 'default_code': 'DEMO-FORMULA-LABEL-01',
        'company_id': company.id, 'type': 'consu', 'is_storable': True,
        'sale_ok': False, 'purchase_ok': False,
    })
    origin = PREFIX + 'Лабораторийн шошго хүлээн авах'
    vendor_location = warehouse.in_type_id.default_location_src_id or orm.ref('stock.stock_location_suppliers')
    receipt = ensure('stock.picking', [('origin', '=', origin)], {
        'origin': origin, 'picking_type_id': warehouse.in_type_id.id,
        'location_id': vendor_location.id, 'location_dest_id': new_stock.id,
        'move_ids': [Command.create({
            'name': product.name, 'product_id': product.id, 'product_uom_qty': 6,
            'product_uom': product.uom_id.id,
            'location_id': vendor_location.id, 'location_dest_id': new_stock.id,
        })],
    })
    if receipt.state != 'done':
        receipt.action_confirm()
        receipt.move_ids.quantity = 6
        receipt.move_ids.picked = True
        receipt.with_context(skip_backorder=True).button_validate()
    assert receipt.state == 'done'
    scrap = ensure('stock.scrap', [('origin', '=', PREFIX + 'Гэмтсэн шошго хасах')], {
        'origin': PREFIX + 'Гэмтсэн шошго хасах', 'company_id': company.id,
        'product_id': product.id, 'product_uom_id': product.uom_id.id, 'scrap_qty': 1,
        'location_id': new_stock.id, 'scrap_location_id': scrap_location.id,
    })
    if scrap.state != 'done':
        scrap.action_validate()
    assert scrap.state == 'done'

    for user in users.values():
        if user.has_group('stock.group_stock_user'):
            visible(scrap, user)
            visible(receipt.move_ids, user)
            visible(receipt.move_line_ids, user)
    assert orm['discuss.channel'].browse(orm.ref('mail.channel_all_employees').id).message_ids
    print(f'Аккаунт: {len(users)}. Шинээр үүссэн: {created or "0"}')


seed(env)
if os.environ.get('ISMS_DEMO_APPLY') == '1':
    env.cr.commit()
    print('COMMIT')
else:
    env.cr.rollback()
    print('PREVIEW — rolled back')
