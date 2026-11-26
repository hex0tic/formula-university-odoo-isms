"""GOV-01: эрхийн дахин баталгаажуулалтын кампанит ажил ба мөр (ISO/IEC 27001 A.5.18)."""
import logging
from datetime import timedelta

from odoo import Command, _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError

from .governance_common import (
    ACTION_CONTEXT, NON_REVIEWABLE_GROUPS, SYSTEM_GROUP, is_manager, is_system,
    effective_groups, new_sod_conflicts, privileged_groups, soft_groups, unlink_groups,
)

_logger = logging.getLogger(__name__)

CADENCE = [('30', '30 хоног'), ('90', '90 хоног'), ('custom', 'Тохируулсан')]
SCOPE = [
    ('all', 'Бүх дотоод хэрэглэгч'),
    ('groups', 'Сонгосон эрхийн бүлгүүд'),
    ('privileged', 'Зөвхөн давуу эрхтнүүд'),
]
DECISION = [('pending', 'Хүлээгдэж буй'), ('keep', 'Баталсан (хадгална)'), ('revoke', 'Эрх хассан')]
ESCALATION_SUMMARY = 'Эрхийн тойм хугацаандаа дуусаагүй (эскалац)'
PROTECTED_LINE_FIELDS = {'decision', 'decided_at', 'decided_by_id', 'outcome', 'escalated', 'escalated_at'}
REVIEWER_EDITABLE_FIELDS = {'revoke_group_ids', 'note'}
MAX_ESCALATION_TARGETS = 5


class AccessRecertCampaign(models.Model):
    _name = 'access.recert.campaign'
    _description = 'Эрхийн дахин баталгаажуулалтын кампанит ажил'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'

    name = fields.Char('Нэр', required=True, tracking=True)
    cadence = fields.Selection(CADENCE, 'Давтамж', required=True, default='90', tracking=True)
    custom_days = fields.Integer('Тохируулсан хоног', default=180)
    cadence_days = fields.Integer('Давтамжийн хоног', compute='_compute_cadence_days', store=True)
    scope = fields.Selection(SCOPE, 'Хамрах хүрээ', required=True, default='privileged', tracking=True)
    group_ids = fields.Many2many('res.groups', 'access_recert_campaign_group_rel', 'campaign_id', 'group_id',
                                 'Хамрах бүлгүүд')
    fallback_reviewer_id = fields.Many2one('res.users', 'Нөөц хянагч (CISO)', tracking=True,
                                           domain=[('share', '=', False)])
    start_date = fields.Date('Эхлэх огноо', required=True, default=fields.Date.context_today, tracking=True)
    due_days = fields.Integer('Хугацаа (хоног)', required=True, default=14)
    due_date = fields.Date('Дуусах огноо', compute='_compute_due_date', store=True)
    state = fields.Selection([('draft', 'Ноорог'), ('running', 'Явагдаж буй'), ('done', 'Дууссан')],
                             'Төлөв', required=True, default='draft', tracking=True, copy=False)
    recurring = fields.Boolean('Автоматаар давтах', help='Үндсэн кампанитаас давтамжаар дараагийнх нь үүснэ.')
    parent_id = fields.Many2one('access.recert.campaign', 'Үндсэн кампанит ажил', index=True,
                                ondelete='set null', copy=False)
    line_ids = fields.One2many('access.recert.line', 'campaign_id', 'Мөрүүд', copy=False)
    line_count = fields.Integer('Мөрийн тоо', compute='_compute_line_stats')
    pending_count = fields.Integer('Хүлээгдэж буй', compute='_compute_line_stats')

    @api.depends('cadence', 'custom_days')
    def _compute_cadence_days(self):
        for rec in self:
            rec.cadence_days = {'30': 30, '90': 90}.get(rec.cadence, rec.custom_days or 0)

    @api.depends('start_date', 'due_days')
    def _compute_due_date(self):
        for rec in self:
            rec.due_date = rec.start_date + timedelta(days=rec.due_days) if rec.start_date else False

    @api.depends('line_ids.decision')
    def _compute_line_stats(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.pending_count = len(rec.line_ids.filtered(lambda l: l.decision == 'pending'))

    @api.constrains('cadence', 'custom_days', 'due_days', 'scope', 'group_ids')
    def _check_values(self):
        for rec in self:
            if rec.cadence == 'custom' and rec.custom_days < 1:
                raise ValidationError(_('Тохируулсан давтамж хамгийн багадаа 1 хоног байна.'))
            if rec.due_days < 1:
                raise ValidationError(_('Хугацаа хамгийн багадаа 1 хоног байна.'))
            if rec.scope == 'groups' and not rec.group_ids:
                raise ValidationError(_('"Сонгосон эрхийн бүлгүүд" хамрах хүрээнд бүлгүүдийг сонгоно уу.'))

    # ------------------------------------------------------------ lifecycle
    def action_start(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Зөвхөн ноорог кампанитыг эхлүүлнэ.'))
            rec.state = 'running'
            rec._generate_lines()
        return True

    def action_close(self):
        for rec in self:
            if rec.state != 'running':
                raise UserError(_('Зөвхөн явагдаж буй кампанитыг хаана.'))
            pending = rec.line_ids.filtered(lambda l: l.decision == 'pending')
            if pending:
                raise UserError(_('Бүх мөрийг шийдвэрлэсний дараа хаана уу. Үлдсэн: %s', len(pending)))
            rec.state = 'done'
        return True

    def _resolve_reviewer(self, user):
        """Ажилтны шууд менежер (hr.employee.parent_id), үгүй бол нөөц CISO хянагч.

        Хэрэглэгч өөрийгөө хянахгүй: тэр тохиолдолд нөөц хянагч руу шилжинэ.
        """
        Employee = self.env['hr.employee'].sudo()
        employee = Employee.search([('user_id', '=', user.id)], limit=1)
        manager = employee.parent_id.user_id.sudo() if employee and employee.parent_id else False
        if manager and manager != user and manager.active and not manager.share:
            return manager
        fallback = self.fallback_reviewer_id.sudo()
        if fallback and fallback != user and fallback.active:
            return fallback
        return self.env['res.users'].sudo().browse()

    def _generate_lines(self):
        """Хамрах хүрээнд нийцэх хэрэглэгч бүрт нэг мөр үүсгэнэ (давхардалгүй)."""
        self.ensure_one()
        Users = self.env['res.users'].sudo()
        excluded = soft_groups(self.env, NON_REVIEWABLE_GROUPS)
        priv = privileged_groups(self.env)
        existing = set(self.line_ids.mapped('user_id').ids)
        vals_list = []
        for user in Users.search([('share', '=', False), ('active', '=', True)]):
            if user.id in existing:
                continue
            held = (user.groups_id - excluded).filtered(lambda g: not g.share)
            if self.scope == 'groups':
                held &= self.group_ids
            elif self.scope == 'privileged':
                held &= priv
            if not held:
                continue
            reviewer = self._resolve_reviewer(user)
            vals_list.append({
                'campaign_id': self.id,
                'user_id': user.id,
                'reviewer_id': reviewer.id or False,
                'group_ids': [Command.set(held.ids)],
            })
        lines = self.env['access.recert.line'].sudo().create(vals_list) if vals_list else self.env['access.recert.line']
        for line in lines:
            if line.reviewer_id:
                line.sudo().activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=self.due_date,
                    summary=_('Эрхийн тойм: %s', line.user_id.name), user_id=line.reviewer_id.id)
        return lines

    # ------------------------------------------------------------ recurrence
    @api.model
    def _cron_create_recurring(self):
        """Давтамжаар дараагийн кампанитыг үүсгэнэ. Давхардахгүй (parent_id + start_date)."""
        today = fields.Date.context_today(self)
        roots = self.sudo().search([('recurring', '=', True), ('parent_id', '=', False), ('state', '!=', 'draft')])
        for root in roots:
            try:
                with self.env.cr.savepoint():
                    root._create_next_cycle(today)
            except Exception:
                _logger.exception('Access recert: recurring campaign %s failed', root.id)
                continue
            if not tools.config['test_enable']:
                self.env.cr.commit()
        return True

    def _create_next_cycle(self, today):
        self.ensure_one()
        cycles = self.search([('parent_id', '=', self.id)]) | self
        latest = max(cycles, key=lambda c: c.start_date)
        next_start = latest.start_date + timedelta(days=self.cadence_days)
        if next_start > today:
            return self.browse()
        start = max(next_start, today)
        if self.search_count([('parent_id', '=', self.id), ('start_date', '=', start)]):
            return self.browse()
        child = self.create({
            'name': '%s (%s)' % (self.name, start),
            'cadence': self.cadence,
            'custom_days': self.custom_days,
            'scope': self.scope,
            'group_ids': [Command.set(self.group_ids.ids)],
            'fallback_reviewer_id': self.fallback_reviewer_id.id or False,
            'start_date': start,
            'due_days': self.due_days,
            'parent_id': self.id,
            'recurring': False,
        })
        child.action_start()
        return child


class AccessRecertLine(models.Model):
    _name = 'access.recert.line'
    _description = 'Эрхийн дахин баталгаажуулалтын мөр'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'decision, due_date, id'
    _sql_constraints = [
        ('campaign_user_uniq', 'unique(campaign_id, user_id)', 'Нэг хэрэглэгч кампанит ажилд нэг мөртэй байна.'),
    ]

    campaign_id = fields.Many2one('access.recert.campaign', 'Кампанит ажил', required=True,
                                  ondelete='cascade', index=True)
    campaign_state = fields.Selection(related='campaign_id.state', string='Кампанитын төлөв')
    user_id = fields.Many2one('res.users', 'Хэрэглэгч', required=True, index=True)
    reviewer_id = fields.Many2one('res.users', 'Хянагч', index=True, tracking=True)
    group_ids = fields.Many2many('res.groups', 'access_recert_line_group_rel', 'line_id', 'group_id',
                                 'Одоогийн бүлгүүд (хамрагдсан)')
    revoke_group_ids = fields.Many2many('res.groups', 'access_recert_line_revoke_rel', 'line_id', 'group_id',
                                        'Хасах бүлгүүд')
    decision = fields.Selection(DECISION, 'Шийдвэр', required=True, default='pending', index=True, tracking=True)
    note = fields.Text('Хянагчийн тайлбар')
    decided_at = fields.Datetime('Шийдвэрлэсэн огноо', readonly=True, copy=False)
    decided_by_id = fields.Many2one('res.users', 'Шийдвэрлэсэн', readonly=True, copy=False)
    outcome = fields.Text('Үр дүн', readonly=True, copy=False)
    due_date = fields.Date('Дуусах огноо', related='campaign_id.due_date', store=True)
    overdue = fields.Boolean('Хугацаа хэтэрсэн', compute='_compute_overdue')
    escalated = fields.Boolean('Эскалац хийсэн', readonly=True, copy=False)
    escalated_at = fields.Datetime('Эскалац хийсэн огноо', readonly=True, copy=False)
    is_privileged = fields.Boolean('Давуу эрх', compute='_compute_is_privileged')

    @api.depends('decision', 'campaign_id.due_date')
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for line in self:
            line.overdue = bool(line.decision == 'pending' and line.due_date and line.due_date < today)

    @api.depends('group_ids')
    def _compute_is_privileged(self):
        priv = privileged_groups(self.env)
        for line in self:
            line.is_privileged = bool(line.group_ids & priv)

    @api.constrains('revoke_group_ids', 'group_ids')
    def _check_revoke_subset(self):
        for line in self:
            if line.revoke_group_ids - line.group_ids:
                raise ValidationError(_('Хасах бүлэг нь хамрагдсан бүлгүүдийн дотор байх ёстой.'))

    # ------------------------------------------------------------ guards
    def write(self, vals):
        if not self.env.su and not self.env.context.get(ACTION_CONTEXT):
            if set(vals) & PROTECTED_LINE_FIELDS:
                raise AccessError(_('Шийдвэрийг зөвхөн "Баталгаажуулах" / "Хасах" үйлдлээр гаргана (GOV-05).'))
            if not is_manager(self.env.user):
                if set(vals) - REVIEWER_EDITABLE_FIELDS:
                    raise AccessError(_('Та зөвхөн хасах бүлэг болон тайлбарыг засна.'))
                if any(line.decision != 'pending' for line in self):
                    raise AccessError(_('Шийдвэрлэсэн мөрийг засах боломжгүй.'))
        return super().write(vals)

    def _check_can_decide(self):
        self.ensure_one()
        actor = self.env.user
        if self.user_id == actor:
            raise AccessError(_('Өөрийн эрхийг өөрөө баталгаажуулахгүй (GOV-05).'))
        if self.campaign_id.state != 'running':
            raise UserError(_('Кампанит ажил идэвхтэй биш байна.'))
        if self.decision != 'pending':
            raise UserError(_('Энэ мөрийг аль хэдийн шийдвэрлэсэн байна.'))
        if self.reviewer_id != actor and not is_system(actor):
            raise AccessError(_('Зөвхөн томилогдсон хянагч энэ мөрийг шийдвэрлэнэ.'))

    def _record_decision(self, decision, outcome):
        actor = self.env.user
        self.sudo().with_context(**{ACTION_CONTEXT: True}).write({
            'decision': decision,
            'decided_at': fields.Datetime.now(),
            'decided_by_id': actor.id,
            'outcome': outcome,
        })
        self.sudo().message_post(body=outcome)

    # ------------------------------------------------------------ decisions
    def action_keep(self):
        for line in self:
            line._check_can_decide()
            line._record_decision('keep', _('Хэрэглэгчийн одоогийн эрхийг хадгалахаар баталсан.'))
        return True

    def action_revoke(self):
        for line in self:
            line._check_can_decide()
            actor = self.env.user
            groups = line.revoke_group_ids
            if not groups:
                raise UserError(_('Хасах бүлгээ сонгоно уу.'))
            if groups & privileged_groups(self.env) and not is_system(actor):
                raise AccessError(_('Давуу эрхийн бүлгийг (%s) зөвхөн системийн администратор хасна (A.8.2).',
                                    ', '.join(groups.mapped('name'))))
            target = line.user_id.sudo()
            removable = groups & target.groups_id
            after = target.groups_id - removable
            conflicts = new_sod_conflicts(self.env, target.groups_id, after)
            if conflicts:
                raise UserError(_('Үүргийн тусгаарлалтын зөрчил (A.5.3): %s', '; '.join(conflicts)))
            # Бүлгийн өөрчлөлт нь res.users.write-ээр явагдана: аудит лог хяналтын хүний нэрээр бичигдэнэ.
            unlink_groups(target, removable)
            still = groups & effective_groups(target.groups_id)
            if still:
                outcome = _('Бүлэг хасагдсан ч өөр бүлгээс удамшсан хэвээр: %s', ', '.join(still.mapped('name')))
            else:
                outcome = _('Хасагдсан бүлгүүд: %s', ', '.join(removable.mapped('name')) or _('байхгүй байсан'))
            line._record_decision('revoke', outcome)
        return True

    # ------------------------------------------------------------ escalation
    @api.model
    def _cron_escalate_overdue(self):
        """Хугацаа хэтэрсэн нээлттэй мөрийг нэг удаа эскалац хийнэ (давхардахгүй)."""
        today = fields.Date.context_today(self)
        lines = self.sudo().search([
            ('decision', '=', 'pending'), ('escalated', '=', False),
            ('campaign_id.state', '=', 'running'), ('campaign_id.due_date', '<', today),
        ])
        for line in lines:
            try:
                with self.env.cr.savepoint():
                    line._escalate()
            except Exception:
                _logger.exception('Access recert: escalation failed for line %s', line.id)
                continue
            if not tools.config['test_enable']:
                self.env.cr.commit()
        return True

    def _escalation_targets(self):
        self.ensure_one()
        campaign = self.campaign_id.sudo()
        if campaign.fallback_reviewer_id:
            return campaign.fallback_reviewer_id
        admins = self.env.ref(SYSTEM_GROUP).sudo().users.filtered(lambda u: u.active and not u.share)
        return admins.sorted('id')[:MAX_ESCALATION_TARGETS]

    def _escalate(self):
        self.ensure_one()
        line = self.sudo()
        today = fields.Date.context_today(self)
        for user in self._escalation_targets():
            line.activity_schedule('mail.mail_activity_data_todo', date_deadline=today,
                                   summary=ESCALATION_SUMMARY, user_id=user.id)
        now = fields.Datetime.now()
        line.with_context(**{ACTION_CONTEXT: True}).write({'escalated': True, 'escalated_at': now})
        line.message_post(body=_('Хугацаа хэтэрсэн: эрхийн тойм %s хийгдээгүй.', line.user_id.name))
        if 'isms.finding' in self.env:
            self.env['isms.finding'].sudo()._upsert_from_source(
                'audit', 'access.recert.line:%s' % line.id, {
                    'name': _('Эрхийн тойм хугацаандаа хийгдээгүй: %s', line.user_id.name),
                    'description': _('Кампанит ажил: %s. Эрхийн дахин баталгаажуулалтын мөр хугацаа хэтэрсэн.',
                                     line.campaign_id.name),
                    'severity': 'medium',
                    'owner_id': line.campaign_id.fallback_reviewer_id.id or False,
                })
        return True
