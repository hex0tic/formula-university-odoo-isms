"""Эрсдэлийн бүртгэл (ISO/IEC 27001:2022 Clause 6.1.2, 6.1.3, 8.2, 8.3).

Арга зүй — Лекц 8–9:
* Эрсдэлийн түвшин = Нөлөө × Магадлал (слайд 18)
* 5×5 матриц → Бага / Дунд / Өндөр (слайд 19)
* Хариу арга хэмжээ: Бууруулах, Шилжүүлэх, Зайлсхийх, Хүлээн зөвшөөрөх (слайд 22–23)
* 6 үе шаттай эрсдэлийн удирдлагын цикл (слайд 17)
"""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

LIKELIHOOD = [
    ('1', '1 — Маш ховор (жилд 1 удаа)'),
    ('2', '2 — Ховор (улиралд 1 удаа)'),
    ('3', '3 — Заримдаа (сард 1 удаа)'),
    ('4', '4 — Ихэвчлэн (долоо хоногт 1 удаа)'),
    ('5', '5 — Тогтмол (өдөр бүр)'),
]
IMPACT = [
    ('1', '1 — Маш бага'),
    ('2', '2 — Бага'),
    ('3', '3 — Дунд'),
    ('4', '4 — Өндөр'),
    ('5', '5 — Маш өндөр'),
]
LEVELS = [('low', 'Бага'), ('medium', 'Дунд'), ('high', 'Өндөр')]
LEVEL_RANK = {'none': 0, 'low': 1, 'medium': 2, 'high': 3}

# Лекц 8–9, слайд 19: мөр = магадлал (1..5), багана = нөлөөлөл (1..5)
RISK_MATRIX = {
    1: 'LLLLM',
    2: 'LLMMM',
    3: 'LMMMH',
    4: 'LMMHH',
    5: 'MMHHH',
}
_CODE_TO_LEVEL = {'L': 'low', 'M': 'medium', 'H': 'high'}


def matrix_level(likelihood, impact):
    if not likelihood or not impact:
        return False
    return _CODE_TO_LEVEL[RISK_MATRIX[int(likelihood)][int(impact) - 1]]


STATES = [
    ('identify', '1. Тодорхойлсон'),
    ('analyze', '2. Шинжилсэн'),
    ('evaluate', '3. Үнэлсэн'),
    ('respond', '4. Хариу арга хэмжээ'),
    ('implement', '5. Хэрэгжүүлж буй'),
    ('residual', '6. Үлдэгдэл эрсдэл хянах'),
]
NEXT_STATE = {a[0]: b[0] for a, b in zip(STATES, STATES[1:])}


class IsmsRisk(models.Model):
    _name = 'isms.risk'
    _description = 'Мэдээллийн аюулгүй байдлын эрсдэл'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'isms.audit.mixin']
    _order = 'score desc, code'
    _rec_names_search = ['code', 'name']
    _isms_lock_code = True

    code = fields.Char('Код', required=True, copy=False, readonly=True, default='/', index=True)
    name = fields.Char('Эрсдэл', required=True, tracking=True)
    description = fields.Text('Сценари / тайлбар')
    active = fields.Boolean(default=True, tracking=True)
    state = fields.Selection(STATES, 'Үе шат', default='identify', required=True, tracking=True,
                             group_expand='_group_expand_states')
    asset_ids = fields.Many2many('isms.asset', 'isms_asset_risk_rel', 'risk_id', 'asset_id',
                                 string='Хөрөнгө', tracking=True)
    threat_id = fields.Many2one('isms.threat', 'Аюул занал (Threat)', tracking=True)
    vulnerability_id = fields.Many2one('isms.vulnerability', 'Эмзэг байдал (Vulnerability)', tracking=True)
    owner_id = fields.Many2one('res.users', 'Эрсдэл хариуцагч', tracking=True,
                               default=lambda self: self.env.user)

    likelihood = fields.Selection(LIKELIHOOD, 'Магадлал (Likelihood)', required=True, default='3', tracking=True)
    impact = fields.Selection(IMPACT, 'Нөлөөлөл (Impact)', required=True, default='3', tracking=True)
    score = fields.Integer('Оноо (М×Н)', compute='_compute_scores', store=True)
    level = fields.Selection(LEVELS, 'Эрсдэлийн түвшин', compute='_compute_scores', store=True, tracking=True)

    treatment = fields.Selection([
        ('mitigate', 'Бууруулах (Mitigate)'),
        ('transfer', 'Шилжүүлэх (Transfer)'),
        ('avoid', 'Зайлсхийх (Avoid)'),
        ('accept', 'Хүлээн зөвшөөрөх (Accept)'),
    ], 'Хариу арга хэмжээ', tracking=True)
    treatment_plan = fields.Html('Хариу арга хэмжээний төлөвлөгөө')
    control_ids = fields.Many2many('isms.control', 'isms_risk_control_rel', 'risk_id', 'control_id',
                                   string='Annex A хяналт', tracking=True)
    due_date = fields.Date('Хэрэгжүүлэх хугацаа', tracking=True)
    accepted_by_id = fields.Many2one('res.users', 'Хүлээн зөвшөөрсөн', readonly=True, tracking=True)
    accepted_date = fields.Date('Хүлээн зөвшөөрсөн огноо', readonly=True)

    residual_likelihood = fields.Selection(LIKELIHOOD, 'Үлдэгдэл магадлал', tracking=True)
    residual_impact = fields.Selection(IMPACT, 'Үлдэгдэл нөлөөлөл', tracking=True)
    residual_score = fields.Integer('Үлдэгдэл оноо', compute='_compute_scores', store=True)
    residual_level = fields.Selection(LEVELS, 'Үлдэгдэл түвшин', compute='_compute_scores', store=True,
                                      tracking=True)
    current_level = fields.Selection(LEVELS, 'Одоогийн түвшин', compute='_compute_scores', store=True,
                                     help='Үлдэгдэл үнэлгээ хийгдсэн бол үлдэгдэл, эс бөгөөс анхны түвшин')

    task_ids = fields.One2many('project.task', 'isms_risk_id', 'Хариу арга хэмжээний даалгавар')
    task_count = fields.Integer('Даалгавар', compute='_compute_task_count')
    incident_ids = fields.Many2many('isms.incident', 'isms_incident_risk_rel', 'risk_id', 'incident_id',
                                    string='Холбогдох инцидент')
    is_overdue = fields.Boolean('Хугацаа хэтэрсэн', compute='_compute_is_overdue')

    _sql_constraints = [('code_uniq', 'unique(code)', 'Эрсдэлийн код давхардахгүй байх ёстой.')]

    # Хүлээн зөвшөөрөлт, үе шатыг зөвхөн сервер талын workflow өөрчилнө (RPC/kanban drag ч шалгагдана)
    _PROTECTED = {'accepted_by_id', 'accepted_date'}
    _ASSESSMENT_FIELDS = {'likelihood', 'impact', 'treatment', 'asset_ids'}

    @api.model_create_multi
    def create(self, vals_list):
        if not self._isms_is_internal():
            for vals in vals_list:
                if vals.get('state', 'identify') != 'identify' or self._PROTECTED & set(vals):
                    raise AccessError(_('Эрсдэлийг зөвхөн «1. Тодорхойлсон» үе шатаас эхлүүлнэ.'))
        for vals in vals_list:
            if not vals.get('code') or vals['code'] == '/':
                vals['code'] = self._isms_next_code('isms.risk')
        return super().create(vals_list)

    def write(self, vals):
        if self._isms_is_internal():
            return super().write(vals)
        if self._PROTECTED & set(vals):
            raise AccessError(_('Хүлээн зөвшөөрөлтийг зөвхөн CISO «Эрсдэлийг хүлээн зөвшөөрөх» үйлдлээр бүртгэнэ.'))
        vals = dict(vals)
        target = vals.pop('state', None)
        res = super().write(vals) if vals else True
        if self._ASSESSMENT_FIELDS & set(vals):
            # Үнэлгээ/шийдвэр өөрчлөгдвөл өмнөх хүлээн зөвшөөрөлт хүчингүй (CISO дахин батлах)
            accepted = self.filtered('accepted_by_id')
            if accepted:
                accepted._isms_internal().write({'accepted_by_id': False, 'accepted_date': False})
                for rec in accepted:
                    rec.message_post(body=_('Үнэлгээ өөрчлөгдсөн тул өмнөх хүлээн зөвшөөрөлт хүчингүй боллоо.'))
        if target:
            for rec in self.filtered(lambda r: r.state != target):
                if target == NEXT_STATE.get(rec.state):
                    rec.action_next_stage()
                elif target == 'identify':
                    rec.action_back_to_identify()
                else:
                    raise UserError(_('%s: «%s» → «%s» шилжилт зөвшөөрөгдөхгүй (үе шатыг алгасахгүй).') % (
                        rec.code, dict(STATES)[rec.state], dict(STATES)[target]))
        return res

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.name) if rec.code and rec.code != '/' else rec.name

    def _group_expand_states(self, states, domain):
        return [key for key, _label in STATES]

    @api.depends('likelihood', 'impact', 'residual_likelihood', 'residual_impact', 'state')
    def _compute_scores(self):
        for rec in self:
            rec.score = int(rec.likelihood or 0) * int(rec.impact or 0)
            rec.level = matrix_level(rec.likelihood, rec.impact)
            if rec.residual_likelihood and rec.residual_impact:
                rec.residual_score = int(rec.residual_likelihood) * int(rec.residual_impact)
                rec.residual_level = matrix_level(rec.residual_likelihood, rec.residual_impact)
            else:
                rec.residual_score = 0
                rec.residual_level = False
            rec.current_level = rec.residual_level if rec.state == 'residual' and rec.residual_level else rec.level

    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = bool(rec.due_date and rec.due_date < today and rec.state != 'residual')

    # ------------------------------------------------------------ workflow
    def _check_transition(self, target):
        for rec in self:
            if target == 'analyze' and not (rec.asset_ids and (rec.threat_id or rec.vulnerability_id)):
                raise UserError(_('%s: хөрөнгө болон аюул занал/эмзэг байдлыг тодорхойлно уу.') % rec.code)
            if target == 'respond' and not rec.level:
                raise UserError(_('%s: магадлал, нөлөөллийг үнэлнэ үү.') % rec.code)
            if target == 'implement':
                if not rec.treatment:
                    raise UserError(_('%s: хариу арга хэмжээг сонгоно уу.') % rec.code)
                if rec.treatment == 'accept' and not rec.accepted_by_id:
                    raise UserError(_('%s: «Хүлээн зөвшөөрөх» шийдвэрийг МАБ менежер (CISO) батлах ёстой.')
                                    % rec.code)
                if rec.treatment != 'accept' and not (rec.control_ids or rec.treatment_plan):
                    raise UserError(_('%s: Annex A хяналт эсвэл хариу арга хэмжээний төлөвлөгөө оруулна уу.')
                                    % rec.code)
            if target == 'residual' and not (rec.residual_likelihood and rec.residual_impact):
                raise UserError(_('%s: үлдэгдэл магадлал, нөлөөллийг үнэлнэ үү.') % rec.code)

    def _require_analyst(self):
        if not self.env.su and not self.env.user.has_group('university_isms.group_isms_analyst'):
            raise AccessError(_('Эрсдэлийн үе шатыг зөвхөн МАБ шинжээч өөрчилнө.'))

    def action_next_stage(self):
        self._require_analyst()
        for rec in self:
            target = NEXT_STATE.get(rec.state)
            if not target:
                continue
            rec._check_transition(target)
            rec._isms_internal().write({'state': target})
        return True

    def action_back_to_identify(self):
        self._require_analyst()
        self._isms_internal().write({'state': 'identify', 'accepted_by_id': False, 'accepted_date': False})

    def action_accept_risk(self):
        if not self.env.user.has_group('university_isms.group_isms_manager'):
            raise AccessError(_('Эрсдэлийг зөвхөн МАБ менежер (CISO) хүлээн зөвшөөрнө.'))
        for rec in self:
            if rec.state not in ('evaluate', 'respond'):
                raise UserError(_('%s: эрсдэлийг үнэлсний дараа (3–4-р үе шат) хүлээн зөвшөөрнө.') % rec.code)
            rec._isms_internal().write({
                'treatment': 'accept',
                'accepted_by_id': self.env.user.id,
                'accepted_date': fields.Date.context_today(self),
            })
            rec.message_post(body=_('Эрсдэлийг %s хүлээн зөвшөөрөв (түвшин: %s).')
                             % (self.env.user.name, dict(LEVELS).get(rec.level)))
        return True

    def action_create_task(self):
        self.ensure_one()
        project = self.env.ref('university_isms.project_risk_treatment')
        task = self.env['project.task'].create({
            'name': '[%s] %s — хариу арга хэмжээ' % (self.code, self.name),
            'project_id': project.id,
            'isms_risk_id': self.id,
            'user_ids': [(6, 0, self.owner_id.ids)],
            'date_deadline': self.due_date or (fields.Date.context_today(self) + timedelta(days=30)),
            'description': self.treatment_plan,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': task.id,
            'view_mode': 'form',
        }

    def action_open_tasks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Хариу арга хэмжээний даалгавар'),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('isms_risk_id', '=', self.id)],
            'context': {'default_isms_risk_id': self.id,
                        'default_project_id': self.env.ref('university_isms.project_risk_treatment').id},
        }
