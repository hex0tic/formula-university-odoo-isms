# Odoo shell скрипт: biydaalt/data/*.csv (schema-university_isms.md §4)-г idempotent байдлаар импортлоно.
#   scripts/odoo-shell.sh scripts/import_case_data.py
# Код/login-оор upsert хийдэг тул дахин ажиллуулахад давхардахгүй. Шинэ хэрэглэгчийн санамсаргүй нууц үгийг
# /mnt/case-data биш, stdout-д биш, харин evidence/private/odoo/isms-user-credentials.csv (640, setgid)-д бичнэ.
import csv
import html
import os
import re
import secrets
import string

DATA = '/mnt/case-data'
POLICIES = '/mnt/case-policies'
CRED_FILE = '/mnt/case-private/isms-user-credentials.csv'
ROLE_GROUP = {
    'reporter': 'university_isms.group_isms_reporter',
    'asset_owner': 'university_isms.group_isms_asset_owner',
    'auditor': 'university_isms.group_isms_auditor',
    'analyst': 'university_isms.group_isms_analyst',
    'manager': 'university_isms.group_isms_manager',
    'admin': 'base.group_system',
}
stats = {}


def rows(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        print('skip (байхгүй): %s' % name)
        return []
    with open(path, encoding='utf-8-sig', newline='') as fh:
        return [{k.strip(): (v or '').strip() for k, v in r.items() if k} for r in csv.DictReader(fh)]


def count(key):
    stats[key] = stats.get(key, 0) + 1


def split(value):
    return [v.strip() for v in re.split(r'[;|]', value or '') if v.strip()]


def boolean(value):
    return (value or '').strip().lower() in ('1', 'true', 'yes', 'y', 'тийм', 'x')


def user(login):
    if not login:
        return env['res.users']
    return env['res.users'].with_context(active_test=False).search([('login', '=', login)], limit=1)


def by_code(model, codes):
    codes = split(codes) if isinstance(codes, str) else codes
    recs = env[model].with_context(active_test=False).search([('code', 'in', codes)])
    missing = set(codes) - set(recs.mapped('code'))
    if missing:
        print('  анхаар: %s-д олдоогүй код: %s' % (model, ', '.join(sorted(missing))))
    return recs


def upsert(model, key, vals):
    Model = env[model].with_context(active_test=False, mail_create_nolog=True, tracking_disable=False)
    rec = Model.search([(key, '=', vals[key])], limit=1)
    if rec:
        rec.write(vals)
        count('%s updated' % model)
    else:
        rec = Model.create(vals)
        count('%s created' % model)
    return rec


def sel(model, field, value):
    """Selection-ийн key эсвэл шошгоор утга олох."""
    if not value:
        return False
    options = dict(env[model]._fields[field]._description_selection(env))
    if value in options:
        return value
    for key, label in options.items():
        if label.lower().startswith(value.lower()):
            return key
    raise ValueError('%s.%s: "%s" буруу утга (%s)' % (model, field, value, ', '.join(options)))


def md_to_html(text):
    out, in_list, table = [], False, []

    def inline(s):
        s = html.escape(s)
        s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        return re.sub(r'`(.+?)`', r'<code>\1</code>', s)

    def flush_table():
        if table:
            body = [r for r in table if not re.match(r'^\|?\s*:?-{2,}', r.replace(' ', ''))]
            cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in body]
            out.append('<table class="table table-sm table-bordered"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>' % (
                ''.join('<th>%s</th>' % inline(c) for c in cells[0]),
                ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % inline(c) for c in r) for r in cells[1:])))
            table.clear()

    for line in text.splitlines():
        if line.strip().startswith('|'):
            table.append(line)
            continue
        flush_table()
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if re.match(r'^\s*([-*]|\d+\.)\s+', line):
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append('<li>%s</li>' % inline(re.sub(r'^\s*([-*]|\d+\.)\s+', '', line)))
            continue
        if in_list:
            out.append('</ul>')
            in_list = False
        if m:
            out.append('<h%d>%s</h%d>' % (len(m.group(1)) + 1, inline(m.group(2)), len(m.group(1)) + 1))
        elif line.strip():
            out.append('<p>%s</p>' % inline(line))
    flush_table()
    if in_list:
        out.append('</ul>')
    return '\n'.join(out)


# 1. Нэгж
for r in rows('departments.csv'):
    parent = env['hr.department'].search([('name', '=', r.get('parent'))], limit=1) if r.get('parent') else False
    dept = env['hr.department'].search([('name', '=', r['name'])], limit=1)
    vals = {'name': r['name'], 'parent_id': parent.id if parent else False}
    dept.write(vals) if dept else env['hr.department'].create(vals)
    count('hr.department')

# 2. Хэрэглэгч (RBAC)
new_creds = []
alphabet = string.ascii_letters + string.digits
for r in rows('users.csv'):
    role = r.get('isms_role', 'reporter')
    groups = [env.ref('base.group_user').id, env.ref(ROLE_GROUP[role]).id]
    if role == 'admin':
        groups.append(env.ref('university_isms.group_isms_reporter').id)
    u = user(r['login'])
    vals = {'name': r['name'], 'login': r['login'], 'tz': 'Asia/Ulaanbaatar',
            'email': r['login'] if '@' in r['login'] else False}
    if u:
        u.write(vals)
        u.write({'groups_id': [(4, g) for g in groups]})
        count('res.users updated')
    else:
        password = ''.join(secrets.choice(alphabet) for _i in range(16))
        u = env['res.users'].with_context(no_reset_password=True).create(
            dict(vals, password=password, groups_id=[(6, 0, groups)]))
        new_creds.append((r['login'], password, role))
        count('res.users created')
    dept = env['hr.department'].search([('name', '=', r.get('department'))], limit=1) if r.get('department') else False
    employee = env['hr.employee'].search([('user_id', '=', u.id)], limit=1)
    emp_vals = {'name': r['name'], 'user_id': u.id, 'job_title': r.get('job_title') or False,
                'department_id': dept.id if dept else False}
    employee.write(emp_vals) if employee else env['hr.employee'].create(emp_vals)
DRY_RUN = bool(os.environ.get('ISMS_IMPORT_DRY_RUN'))
if new_creds and not DRY_RUN:
    os.makedirs(os.path.dirname(CRED_FILE), exist_ok=True)
    exists = os.path.exists(CRED_FILE)
    with open(CRED_FILE, 'a', encoding='utf-8') as fh:
        if not exists:
            fh.write('login,password,isms_role\n')
        fh.writelines('%s,%s,%s\n' % c for c in new_creds)
    os.chmod(CRED_FILE, 0o640)  # owner odoo, group = хэрэглэгч (setgid хавтас)
    print('шинэ %d хэрэглэгчийн нууц үг → evidence/private/odoo/isms-user-credentials.csv' % len(new_creds))

# Хэлтсийн менежер
for r in rows('departments.csv'):
    if r.get('manager_login'):
        mgr = env['hr.employee'].search([('user_id', '=', user(r['manager_login']).id)], limit=1)
        env['hr.department'].search([('name', '=', r['name'])], limit=1).manager_id = mgr

# 3. Каталог
for fname, model in (('threats.csv', 'isms.threat'), ('vulnerabilities.csv', 'isms.vulnerability')):
    for r in rows(fname):
        upsert(model, 'code', {'code': r['code'], 'name': r['name'],
                               'category': sel(model, 'category', r.get('category')) or 'technical'
                               if model == 'isms.vulnerability' else sel(model, 'category', r.get('category')) or 'deliberate',
                               'description': r.get('description') or False})

# 4. Хөрөнгө
for r in rows('assets.csv'):
    dept = env['hr.department'].search([('name', '=', r.get('department'))], limit=1) if r.get('department') else False
    upsert('isms.asset', 'code', {
        'code': r['code'], 'name': r['name'],
        'asset_type': sel('isms.asset', 'asset_type', r.get('asset_type')) or 'information',
        'department_id': dept.id if dept else False,
        'owner_id': user(r.get('owner_login')).id or False,
        'custodian_id': user(r.get('custodian_login')).id or False,
        'location': r.get('location') or False,
        'classification': sel('isms.asset', 'classification', r.get('classification')) or 'internal',
        'confidentiality': r.get('confidentiality') or '2',
        'integrity': r.get('integrity') or '2',
        'availability': r.get('availability') or '2',
        'personal_data': boolean(r.get('personal_data')),
        'lifecycle_stage': sel('isms.asset', 'lifecycle_stage', r.get('lifecycle_stage')) or 'protect',
        'description': r.get('description') or False,
    })

# 5. SoA
for r in rows('soa.csv'):
    control = env['isms.control'].search([('code', '=', r['control_code'].replace('A.', ''))], limit=1)
    if not control:
        print('  анхаар: control олдсонгүй %s' % r['control_code'])
        continue
    control.write({
        'selected': boolean(r.get('selected', '1')),
        'applicable': boolean(r.get('applicable', '1')),
        'implementation': sel('isms.control', 'implementation', r.get('implementation')) or 'no',
        'justification': r.get('justification') or False,
        'odoo_implementation': r.get('odoo_implementation') or False,
        'evidence': r.get('evidence') or False,
        'responsible_id': user(r.get('responsible_login')).id or False,
    })
    count('isms.control SoA')

# 6. Эрсдэл
for r in rows('risks.csv'):
    threat = env['isms.threat'].search([('code', '=', r.get('threat_code'))], limit=1)
    vuln = env['isms.vulnerability'].search([('code', '=', r.get('vulnerability_code'))], limit=1)
    vals = {
        'code': r['code'], 'name': r['name'], 'description': r.get('description') or False,
        'asset_ids': [(6, 0, by_code('isms.asset', r.get('asset_codes')).ids)],
        'threat_id': threat.id or False, 'vulnerability_id': vuln.id or False,
        'likelihood': r['likelihood'], 'impact': r['impact'],
        'treatment': sel('isms.risk', 'treatment', r.get('treatment')),
        'control_ids': [(6, 0, by_code('isms.control', [c.replace('A.', '') for c in split(r.get('control_codes'))]).ids)],
        'owner_id': user(r.get('owner_login')).id or env.user.id,
        'residual_likelihood': r.get('residual_likelihood') or False,
        'residual_impact': r.get('residual_impact') or False,
        'due_date': r.get('due_date') or False,
        'treatment_plan': '<p>%s</p>' % html.escape(r['treatment_plan']) if r.get('treatment_plan') else False,
    }
    risk = upsert('isms.risk', 'code', vals)
    if r.get('state'):
        risk.state = sel('isms.risk', 'state', r['state'])

# 7. Инцидент
for r in rows('incidents.csv'):
    vals = {
        'code': r['code'], 'name': r['name'],
        'category': sel('isms.incident', 'category', r.get('category')) or 'other',
        'severity': sel('isms.incident', 'severity', r.get('severity')) or 'medium',
        'reporter_type': sel('isms.incident', 'reporter_type', r.get('reporter_type')) or 'staff',
        'reporter_id': user(r.get('reporter_login')).id or env.user.id,
        'assignee_id': user(r.get('assignee_login')).id or False,
        'detected_at': r.get('detected_at') or False,
        'asset_ids': [(6, 0, by_code('isms.asset', r.get('asset_codes')).ids)],
        'risk_ids': [(6, 0, by_code('isms.risk', r.get('risk_codes')).ids)],
        'control_ids': [(6, 0, by_code('isms.control', [c.replace('A.', '') for c in split(r.get('control_codes'))]).ids)],
        'impact_c': boolean(r.get('impact_c')), 'impact_i': boolean(r.get('impact_i')),
        'impact_a': boolean(r.get('impact_a')),
        'personal_data_breach': boolean(r.get('personal_data_breach')),
        'data_subjects_count': int(r.get('data_subjects_count') or 0),
        'description': r.get('description') or False, 'containment': r.get('containment') or False,
        'root_cause': r.get('root_cause') or False, 'resolution': r.get('resolution') or False,
        'lessons_learned': r.get('lessons_learned') or False,
        'notification_done': boolean(r.get('notification_done')),
        'notification_note': r.get('notification_note') or False,
    }
    if not vals['detected_at']:
        vals.pop('detected_at')
    inc = upsert('isms.incident', 'code', vals)
    target = sel('isms.incident', 'state', r.get('state')) or 'incident'
    order = ['incident', 'report', 'investigate', 'resolve', 'close']
    stamp = {'report': 'reported_at', 'investigate': 'investigation_at', 'resolve': 'resolved_at', 'close': 'closed_at'}
    if order.index(target) > order.index(inc.state):
        # Seed-ийн төлөвийг хуучин урсгалаар тэмдэглэнэ; бодит шилжилтийг UI-д хэрэглэгчид хийнэ
        inc.write({'state': target, **{stamp[s]: inc.detected_at for s in order[1:order.index(target) + 1]}})

# 8. Бодлого
for r in rows('policies.csv'):
    content = False
    if r.get('content_file'):
        path = os.path.join(POLICIES, os.path.basename(r['content_file']))
        if os.path.exists(path):
            content = md_to_html(open(path, encoding='utf-8').read())
        else:
            print('  анхаар: бодлогын файл олдсонгүй %s' % r['content_file'])
    vals = {
        'code': r['code'], 'name': r['name'],
        'policy_type': sel('isms.policy', 'policy_type', r.get('policy_type')) or 'issp',
        'version': r.get('version') or '1.0',
        'owner_id': user(r.get('owner_login')).id or env.user.id,
        'control_ids': [(6, 0, by_code('isms.control', [c.replace('A.', '') for c in split(r.get('control_codes'))]).ids)],
        'content': content,
    }
    pol = upsert('isms.policy', 'code', vals)
    state = sel('isms.policy', 'state', r.get('state')) or 'draft'
    if state == 'approved' and pol.state != 'approved':
        pol.write({'state': 'approved', 'approver_id': user(r.get('approver_login')).id or env.user.id,
                   'approval_date': r.get('approval_date') or False,
                   'next_review_date': r.get('next_review_date') or False})
    elif state != 'approved':
        pol.state = state

# 9. Workflow-ийн нийцэл (university_isms 18.0.1.1.0+): CSV-ийн төлөвийг шууд бичсэн тул дүрэмтэй тулгана
if hasattr(env['isms.risk'], '_isms_repair_workflow_consistency'):
    repair = env['isms.risk']._isms_repair_workflow_consistency('canonical import')
    print('workflow repair:', repair)
problems = []
for inc in env['isms.incident'].search([('state', 'in', ('resolve', 'close'))]):
    if not (inc.root_cause and inc.resolution):
        problems.append('%s: root_cause/resolution хоосон' % inc.code)
    if inc.personal_data_breach and not inc.notification_note:
        problems.append('%s: хувийн мэдээллийн зөрчлийн notification_note хоосон' % inc.code)
    if inc.state == 'close' and not inc.lessons_learned:
        problems.append('%s: lessons_learned хоосон' % inc.code)
for pol in env['isms.policy'].search([('state', '=', 'approved'), ('approver_id', '=', False)]):
    problems.append('%s: батлагдсан бодлогын батлагч хоосон' % pol.code)
print('consistency problems:', problems or 'байхгүй')
print('IMPORT %s' % ('DRY-RUN (rollback)' if DRY_RUN else 'OK'), stats)
print('counts: assets=%d risks=%d selected_controls=%d incidents=%d policies=%d users_isms=%d' % (
    env['isms.asset'].search_count([]), env['isms.risk'].search_count([]),
    env['isms.control'].search_count([('selected', '=', True)]), env['isms.incident'].search_count([]),
    env['isms.policy'].search_count([]),
    env['res.users'].search_count([('groups_id', 'in', env.ref('university_isms.group_isms_reporter').id)])))
if DRY_RUN:
    env.cr.rollback()
else:
    env.cr.commit()
