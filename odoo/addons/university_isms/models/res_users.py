"""Нэвтрэлт болон хандах эрхийн өөрчлөлтийг аудит логт бичнэ (A.5.18, A.8.2, A.8.15, A.8.16)."""
import logging

from odoo import SUPERUSER_ID, api, models
from odoo.exceptions import AccessDenied

from .audit import client_ip

_logger = logging.getLogger(__name__)

TRACKED_USER_KEYS = ('groups_id', 'active')
TRACKED_USER_PREFIXES = ('in_group_', 'sel_groups_')


class ResUsers(models.Model):
    _inherit = 'res.users'

    # ---------------------------------------------------------------- login
    @classmethod
    def _login(cls, db, credential, user_agent_env):
        login = credential.get('login') if isinstance(credential, dict) else None
        cred_type = credential.get('type') if isinstance(credential, dict) else None
        try:
            auth_info = super()._login(db, credential, user_agent_env=user_agent_env)
        except AccessDenied:
            cls._isms_log_auth(login, 'login_failed', cred_type)
            raise
        cls._isms_log_auth(login, 'login', cred_type, uid=auth_info.get('uid'))
        return auth_info

    @classmethod
    def _isms_log_auth(cls, login, action, cred_type=None, uid=None):
        try:
            with cls.pool.cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                users = env['res.users'].with_context(active_test=False)
                user = users.browse(uid) if uid else users.search([('login', '=', login)], limit=1)
                env['isms.audit.log'].create({
                    'action': action,
                    'user_id': user.id or False,
                    'login': login,
                    'model': 'res.users',
                    'model_name': 'Хэрэглэгч',
                    'res_id': user.id or 0,
                    'res_name': user.name or login,
                    'changes': 'Баталгаажуулалтын төрөл: %s' % (cred_type or 'password')
                               + ('' if user else '\nТийм нэвтрэх нэртэй хэрэглэгч байхгүй'),
                    'ip_address': client_ip(),
                })
        except Exception:  # аудит лог алдаа нэвтрэлтийг саатуулахгүй
            _logger.exception('ISMS audit: failed to log %s for %s', action, login)

    # ---------------------------------------------------------- access rights
    def _isms_relevant_groups(self, groups):
        categories = self.env['ir.module.category']
        for xmlid in ('university_isms.module_category_isms', 'university_isms.module_category_isms_audit'):
            categories |= self.env.ref(xmlid, raise_if_not_found=False) or categories
        key_groups = self.env['res.groups']
        for xmlid in ('base.group_system', 'base.group_erp_manager', 'base.group_user', 'base.group_portal'):
            key_groups |= self.env.ref(xmlid, raise_if_not_found=False) or key_groups
        return groups.filtered(lambda g: g.category_id in categories or g in key_groups)

    def _isms_group_lines(self, added, removed):
        lines = []
        added, removed = self._isms_relevant_groups(added), self._isms_relevant_groups(removed)
        if added:
            lines.append('Нэмэгдсэн эрх: %s' % ', '.join(added.mapped('full_name')))
        if removed:
            lines.append('Хасагдсан эрх: %s' % ', '.join(removed.mapped('full_name')))
        return lines

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        changes = {}
        for user in users.sudo():
            lines = ['Шинэ хэрэглэгч үүсгэв (%s)' % user.login]
            lines += self._isms_group_lines(user.groups_id, self.env['res.groups'])
            changes[user.id] = '\n'.join(lines)
        if users:
            self.env['isms.audit.log']._log('access_change', users, changes)
        return users

    def write(self, vals):
        track = any(k in TRACKED_USER_KEYS or k.startswith(TRACKED_USER_PREFIXES) for k in vals)
        before = {u.id: (u.groups_id, u.active) for u in self.sudo().with_context(active_test=False)} \
            if track else {}
        res = super().write(vals)
        if track:
            changes = {}
            for user in self.sudo().with_context(active_test=False):
                old_groups, old_active = before[user.id]
                lines = self._isms_group_lines(user.groups_id - old_groups, old_groups - user.groups_id)
                if old_active != user.active:
                    lines.append('Данс %s' % ('идэвхжүүлсэн' if user.active else 'идэвхгүй болгосон (архивласан)'))
                if lines:
                    changes[user.id] = '\n'.join(lines)
            if changes:
                self.env['isms.audit.log']._log('access_change', self.browse(list(changes)), changes)
        return res


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def write(self, vals):
        track = 'users' in vals
        before = {g.id: g.users for g in self.sudo()} if track else {}
        res = super().write(vals)
        if track:
            changes = {}
            for group in self.sudo():
                added, removed = group.users - before[group.id], before[group.id] - group.users
                lines = []
                if added:
                    lines.append('Бүлэгт нэмсэн: %s' % ', '.join(added.mapped('login')))
                if removed:
                    lines.append('Бүлгээс хассан: %s' % ', '.join(removed.mapped('login')))
                if lines:
                    changes[group.id] = '\n'.join(lines)
            if changes:
                self.env['isms.audit.log']._log('access_change', self.browse(list(changes)), changes)
        return res
