"""Хэрэглэгчийн эрхийн тойм (ISO/IEC 27001:2022 A.5.15, A.5.18, A.8.2).

Эрхийг ACL-ийн хүснэгтээс таамаглахгүй, сонгосон хэрэглэгчийн нэрээр (su=False) бодитоор
хайлт хийж, бичлэгийн дүрмийг оролцуулан тооцоолно. Зөвхөн base.group_erp_manager ашиглана.
"""
from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError

# (ангилал, техникийн нэр, монгол нэр)
REVIEW_MODELS = [
    ('ISMS', 'isms.asset', 'Хөрөнгө'),
    ('ISMS', 'isms.risk', 'Эрсдэл'),
    ('ISMS', 'isms.threat', 'Аюул занал'),
    ('ISMS', 'isms.vulnerability', 'Эмзэг байдал'),
    ('ISMS', 'isms.control', 'Annex A хяналт ба SoA'),
    ('ISMS', 'isms.policy', 'Бодлого'),
    ('ISMS', 'isms.incident', 'Зөрчил'),
    ('ISMS', 'isms.audit.log', 'Аудит лог'),
    ('Helpdesk', 'helpdesk.ticket', 'Helpdesk тасалбар'),
    ('Төсөл', 'project.project', 'Төсөл'),
    ('Төсөл', 'project.task', 'Даалгавар'),
    ('Inventory', 'product.template', 'Бүтээгдэхүүн, хөрөнгийн каталог'),
    ('Inventory', 'stock.quant', 'Агуулахын үлдэгдэл'),
    ('Академик', 'campus.program', 'Хөтөлбөр'),
    ('Академик', 'campus.student', 'Оюутан'),
    ('Академик', 'campus.course', 'Хичээл'),
    ('Академик', 'campus.offering', 'Хичээлийн хуваарь'),
    ('Академик', 'campus.enrollment', 'Хичээлийн бүртгэл ба дүн'),
    ('Академик', 'campus.grade.change', 'Дүнгийн засварын хүсэлт'),
    ('Хүний нөөц', 'hr.employee', 'Ажилтан'),
    ('Хүний нөөц', 'hr.department', 'Нэгж'),
    ('Чат', 'discuss.channel', 'Чат суваг'),
    ('Систем', 'res.users', 'Хэрэглэгч'),
    ('Систем', 'res.groups', 'Эрхийн бүлэг'),
]

# Кодонд (has_group) бичигдсэн бизнесийн хориг. (ангилал, үйлдэл, шаардлагатай бүлгүүд, тайлбар)
REVIEW_ACTIONS = [
    ('ISMS', 'Зөрчил мэдээлэх', ['university_isms.group_isms_reporter'], ''),
    ('ISMS', 'Зөрчлийг шалгах, шийдвэрлэх', ['university_isms.group_isms_analyst'], ''),
    ('ISMS', 'Зөрчилд эрсдэл, хяналт холбох', ['university_isms.group_isms_analyst'], ''),
    ('ISMS', 'Зөрчил хаах, дахин нээх', ['university_isms.group_isms_manager'], 'Зөвхөн CISO'),
    ('ISMS', 'Бодлогыг хянуулахаар илгээх', ['university_isms.group_isms_analyst'], ''),
    ('ISMS', 'Бодлого батлах', ['university_isms.group_isms_manager'], 'Зөвхөн CISO'),
    ('ISMS', 'Эрсдэлийн үе шат өөрчлөх', ['university_isms.group_isms_analyst'], ''),
    ('ISMS', 'Эрсдэлийг хүлээн зөвшөөрөх', ['university_isms.group_isms_manager'], 'Зөвхөн CISO'),
    ('ISMS', 'Үлдэгдэл эрсдэл батлах', 'residual', ''),
    ('Академик', 'Дүнгийн засварын хүсэлт гаргах',
     ['campus_university.group_campus_lecturer', 'campus_university.group_campus_registrar'],
     'Багш зөвхөн өөрийн заадаг хичээлд'),
    ('Академик', 'Дүнгийн засварын хүсэлт батлах, татгалзах',
     ['campus_university.group_campus_registrar'], 'Өөрийн гаргасан хүсэлтийг батлахгүй'),
    ('Академик', 'Хичээлийн хуваарь нээх, түгжих', ['campus_university.group_campus_registrar'], ''),
    ('Систем', 'Хэрэглэгчийн эрх өөрчлөх', ['base.group_erp_manager'], ''),
    ('Систем', 'Системийн тохиргоо өөрчлөх', ['base.group_system'], ''),
]

MANAGER_GROUP = 'base.group_erp_manager'
# GOV-05: зөвхөн системийн администратор олгож, хурааж болох давуу эрх (A.8.2).
PRIVILEGED_GROUPS = ['base.group_system', 'base.group_erp_manager']
# GOV-02: нэг хүнд хамт олгохгүй эрхийн хослол (A.5.3). (бүлэг 1, бүлэг 2, шалтгаан[, чөлөөлөх бүлэг])
SOD_RULES = [
    ('campus_university.group_campus_lecturer', 'campus_university.group_campus_registrar',
     'Дүнгийн засварын хүсэлт гаргагч ба батлагч нэг хүн болно'),
    ('university_isms.group_isms_auditor', 'university_isms.group_isms_analyst',
     'Дотоод аудитор өөрийн шалгах ISMS бүртгэлийг засах эрхтэй болно',
     # CISO-гийн бүлэг хоёуланг нь загвараар агуулдаг тул энэ дүрэмд хамаарахгүй.
     'university_isms.group_isms_manager'),
    ('university_isms.group_isms_auditor', 'base.group_system',
     'Аудитор системийн тохиргоо ба аудит логийн орчныг өөрчлөх эрхтэй болно'),
]
OPS = ('read', 'write', 'create', 'unlink')


class AccessReview(models.TransientModel):
    _name = 'access.review'
    _description = 'Хэрэглэгчийн эрхийн тойм'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', 'Хэрэглэгч', required=True,
                              domain=[('share', '=', False)])
    login = fields.Char('Нэвтрэх нэр', related='user_id.login')
    job_title = fields.Char('Албан тушаал')
    department = fields.Char('Нэгж')
    isms_role = fields.Char('ISMS үүрэг')
    project_summary = fields.Char('Төсөл')
    channel_summary = fields.Char('Чат')
    model_summary = fields.Char('Модел')
    sod_warnings = fields.Text('Үүргийн тусгаарлалтын зөрчил')
    model_line_ids = fields.One2many('access.review.model.line', 'review_id', 'Модел ба бичлэг')
    project_line_ids = fields.One2many('access.review.project.line', 'review_id', 'Төслүүд')
    channel_line_ids = fields.One2many('access.review.channel.line', 'review_id', 'Чат')
    action_line_ids = fields.One2many('access.review.action.line', 'review_id', 'Бизнесийн үйлдэл')
    group_line_ids = fields.One2many('access.review.group.line', 'review_id', 'Эрхийн бүлэг')

    # ------------------------------------------------------------------ guard
    def _check_manager(self):
        if not self.env.su and not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_('Хэрэглэгчийн эрхийг зөвхөн эрх өөрчлөх эрхтэй ажилтан харна.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        records = super().create(vals_list)
        for rec in records:
            if rec.user_id and not rec.model_line_ids:
                rec.write(rec._review_values(rec.user_id))
        return records

    @api.onchange('user_id')
    def _onchange_user_id(self):
        self._check_manager()
        if self.user_id:
            self.update(self._review_values(self.user_id._origin or self.user_id))
        else:
            self.update({k: [Command.clear()] for k in (
                'model_line_ids', 'project_line_ids', 'channel_line_ids', 'action_line_ids', 'group_line_ids')})

    # ------------------------------------------------------------------ build
    def _review_values(self, user):
        user = user.sudo()
        as_user = self.env(user=user.id, su=False)
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        vals = {
            'job_title': employee.job_title or employee.job_id.name or '',
            'department': employee.department_id.name or '',
            'isms_role': self._isms_role(user),
            'sod_warnings': '\n'.join(self._sod_conflicts(user.groups_id)),
        }
        vals.update(self._model_lines(user, as_user))
        vals.update(self._project_lines(as_user))
        vals.update(self._channel_lines(user, as_user))
        vals['action_line_ids'] = [Command.clear()] + [Command.create(v) for v in self._action_lines(user)]
        vals['group_line_ids'] = [Command.clear()] + [Command.create(v) for v in self._group_lines(user)]
        return vals

    def _isms_role(self, user):
        roles = [('university_isms.group_isms_manager', '5. МАБ менежер (CISO)'),
                 ('university_isms.group_isms_analyst', '4. МАБ шинжээч'),
                 ('university_isms.group_isms_auditor', '3. Дотоод аудитор'),
                 ('university_isms.group_isms_asset_owner', '2. Хөрөнгө эзэмшигч'),
                 ('university_isms.group_isms_reporter', '1. Мэдээлэгч')]
        for xmlid, label in roles:
            if self.env.ref(xmlid, raise_if_not_found=False) and user.has_group(xmlid):
                return label
        return 'ISMS эрхгүй'

    def _model_lines(self, user, as_user):
        lines, readable = [], 0
        for seq, (category, model, label) in enumerate(REVIEW_MODELS):
            if model not in self.env:
                continue
            Model = as_user[model]
            rights = {op: Model.has_access(op) for op in OPS}
            total = self.env[model].sudo().search_count([])
            visible = writable = 0
            if rights['read']:
                try:
                    records = Model.search([])
                    visible = len(records)
                    if rights['write']:
                        writable = len(records._filtered_access('write'))
                except AccessError:
                    visible = writable = 0
            readable += bool(visible)
            granted_by = self._acl_sources(user, model)
            lines.append({
                'sequence': seq, 'category': category, 'name': label, 'model': model,
                'can_read': rights['read'], 'can_write': rights['write'],
                'can_create': rights['create'], 'can_unlink': rights['unlink'],
                'visible_count': visible, 'writable_count': writable, 'total_count': total,
                'granted_by': granted_by,
            })
        return {
            'model_line_ids': [Command.clear()] + [Command.create(v) for v in lines],
            'model_summary': _('%(n)s моделоос %(r)s-д бичлэг харна', n=len(lines), r=readable),
        }

    def _acl_sources(self, user, model):
        """Тухайн моделийг унших эрхийг аль бүлэг олгож байгааг тайлбарлана (WF-06)."""
        acls = self.env['ir.model.access'].sudo().search([
            ('model_id.model', '=', model), ('perm_read', '=', True), ('active', '=', True)])
        names = []
        for acl in acls:
            if not acl.group_id:
                names.append(_('Бүх хэрэглэгч'))
            elif acl.group_id in user.groups_id:
                names.append(acl.group_id.name)
        return ', '.join(sorted(set(names)))

    def _sod_conflicts(self, groups):
        groups = groups | groups.trans_implied_ids
        found = []
        for rule in SOD_RULES:
            first, second, reason = rule[:3]
            g1 = self.env.ref(first, raise_if_not_found=False)
            g2 = self.env.ref(second, raise_if_not_found=False)
            exempt = self.env.ref(rule[3], raise_if_not_found=False) if len(rule) > 3 else False
            if exempt and exempt in groups:
                continue
            if g1 and g2 and g1 in groups and g2 in groups:
                found.append('%s + %s: %s' % (g1.sudo().name, g2.sudo().name, reason))
        return found

    def _project_lines(self, as_user):
        Project = self.env['project.project'].sudo()
        projects = Project.search([])
        visible = writable = Project.browse()
        if as_user['project.project'].has_access('read'):
            visible = as_user['project.project'].search([])
            if as_user['project.project'].has_access('write'):
                writable = visible._filtered_access('write')
        can_tasks = as_user['project.task'].has_access('read')
        lines, task_seen, task_total = [], 0, 0
        for project in projects:
            total = self.env['project.task'].sudo().search_count([('project_id', '=', project.id)])
            seen = as_user['project.task'].search_count([('project_id', '=', project.id)]) if can_tasks else 0
            task_seen += seen
            task_total += total
            lines.append({
                'name': project.display_name,
                'can_read': project.id in visible.ids,
                'can_write': project.id in writable.ids,
                'task_visible': seen, 'task_total': total,
            })
        return {
            'project_line_ids': [Command.clear()] + [Command.create(v) for v in lines],
            'project_summary': _('Нийт %(t)s төслөөс %(v)s-д хандана, даалгавар %(s)s / %(a)s',
                                 t=len(projects), v=len(visible), s=task_seen, a=task_total),
        }

    def _channel_lines(self, user, as_user):
        Channel = self.env['discuss.channel'].sudo()
        channels = Channel.search([])
        visible_ids = set()
        if as_user['discuss.channel'].has_access('read'):
            visible_ids = set(as_user['discuss.channel'].search([]).ids)
        types = dict(Channel._fields['channel_type'].selection)
        lines = []
        for channel in channels:
            members = channel.channel_member_ids.partner_id
            name = channel.name or ', '.join(members.mapped('name')) or _('Нэргүй групп чат %s', channel.id)
            lines.append({
                'name': name,
                'channel_type': types.get(channel.channel_type, channel.channel_type),
                'is_member': user.partner_id in members,
                'can_read': channel.id in visible_ids,
                'member_count': len(members),
            })
        return {
            'channel_line_ids': [Command.clear()] + [Command.create(v) for v in lines],
            'channel_summary': _('Нийт %(t)s чатаас %(v)s-ийг харна', t=len(channels), v=len(visible_ids)),
        }

    def _action_lines(self, user):
        lines = []
        for seq, (category, label, groups, note) in enumerate(REVIEW_ACTIONS):
            if groups == 'residual':
                if 'isms.risk' not in self.env:
                    continue
                if user.has_group('university_isms.group_isms_manager'):
                    allowed, note = True, 'CISO: бүх эрсдэл'
                else:
                    own = self.env['isms.risk'].sudo().search_count([('owner_id', '=', user.id)])
                    allowed = bool(own)
                    note = _('Зөвхөн өөрийн %s эрсдэл', own) if own else 'Эрсдэлийн эзэн эсвэл CISO'
                lines.append({'sequence': seq, 'category': category, 'name': label,
                              'allowed': allowed, 'note': note})
                continue
            existing = [g for g in groups if self.env.ref(g, raise_if_not_found=False)]
            if not existing:
                continue
            names = ', '.join(self.env.ref(g).sudo().name for g in existing)
            lines.append({
                'sequence': seq, 'category': category, 'name': label,
                'allowed': any(user.has_group(g) for g in existing),
                'required_groups': names, 'note': note,
            })
        return lines

    def _hidden_categories(self):
        return self.env['ir.module.category'].sudo().browse([
            c.id for c in (self.env.ref('base.module_category_user_type', raise_if_not_found=False),
                           self.env.ref('base.module_category_hidden', raise_if_not_found=False)) if c])

    def _group_lines(self, user):
        hidden = self._hidden_categories()
        groups = self.env['res.groups'].sudo().search([('share', '=', False)])
        groups = groups.filtered(lambda g: g.category_id not in hidden)
        granted = user.groups_id
        lines = []
        for group in groups.sorted(lambda g: (g.category_id.name or 'zz', g.name)):
            parents = granted.filtered(lambda h: h != group and group in h.trans_implied_ids)
            lines.append({
                'group_id': group.id,
                'category': group.category_id.name or _('Бусад'),
                'granted': group in granted,
                'inherited': bool(parents) and group in granted,
                'implied_by': ', '.join(parents.mapped('name')),
            })
        return lines

    # ------------------------------------------------------------------ actions
    def action_refresh(self):
        self.ensure_one()
        self._check_manager()
        self.write(self._review_values(self.user_id))
        return True

    def action_apply_groups(self):
        """Сонгосон бүлгүүдээр хэрэглэгчийн эрхийг шинэчилнэ (A.5.18). Аудит логт бичигдэнэ."""
        self.ensure_one()
        self._check_manager()
        user = self.user_id
        if user == self.env.user:
            raise UserError(_('Өөрийн эрхийг өөрөө өөрчлөхгүй (A.5.3). Өөр эрх бүхий ажилтнаар өөрчлүүлнэ үү.'))
        protected = [self.env.ref(x, raise_if_not_found=False) for x in ('base.user_root', 'base.user_admin')]
        if user in protected:
            raise UserError(_('Үндсэн администраторын эрхийг энэ хэрэгслээр өөрчлөхгүй.'))
        hidden = self._hidden_categories()
        keep = user.groups_id.filtered(lambda g: g.category_id in hidden or g.share)
        wanted = self.group_line_ids.filtered('granted').group_id
        new_groups = keep | wanted
        before = user.groups_id
        after = new_groups | new_groups.trans_implied_ids
        changed = (after - before) | (before - after)
        privileged = self.env['res.groups'].browse([
            g.id for g in (self.env.ref(x, raise_if_not_found=False) for x in PRIVILEGED_GROUPS) if g])
        if changed & privileged and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Давуу эрх (%s)-ийг зөвхөн системийн администратор олгож, хураана (A.8.2).')
                              % ', '.join((changed & privileged).mapped('name')))
        new_conflicts = set(self._sod_conflicts(new_groups)) - set(self._sod_conflicts(before))
        if new_conflicts:
            raise UserError(_('Үүргийн тусгаарлалтын зөрчил үүснэ (A.5.3):\n%s') % '\n'.join(sorted(new_conflicts)))
        if set(new_groups.ids) != set(user.groups_id.ids):
            user.write({'groups_id': [Command.set(new_groups.ids)]})
        self.write(self._review_values(user))
        return True

    def action_open_user(self):
        self.ensure_one()
        self._check_manager()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'res.users', 'res_id': self.user_id.id,
            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'current',
        }


class AccessReviewModelLine(models.TransientModel):
    _name = 'access.review.model.line'
    _description = 'Эрхийн тойм: модел'
    _order = 'sequence, id'

    review_id = fields.Many2one('access.review', required=True, ondelete='cascade')
    sequence = fields.Integer()
    category = fields.Char('Ангилал')
    name = fields.Char('Хэсэг')
    model = fields.Char('Техникийн нэр')
    can_read = fields.Boolean('Унших')
    can_write = fields.Boolean('Засах')
    can_create = fields.Boolean('Үүсгэх')
    can_unlink = fields.Boolean('Устгах')
    visible_count = fields.Integer('Харах бичлэг')
    writable_count = fields.Integer('Засах боломжтой')
    total_count = fields.Integer('Нийт бичлэг')
    granted_by = fields.Char('Унших эрх олгосон бүлэг')


class AccessReviewProjectLine(models.TransientModel):
    _name = 'access.review.project.line'
    _description = 'Эрхийн тойм: төсөл'

    review_id = fields.Many2one('access.review', required=True, ondelete='cascade')
    name = fields.Char('Төсөл')
    can_read = fields.Boolean('Харах')
    can_write = fields.Boolean('Засах')
    task_visible = fields.Integer('Харах даалгавар')
    task_total = fields.Integer('Нийт даалгавар')


class AccessReviewChannelLine(models.TransientModel):
    _name = 'access.review.channel.line'
    _description = 'Эрхийн тойм: чат'

    review_id = fields.Many2one('access.review', required=True, ondelete='cascade')
    name = fields.Char('Чат')
    channel_type = fields.Char('Төрөл')
    member_count = fields.Integer('Гишүүд')
    is_member = fields.Boolean('Гишүүн')
    can_read = fields.Boolean('Харах')


class AccessReviewActionLine(models.TransientModel):
    _name = 'access.review.action.line'
    _description = 'Эрхийн тойм: бизнесийн үйлдэл'
    _order = 'sequence, id'

    review_id = fields.Many2one('access.review', required=True, ondelete='cascade')
    sequence = fields.Integer()
    category = fields.Char('Ангилал')
    name = fields.Char('Үйлдэл')
    allowed = fields.Boolean('Зөвшөөрөгдсөн')
    required_groups = fields.Char('Шаардлагатай бүлэг')
    note = fields.Char('Тайлбар')


class AccessReviewGroupLine(models.TransientModel):
    _name = 'access.review.group.line'
    _description = 'Эрхийн тойм: эрхийн бүлэг'

    review_id = fields.Many2one('access.review', required=True, ondelete='cascade')
    group_id = fields.Many2one('res.groups', 'Бүлэг')
    category = fields.Char('Апп')
    granted = fields.Boolean('Олгосон')
    inherited = fields.Boolean('Удамшсан')
    implied_by = fields.Char('Удамшуулсан бүлэг')


class ResUsers(models.Model):
    _inherit = 'res.users'

    def action_open_access_review(self):
        self.ensure_one()
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_('Хэрэглэгчийн эрхийг зөвхөн эрх өөрчлөх эрхтэй ажилтан харна.'))
        return {
            'type': 'ir.actions.act_window', 'name': _('Эрхийн тойм'), 'res_model': 'access.review',
            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'current',
            'context': {'default_user_id': self.id},
        }
