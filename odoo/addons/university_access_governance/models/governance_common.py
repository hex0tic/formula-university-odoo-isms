"""Хандалтын засаглалын туслах функцүүд (GOV-01, GOV-03, GOV-04, GOV-05).

Эрхийн тодорхойлолт (MANAGER_GROUP, PRIVILEGED_GROUPS, SOD_RULES) ба SoD шалгалтыг
university_access_review-ээс импортлоно; хуулахгүй. Бүх бүлгийн өөрчлөлт res.users.write-ээр
явагдана, тиймээс university_isms-ийн access_change аудит лог автоматаар бичигдэнэ.
"""
from odoo import Command

from odoo.addons.university_access_review.models.access_review import MANAGER_GROUP, PRIVILEGED_GROUPS

SYSTEM_GROUP = 'base.group_system'
AUDITOR_GROUP = 'university_isms.group_isms_auditor'
CISO_GROUP = 'university_isms.group_isms_manager'
# Access review-ийн давуу эрхүүдээс гадна ISMS CISO, кампусын бүртгэгч, агуулахын менежер.
EXTRA_PRIVILEGED_GROUPS = [CISO_GROUP, 'campus_university.group_campus_registrar', 'stock.group_stock_manager']
# Хянагдах бүлгээс хасах (суурь хандалт, нийтийн хэрэглэгч).
NON_REVIEWABLE_GROUPS = ['base.group_user', 'base.group_portal', 'base.group_public']
ACTION_CONTEXT = 'access_gov_action'


def soft_groups(env, xmlids):
    """Модуль суулгагдсан эсэхээс үл хамааран олдсон бүлгүүдийг буцаана."""
    ids = []
    for xmlid in xmlids:
        group = env.ref(xmlid, raise_if_not_found=False)
        if group:
            ids.append(group.id)
    return env['res.groups'].browse(ids)


def privileged_groups(env):
    return soft_groups(env, list(PRIVILEGED_GROUPS) + EXTRA_PRIVILEGED_GROUPS)


def is_manager(user):
    """erp_manager (system бүлэг нь үүнийг удамшуулдаг)."""
    return user.has_group(MANAGER_GROUP)


def is_system(user):
    return user.has_group(SYSTEM_GROUP)


def effective_groups(groups):
    return groups | groups.trans_implied_ids


def sod_conflicts(env, groups):
    """access.review-ийн SoD логикийг дахин бичихгүйгээр дуудна (GOV-02)."""
    return env['access.review']._sod_conflicts(groups)


def new_sod_conflicts(env, before, after):
    """Хоёр бүлгийн багцын хооронд ШИНЭЭР үүсэх SoD зөрчлүүд."""
    old = set(sod_conflicts(env, before))
    return [c for c in sod_conflicts(env, after) if c not in old]


def link_groups(user, groups):
    if groups:
        user.write({'groups_id': [Command.link(g.id) for g in groups]})


def unlink_groups(user, groups):
    if groups:
        user.write({'groups_id': [Command.unlink(g.id) for g in groups]})
