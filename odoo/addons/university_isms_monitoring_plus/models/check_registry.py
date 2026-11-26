"""Автомат хяналтын шалгалтуудын бүртгэл (ISMS-03, ISO/IEC 27001:2022 A.8.16, Clause 9.1).

Гэрээ:
* Шалгалт бүр `func(env) -> (result, details, metrics)` хэлбэртэй чистый функц.
* `result`: 'pass' | 'fail' | 'not_applicable'. Алдаа гарвал exception шидэж, гүйцэтгэгч
  `result='error'` гэж бүртгэнэ.
* `details`: зөвхөн агрегат тоо, бодлогын код, хэрэглэгчийн нэвтрэх нэр (давуу эрхтэй
  бүртгэлийн тоонд). Нууц үг, TOTP нууц, токен, хэш, имэйл, IP хаяг хэзээ ч гаргахгүй.
* Бүх шалгалт ЗӨВХӨН УНШИХ. Ямар ч бичлэг үүсгэх, засах, устгахгүй. Аудит логийн
  хамгаалалтын шалгалт нь зөвхөн савепойнт дотор оролдлого хийж, бүгдийг буцаадаг.
* `sudo()` зөвхөн функцийн дотор, зөвхөн уншихад ашиглана. Гүйцэтгэх орчинд
  `sudo` тохируулсан эсэхээс үл хамааран дүн шинжилгээ өгөгдөлд бүрэн хамрагдана.
"""
from collections import namedtuple
from datetime import timedelta

from odoo import fields

CheckSpec = namedtuple('CheckSpec', 'key label severity control_code scope func')

PASS = 'pass'
FAIL = 'fail'
NOT_APPLICABLE = 'not_applicable'

GROUP_SYSTEM = 'base.group_system'
GROUP_ERP_MANAGER = 'base.group_erp_manager'
GROUP_ISMS_MANAGER = 'university_isms.group_isms_manager'
GROUP_ISMS_ANALYST = 'university_isms.group_isms_analyst'
PRIVILEGED_GROUPS = (GROUP_SYSTEM, GROUP_ERP_MANAGER, GROUP_ISMS_MANAGER)

PARAM_MAX_ADMINS = 'university_isms_monitoring_plus.max_privileged_admins'
PARAM_MAX_INACTIVE_DAYS = 'university_isms_monitoring_plus.max_inactive_days'
DEFAULT_MAX_ADMINS = 2
DEFAULT_MAX_INACTIVE_DAYS = 90


def _param_int(env, key, default):
    try:
        return int(env['ir.config_parameter'].sudo().get_param(key, default))
    except (TypeError, ValueError):
        return default


def _active_internal_users(env, xmlids):
    """Идэвхтэй, дотоод (share биш) хэрэглэгчид тодорхой группт (аль нэг нь)."""
    group_ids = [env.ref(xmlid).id for xmlid in xmlids]
    return env['res.users'].sudo().search([
        ('groups_id', 'in', group_ids), ('share', '=', False), ('active', '=', True)])


def _totp_state(user):
    """True/False: auth_totp суугдсан бол TOTP идэвхтэй эсэх. None: модуль байхгүй.

    Утга нь нууц биш, зөвхөн логик төлөв. Нууц утгыг хэзээ ч уншихгүй.
    """
    if 'totp_enabled' not in user._fields:
        return None
    return bool(user.totp_enabled)


# ----------------------------------------------------------------- checks

def check_privileged_no_totp(env):
    """Scope: base.group_system, base.group_erp_manager, university_isms.group_isms_manager
    группийн идэвхтэй хэрэглэгчдээс TOTP идэвхгүйг олно. Нэвтрэх нэрийг л гаргана."""
    users = _active_internal_users(env, PRIVILEGED_GROUPS)
    states = {user.login: _totp_state(user) for user in users}
    if any(state is None for state in states.values()):
        return (NOT_APPLICABLE, 'auth_totp модуль суулгаагүй тул TOTP төлөвийг шалгах боломжгүй.', {})
    missing = sorted(login for login, state in states.items() if not state)
    details = 'Давуу эрхтэй хэрэглэгч: %d; TOTP идэвхгүй: %d' % (len(states), len(missing))
    if missing:
        details += ' (%s)' % ', '.join(missing)
    metrics = {'privileged_users': len(states), 'without_totp': len(missing)}
    return (FAIL if missing else PASS, details, metrics)


def check_privileged_group_size(env):
    """Scope: Settings (base.group_system) болон Access Rights (base.group_erp_manager)
    группийн идэвхтэй хэрэглэгчийн тоог тохируулсан босготой харьцуулна.
    Босго: ir.config_parameter `university_isms_monitoring_plus.max_privileged_admins` (анх 2)."""
    limit = _param_int(env, PARAM_MAX_ADMINS, DEFAULT_MAX_ADMINS)
    system_count = len(_active_internal_users(env, (GROUP_SYSTEM,)))
    erp_count = len(_active_internal_users(env, (GROUP_ERP_MANAGER,)))
    details = 'Settings: %d; Access Rights: %d; дээд босго: %d' % (system_count, erp_count, limit)
    metrics = {'system_users': system_count, 'erp_manager_users': erp_count, 'threshold': limit}
    over = system_count > limit or erp_count > limit
    return (FAIL if over else PASS, details, metrics)


class _ProbeRollback(Exception):
    """Савепойнтыг үргэлж буцаахад ашиглана (оролдлого амжилттай бол ч өөрчлөлт хадгалагдахгүй)."""


def check_audit_log_tamper_guard(env):
    """Scope: isms.audit.log-ийн сүүлийн нэг бичлэг дээр шинжээчийн (аль байхгүй бол одоогийн
    орчны) эрхээр write болон unlink оролдоно. Оролдлого бүр савепойнт дотор ажиллаж,
    амжилттай бол ч буцаагдана. Татгалзсан байх ёстой (ORM хамгаалалт эсвэл ACL)."""
    row = env['isms.audit.log'].sudo().search([], order='id desc', limit=1)
    if not row:
        return (NOT_APPLICABLE, 'Аудит логийн бичлэг байхгүй.', {})
    analyst = env['res.users'].sudo().search(
        [('groups_id', 'in', [env.ref(GROUP_ISMS_ANALYST).id]), ('share', '=', False)], limit=1)
    actor = analyst or env.user
    target = env(user=actor, su=False)['isms.audit.log'].browse(row.id)
    refused = {}
    for label, operation in (
            ('write', lambda rec: rec.write({'action': row.action})),
            ('unlink', lambda rec: rec.unlink())):
        accepted = False
        try:
            with env.cr.savepoint():
                operation(target)
                raise _ProbeRollback()
        except _ProbeRollback:
            accepted = True
        except Exception:  # UserError / AccessError: хамгаалалт ажилласан
            accepted = False
        refused[label] = not accepted
    details = 'Аудит лог: сүүлийн бичлэгийг засах %s; устгах %s' % (
        'татгалзсан' if refused['write'] else 'ЗӨВШӨӨРСӨН',
        'татгалзсан' if refused['unlink'] else 'ЗӨВШӨӨРСӨН')
    metrics = {'write_refused': refused['write'], 'unlink_refused': refused['unlink']}
    return (PASS if all(refused.values()) else FAIL, details, metrics)


def check_policies_past_review(env):
    """Scope: батлагдсан (state=approved) бодлогын next_review_date өнгөрсөн тоо, кодоор."""
    today = fields.Date.context_today(env.user)
    policies = env['isms.policy'].sudo().search([
        ('state', '=', 'approved'), ('next_review_date', '!=', False),
        ('next_review_date', '<', today)])
    details = 'Дахин хянах хугацаа хэтэрсэн бодлого: %d' % len(policies)
    if policies:
        details += ' (%s)' % ', '.join(policies.mapped('code'))
    return (FAIL if policies else PASS, details, {'overdue_policies': len(policies)})


def check_incidents_past_sla_unassigned(env):
    """Scope: хаагдаагүй (resolve/close биш) инцидентийн SLA хугацаа хэтэрсэн ба шалгагчгүй тоо."""
    now = fields.Datetime.now()
    overdue = env['isms.incident'].sudo().search([
        ('state', 'not in', ('resolve', 'close')), ('sla_deadline', '<', now)])
    unassigned = overdue.filtered(lambda inc: not inc.assignee_id)
    details = 'SLA хэтэрсэн инцидент: %d; түүнээс шалгагчгүй: %d' % (len(overdue), len(unassigned))
    if unassigned:
        details += ' (%s)' % ', '.join(unassigned.mapped('code'))
    metrics = {'sla_overdue': len(overdue), 'unassigned_overdue': len(unassigned)}
    return (FAIL if unassigned else PASS, details, metrics)


def check_inactive_privileged_users(env):
    """Scope: идэвхтэй боловч N хоног (ir.config_parameter, анх 90) нэвтрээгүй давуу эрхтэй
    хэрэглэгч. Огноо: login_date (сүүлд нэвтэрсэн), байхгүй бол үүсгэсэн огноо."""
    days = _param_int(env, PARAM_MAX_INACTIVE_DAYS, DEFAULT_MAX_INACTIVE_DAYS)
    cutoff = fields.Datetime.now() - timedelta(days=days)
    users = _active_internal_users(env, PRIVILEGED_GROUPS)
    stale = users.filtered(lambda u: (u.login_date or u.create_date) and
                           (u.login_date or u.create_date) < cutoff)
    details = 'Давуу эрхтэй, %d хоногоос нэвтрээгүй идэвхтэй хэрэглэгч: %d' % (days, len(stale))
    if stale:
        details += ' (%s)' % ', '.join(stale.mapped('login'))
    return (FAIL if stale else PASS, details, {'inactive_privileged': len(stale), 'days': days})


def check_evidence_freshness(env):
    """Scope: isms.evidence модель (ISMS-01) байвал state=approved ба valid_until < өнөөдөр
    бичлэгийн тоо. Модель эсвэл талбар байхгүй бол not_applicable."""
    if 'isms.evidence' not in env.registry:
        return (NOT_APPLICABLE, 'isms.evidence модель суулгагдаагүй.', {})
    model = env['isms.evidence'].sudo()
    if not {'state', 'valid_until'} <= set(model._fields):
        return (NOT_APPLICABLE, 'isms.evidence дээр state/valid_until талбар байхгүй.', {})
    today = fields.Date.context_today(env.user)
    expired = model.search_count([('state', '=', 'approved'), ('valid_until', '<', today)])
    details = 'Хугацаа дууссан батлагдсан нотолгоо: %d' % expired
    return (FAIL if expired else PASS, details, {'expired_evidence': expired})


def check_audit_chain_integrity(env):
    """Scope: university_isms_audit_chain суулгагдсан үед isms.audit.log-ийн hash гинжийг бүрэн
    шалгана (seq дараалал, prev_hash холбоос, entry_hash, толгойн харьцуулалт). Зөвхөн унших.
    Эвдрэлтэй бол эвдэрсэн seq ба шалтгааныг дурдана (хэш утга гаргахгүй). Аддон суулгаагүй бол
    not_applicable; энэ модуль тэр аддоноос хамаардаггүй."""
    if 'isms.audit.chain.head' not in env.registry or 'isms.audit.log' not in env.registry:
        return (NOT_APPLICABLE, 'Аудит гинжийн аддон суулгагдаагүй.', {})
    result = env['isms.audit.log'].sudo()._verify_chain()
    checked = int(result.get('checked') or 0)
    if result.get('ok'):
        if not checked:
            return (NOT_APPLICABLE, 'Гинжинд бичлэг байхгүй.', {'checked': 0})
        return (PASS, 'Аудит гинж бүрэн: %d бичлэг.' % checked, {'checked': checked})
    broken = int(result.get('broken_seq') or 0)
    details = 'Аудит гинж эвдэрсэн: seq=%s. Шалтгаан: %s' % (broken or '-', result.get('reason') or '')
    return (FAIL, details, {'checked': checked, 'broken_seq': broken})


CHECKS = {spec.key: spec for spec in (
    CheckSpec('privileged_no_totp', 'Давуу эрхтэй хэрэглэгч TOTP-гүй', 'high', 'Annex A 8.5',
              'Давуу эрхтэй группийн идэвхтэй хэрэглэгчдээс TOTP идэвхгүйг тоолно (auth_totp байвал).',
              check_privileged_no_totp),
    CheckSpec('privileged_group_size', 'Давуу эрхтэй группын хэмжээ', 'medium', 'Annex A 8.2',
              'Settings болон Access Rights группийн хэрэглэгчийн тоог босготой харьцуулна.',
              check_privileged_group_size),
    CheckSpec('audit_log_tamper_guard', 'Аудит логийн хамгаалалт', 'high', 'Annex A 8.15',
              'Аудит логийн бичлэг дээр засах, устгах оролдлого татгалзагдсаныг шалгана (савепойнтод).',
              check_audit_log_tamper_guard),
    CheckSpec('policies_past_review', 'Бодлогын дахин хяналт хэтэрсэн', 'medium', 'Annex A 5.1',
              'Батлагдсан бодлогын дахин хянах огноо өнгөрсөн тоо.',
              check_policies_past_review),
    CheckSpec('incidents_past_sla_unassigned', 'SLA хэтэрсэн шалгагчгүй инцидент', 'high', 'Annex A 5.26',
              'Хаагдаагүй инцидентийн SLA хэтэрсэн ба шалгагчгүй тоо.',
              check_incidents_past_sla_unassigned),
    CheckSpec('inactive_privileged_users', 'Удаан нэвтрээгүй давуу эрхтэй хэрэглэгч', 'high', 'Annex A 5.18',
              'Идэвхтэй, давуу эрхтэй, N хоног нэвтрээгүй хэрэглэгчийн тоо.',
              check_inactive_privileged_users),
    CheckSpec('evidence_freshness', 'Нотолгооны хугацаа дууссан', 'medium', 'Annex A 5.33',
              'isms.evidence байвал хугацаа дууссан батлагдсан нотолгоо. Байхгүй бол хамааралгүй.',
              check_evidence_freshness),
    CheckSpec('audit_chain_integrity', 'Аудит гинжийн бүрэн бүтэн байдал', 'high', 'Annex A 8.15',
              'university_isms_audit_chain суулгагдсан үед аудит логийн hash гинжийг бүтнээр шалгана. Суулгаагүй бол хамааралгүй.',
              check_audit_chain_integrity),
)}


def check_selection():
    return [(key, spec.label) for key, spec in CHECKS.items()]
