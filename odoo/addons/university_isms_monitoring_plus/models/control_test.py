"""Хяналтын тестийн төлөвлөгөө ба гүйцэтгэл (ISMS-02, ISMS-03, ISMS-04; ISO/IEC 27001:2022 9.1, A.8.15).

* `isms.control.test.plan`: Annex A хяналт бүрт гар аргын эсвэл автомат шалгалтын төлөвлөгөө.
* `isms.control.test.run`: гүйцэтгэлийн бүртгэл. Append-only: үүсгэснийг дараа нь засах,
  устгах боломжгүй (зөвхөн sudo / системийн эрхтэй үед).
* Цагийн товлолт `_run_due_plans` нь тохирсон хугацааны цонхонд нэг шалгалтыг зөвхөн нэг удаа
  ажиллуулна, алдаа бүрийг тусад нь барина, cron-ийг хэзээ ч унагахгүй.
"""
import logging
import time
from datetime import datetime, timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import config

from . import check_registry as reg

_logger = logging.getLogger(__name__)

GROUP_ANALYST = 'university_isms.group_isms_analyst'
GROUP_AUDITOR = 'university_isms.group_isms_auditor'
GROUP_MANAGER = 'university_isms.group_isms_manager'

RESULTS = [
    ('pass', 'Амжилттай'),
    ('fail', 'Бүтэлгүйтсэн'),
    ('error', 'Алдаа'),
    ('not_applicable', 'Хамааралгүй'),
]
FREQUENCY = [
    ('daily', 'Өдөр бүр'),
    ('weekly', 'Долоо хоног бүр'),
    ('monthly', 'Сар бүр'),
    ('quarterly', 'Улирал бүр'),
]
FREQUENCY_DELTA = {
    'daily': timedelta(days=1),
    'weekly': timedelta(days=7),
    'monthly': timedelta(days=30),
    'quarterly': timedelta(days=91),
}
SEVERITY = [('low', 'Бага'), ('medium', 'Дунд'), ('high', 'Өндөр'), ('critical', 'Ноцтой')]
TRIGGER = [('manual', 'Гар аргаар бүртгэсэн'), ('run_now', 'Одоо ажиллуулсан'), ('cron', 'Товлолтоор (систем)')]


def window_key(frequency, when):
    """Давтамжийн цонхны түлхүүр. Нэг цонхонд автомат шалгалт дахин ажиллахгүй."""
    day = when.date() if isinstance(when, datetime) else when
    if frequency == 'daily':
        return day.isoformat()
    if frequency == 'weekly':
        year, week, _weekday = day.isocalendar()
        return '%d-W%02d' % (year, week)
    if frequency == 'monthly':
        return '%d-%02d' % (day.year, day.month)
    return '%d-Q%d' % (day.year, (day.month - 1) // 3 + 1)


def _short(text, limit=500):
    text = str(text or '')
    return text if len(text) <= limit else text[:limit - 1] + '…'


class IsmsControlTestPlan(models.Model):
    _name = 'isms.control.test.plan'
    _description = 'ISMS хяналтын тестийн төлөвлөгөө'
    _inherit = ['mail.thread', 'isms.audit.mixin']
    _order = 'active desc, control_id, id'

    code = fields.Char('Дугаар', readonly=True, copy=False, default='/', index=True)
    name = fields.Char('Тестийн нэр', required=True, tracking=True)
    control_id = fields.Many2one('isms.control', 'Annex A хяналт', required=True, index=True,
                                 tracking=True, ondelete='restrict')
    description = fields.Text('Хамрах хүрээ, шалгах арга')
    method = fields.Selection([('manual', 'Гар аргаар'), ('automated', 'Автомат')],
                              'Арга', required=True, default='manual', tracking=True)
    check_key = fields.Selection(selection='_selection_check_keys', string='Автомат шалгалт',
                                 tracking=True)
    check_scope = fields.Text('Шалгалтын хүрээ', compute='_compute_check_info')
    check_label = fields.Char('Шалгалтын нэр', compute='_compute_check_info')
    severity = fields.Selection(SEVERITY, 'Ноцтой байдал (гар аргад)', required=True,
                                default='medium', tracking=True,
                                help='Гар аргын тест бүтэлгүйтэх үед үүсэх олдворын ноцтой байдал. '
                                     'Автомат шалгалтад шалгалтын тодорхойлолтын ноцтой байдал хэрэглэгдэнэ.')
    effective_severity = fields.Selection(SEVERITY, 'Олдворын ноцтой байдал',
                                          compute='_compute_check_info')
    frequency = fields.Selection(FREQUENCY, 'Давтамж', required=True, default='monthly', tracking=True)
    # Seed data is loaded by the superuser; do not make OdooBot the accountable owner.
    owner_id = fields.Many2one('res.users', 'Хариуцагч',
                               default=lambda self: self.env.user if self.env.uid != SUPERUSER_ID else False,
                               tracking=True)
    next_run_at = fields.Datetime('Дараагийн гүйцэтгэл', copy=False,
                                  help='Автомат шалгалтын хугацаа. Cron энэ цагаас хойш ажиллана.')
    active = fields.Boolean('Идэвхтэй', default=True, tracking=True)
    run_ids = fields.One2many('isms.control.test.run', 'plan_id', 'Гүйцэтгэлийн түүх')
    run_count = fields.Integer('Гүйцэтгэлийн тоо', compute='_compute_last')
    last_run_at = fields.Datetime('Сүүлд гүйцэтгэсэн', compute='_compute_last')
    last_result = fields.Selection(RESULTS, 'Сүүлийн үр дүн', compute='_compute_last')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Тестийн дугаар давтагдахгүй.'),
    ]

    # ------------------------------------------------------------ fields
    @api.model
    def _selection_check_keys(self):
        return reg.check_selection()

    @api.depends('check_key', 'severity')
    def _compute_check_info(self):
        for plan in self:
            spec = reg.CHECKS.get(plan.check_key) if plan.check_key else None
            plan.check_label = spec.label if spec else False
            plan.check_scope = spec.scope if spec else False
            plan.effective_severity = spec.severity if spec else plan.severity

    @api.depends('run_ids.executed_at', 'run_ids.result')
    def _compute_last(self):
        for plan in self:
            runs = plan.run_ids.sorted(key=lambda r: (r.executed_at, r.id))
            plan.run_count = len(runs)
            last = runs[-1:]
            plan.last_run_at = last.executed_at if last else False
            plan.last_result = last.result if last else False

    @api.constrains('method', 'check_key')
    def _check_method_and_key(self):
        for plan in self:
            if plan.method == 'automated' and not plan.check_key:
                raise ValidationError(_('Автомат тестэд автомат шалгалтын төрлийг заавал сонгоно.'))
            if plan.method == 'manual' and plan.check_key:
                raise ValidationError(_('Гар аргын тестэд автомат шалгалт сонгож болохгүй.'))

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if vals.get('code', '/') in (False, '/'):
                vals['code'] = self._isms_next_code('isms.control.test.plan')
            if vals.get('method') == 'automated' and not vals.get('next_run_at'):
                vals['next_run_at'] = now
        return super().create(vals_list)

    def _isms_audit_fields(self, fnames):
        # Цагийн товлолтын шинэчлэлт бүр аудит логийн мөр болж хуримтлагдахгүй байх
        return [f for f in super()._isms_audit_fields(fnames) if f != 'next_run_at']

    # ------------------------------------------------------------ permissions
    def _check_can_run_now(self):
        if self.env.su:
            return
        user = self.env.user
        if not (user.has_group(GROUP_ANALYST) or user.has_group(GROUP_MANAGER)):
            raise AccessError(_('Шалгалтыг одоо ажиллуулах эрх зөвхөн МАБ шинжээч эсвэл CISO-д байна.'))

    # ------------------------------------------------------------ actions
    def action_run_now(self):
        self.ensure_one()
        self._check_can_run_now()
        if self.method != 'automated' or not self.check_key:
            raise UserError(_('Зөвхөн автомат шалгалтыг одоо ажиллуулах боломжтой.'))
        self._execute(trigger='run_now', window_key=window_key(self.frequency, fields.Datetime.now()))
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'views': [(False, 'form')], 'target': 'current'}

    def action_record_manual_run(self):
        self.ensure_one()
        if self.method != 'manual':
            raise UserError(_('Автомат тестийн гүйцэтгэлийг гараар бүртгэх шаардлагагүй.'))
        create_view = self.env.ref('university_isms_monitoring_plus.isms_control_test_run_create_view')
        return {'type': 'ir.actions.act_window', 'name': _('Гар аргын гүйцэтгэл'),
                'res_model': 'isms.control.test.run', 'view_mode': 'form',
                'views': [(create_view.id, 'form')], 'target': 'new',
                'context': {'default_plan_id': self.id}}

    # ------------------------------------------------------------ execution
    def _schedule_next(self, now):
        self.ensure_one()
        self.sudo().write({'next_run_at': now + FREQUENCY_DELTA.get(self.frequency, timedelta(days=30))})

    def _execute(self, trigger, window_key=None):
        """Автомат шалгалтыг нэг удаа ажиллуулж гүйцэтгэлийн бүртгэл үүсгэнэ.

        Шалгалтын алдаа нь exception биш `result='error'` болж бүртгэгдэнэ. Олдворыг
        `_upsert_from_source` ашиглан давхардуулалгүй үүсгэнэ (зөвхөн системийн эрхээр)."""
        self.ensure_one()
        started = time.monotonic()
        now = fields.Datetime.now()
        spec = reg.CHECKS.get(self.check_key)
        result, details, error_message, metrics = 'error', '', False, {}
        if not spec:
            error_message = _('Бүртгэгдээгүй шалгалт: %s') % self.check_key
        else:
            try:
                with self.env.cr.savepoint():
                    outcome = spec.func(self.env)
                if not (isinstance(outcome, tuple) and len(outcome) == 3
                        and outcome[0] in (reg.PASS, reg.FAIL, reg.NOT_APPLICABLE)):
                    raise ValueError('Шалгалт буруу хариу буцаалаа.')
                result, details, metrics = outcome
            except Exception as exc:  # noqa: BLE001 - алдааг бүртгэнэ, дахин шидэхгүй
                _logger.exception('Control test %s (plan %s) failed', self.check_key, self.id)
                error_message = _short('%s: %s' % (type(exc).__name__, exc))
        finding = self.env['isms.finding']
        if result == reg.FAIL:
            try:
                with self.env.cr.savepoint():
                    finding, _created = self._upsert_finding(
                        'control_test', '%s:%s' % (self.check_key, self.id), spec.severity, details)
            except Exception as exc:  # noqa: BLE001
                _logger.exception('Finding for plan %s could not be created', self.id)
                result, error_message = 'error', _short('Олдвор үүсгэх алдаа: %s' % type(exc).__name__)
        if metrics:
            details = '%s\n%s' % (details, ', '.join('%s=%s' % kv for kv in sorted(metrics.items())))
        run = self.env['isms.control.test.run'].sudo().create({
            'plan_id': self.id,
            'executed_at': now,
            'trigger': trigger,
            'result': result,
            'details': _short(details, 4000),
            'duration_ms': int((time.monotonic() - started) * 1000),
            'error_message': error_message,
            'finding_id': finding.id or False,
            'window_key': window_key or False,
        })
        self._schedule_next(now)
        return run

    def _upsert_finding(self, source, source_key, severity, details):
        """Олдвор үүсгэх/шинэчлэх (системийн эрхээр). Буцаах: (олдвор, шинээр үүссэн эсэх)."""
        self.ensure_one()
        vals = {
            'name': _('Хяналтын тест бүтэлгүйтсэн: %s') % self.name,
            'description': _short(details, 2000),
            'severity': severity,
            'control_id': self.control_id.id,
            'owner_id': self.owner_id.id or False,
        }
        return self.env['isms.finding'].sudo()._upsert_from_source(source, source_key, vals)

    @api.model
    def _run_due_plans(self, time_budget=240, max_plans=200):
        """Cron: хугацаа нь болсон автомат шалгалтуудыг нэг нэгээр ажиллуулна.

        * Нэг шалгалтын алдаа бусдыг зогсоохгүй; алдааг `error` гүйцэтгэлээр бүртгэнэ.
        * Цагийн төсөв хэтэрвэл үлдсэнийг дараагийн cron дээр хийнэ.
        * Цонх бүрт шалгалт нэг удаа: ижил цонхонд гүйцэтгэл байвал дахин ажиллуулахгүй.
        * Exception шидэхгүй (бүх алдааг лог + summary-д буцаана).
        """
        summary = {'processed': 0, 'skipped': 0, 'errors': 0, 'stopped_on_budget': False}
        started = time.monotonic()
        try:
            now = fields.Datetime.now()
            plans = self.sudo().search([
                ('active', '=', True), ('method', '=', 'automated'), ('check_key', '!=', False),
                '|', ('next_run_at', '=', False), ('next_run_at', '<=', now),
            ], order='next_run_at, id', limit=max_plans)
        except Exception:  # noqa: BLE001
            _logger.exception('Control test scheduler could not load due plans')
            return summary
        for plan in plans:
            if time.monotonic() - started > time_budget:
                summary['stopped_on_budget'] = True
                break
            window = False
            try:
                window = window_key(plan.frequency, now)
                done = self.env['isms.control.test.run'].sudo().search_count([
                    ('plan_id', '=', plan.id), ('window_key', '=', window)])
                if done:
                    summary['skipped'] += 1
                    plan._schedule_next(now)
                else:
                    plan._execute(trigger='cron', window_key=window)
                    summary['processed'] += 1
            except Exception:  # noqa: BLE001
                _logger.exception('Control test plan %s could not run', plan.id)
                summary['errors'] += 1
                self._record_scheduler_error(plan, window, now)
            self._commit_between_plans()
        _logger.info('Control test scheduler: %s', summary)
        return summary

    def _commit_between_plans(self):
        # Cron-д план бүрийн дараа commit хийснээр цагийн төсвөөс хойшхи ажил алдагдахгүй.
        # TransactionCase-д cr.commit хориотой тул тестийн горимд (--test-enable) алгасна.
        if config.get('test_enable'):
            return
        self.env.cr.commit()

    def _record_scheduler_error(self, plan, window, now):
        try:
            with self.env.cr.savepoint():
                self.env['isms.control.test.run'].sudo().create({
                    'plan_id': plan.id,
                    'executed_at': now,
                    'trigger': 'cron',
                    'result': 'error',
                    'details': '',
                    'error_message': _('Товлолтын алдаа; дэлгэрэнгүйг серверийн логоос харна уу.'),
                    'window_key': window or False,
                })
                plan._schedule_next(now)
        except Exception:  # noqa: BLE001
            _logger.exception('Could not store scheduler error for plan %s', plan.id)


class IsmsControlTestRun(models.Model):
    _name = 'isms.control.test.run'
    _description = 'ISMS хяналтын тестийн гүйцэтгэл'
    _order = 'executed_at desc, id desc'

    plan_id = fields.Many2one('isms.control.test.plan', 'Төлөвлөгөө', required=True,
                              ondelete='restrict', index=True)
    control_id = fields.Many2one(related='plan_id.control_id', store=True, index=True,
                                 string='Annex A хяналт')
    method = fields.Selection(related='plan_id.method', store=True, string='Арга')
    executed_at = fields.Datetime('Гүйцэтгэсэн огноо', required=True, default=fields.Datetime.now,
                                  readonly=True)
    executed_by_id = fields.Many2one('res.users', 'Гүйцэтгэсэн', required=True,
                                     default=lambda self: self.env.user, readonly=True)
    trigger = fields.Selection(TRIGGER, 'Эх үүсвэр', required=True, default='manual', readonly=True)
    result = fields.Selection(RESULTS, 'Үр дүн', required=True)
    details = fields.Text('Хэмжилт, дэлгэрэнгүй')
    evidence_text = fields.Text('Нотолгоо (гар аргын тест)',
                                help='Гар аргаар хийсэн шалгалтын нотолгооны тайлбар. Нууц утга оруулахгүй.')
    duration_ms = fields.Integer('Хугацаа (ms)', readonly=True)
    error_message = fields.Text('Алдааны мэдээлэл', readonly=True)
    finding_id = fields.Many2one('isms.finding', 'Олдвор', readonly=True, ondelete='set null')
    window_key = fields.Char('Цонх', readonly=True, index=True)

    # ------------------------------------------------------------ create only
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            user = self.env.user
            if not any(user.has_group(g) for g in (GROUP_ANALYST, GROUP_AUDITOR, GROUP_MANAGER)):
                raise AccessError(_('Гүйцэтгэл бүртгэх эрх байхгүй.'))
            Plan = self.env['isms.control.test.plan'].sudo()
            for vals in vals_list:
                plan = Plan.browse(vals.get('plan_id'))
                if plan.method != 'manual':
                    raise UserError(_('Автомат тестийн гүйцэтгэлийг товлолт эсвэл "Одоо ажиллуулах" бүртгэнэ.'))
                # Серверийн талд зөвхөн гар аргын бүртгэл, системийн талбар хуурамчаар оруулахгүй
                vals.update({'trigger': 'manual', 'executed_by_id': user.id,
                             'executed_at': fields.Datetime.now(), 'duration_ms': 0,
                             'error_message': False, 'window_key': False, 'finding_id': False})
                if vals.get('result') == 'fail':
                    finding, _created = plan._upsert_finding(
                        'control_test', 'manual:%s' % plan.id, plan.severity,
                        vals.get('details') or plan.name)
                    vals['finding_id'] = finding.id
        return super().create(vals_list)

    # ------------------------------------------------------------ append-only
    def write(self, vals):
        if not self.env.su:
            raise UserError(_('Гүйцэтгэлийн бүртгэлийг өөрчлөх боломжгүй (append-only, ISO/IEC 27001:2022 A.8.15).'))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_('Гүйцэтгэлийн бүртгэлийг устгах боломжгүй (append-only, ISO/IEC 27001:2022 A.8.15).'))
        return super().unlink()
