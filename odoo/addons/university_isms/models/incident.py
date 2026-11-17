"""Мэдээллийн аюулгүй байдлын инцидент (A.5.24–A.5.28, A.6.8).

Odoo Helpdesk нь Enterprise модуль тул Community-д өөрсдийн workflow:
Incident → Report → Investigate → Resolve → Close
"""
from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError

STATES = [
    ('incident', 'Incident (илэрсэн)'),
    ('report', 'Report (бүртгэсэн)'),
    ('investigate', 'Investigate (шалгаж буй)'),
    ('resolve', 'Resolve (шийдвэрлэсэн)'),
    ('close', 'Close (хаасан)'),
]
SEVERITIES = [
    ('low', 'Бага'),
    ('medium', 'Дунд'),
    ('high', 'Өндөр'),
    ('critical', 'Ноцтой'),
]
# Хариу өгөх/шийдвэрлэх хугацаа (цаг) — дотоод журмын санал
SLA_HOURS = {'low': 120, 'medium': 72, 'high': 24, 'critical': 4}


class IsmsIncident(models.Model):
    _name = 'isms.incident'
    _description = 'МАБ-ын инцидент'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'isms.audit.mixin']
    _order = 'detected_at desc, id desc'
    _rec_names_search = ['code', 'name']
    _isms_lock_code = True

    code = fields.Char('Дугаар', required=True, copy=False, readonly=True, default='/', index=True)
    name = fields.Char('Гарчиг', required=True, tracking=True)
    description = fields.Text('Юу болсон бэ?')
    state = fields.Selection(STATES, 'Үе шат', default='incident', required=True, tracking=True,
                             group_expand='_group_expand_states')
    category = fields.Selection([
        ('phishing', 'Фишинг'),
        ('malware', 'Хортой код / ransomware'),
        ('unauthorized_access', 'Зөвшөөрөлгүй хандалт'),
        ('account_compromise', 'Данс булаагдсан'),
        ('data_leak', 'Мэдээлэл задарсан'),
        ('integrity', 'Бүртгэл/дүн зөвшөөрөлгүй өөрчлөгдсөн'),
        ('dos', 'Үйлчилгээ тасалдсан / DoS'),
        ('physical', 'Физик (алдагдсан, хулгайлагдсан төхөөрөмж)'),
        ('policy_violation', 'Бодлого зөрчсөн'),
        ('other', 'Бусад'),
    ], 'Ангилал', required=True, default='other', tracking=True)
    severity = fields.Selection(SEVERITIES, 'Ноцтой байдал', required=True, default='medium', tracking=True)

    reporter_id = fields.Many2one('res.users', 'Мэдээлсэн', default=lambda self: self.env.user,
                                  required=True, tracking=True)
    reporter_type = fields.Selection([
        ('student', 'Оюутан'),
        ('faculty', 'Багш'),
        ('staff', 'Ажилтан'),
        ('external', 'Гадны этгээд'),
        ('system', 'Систем / мониторинг'),
    ], 'Мэдээлэгчийн төрөл', default='staff', required=True)
    assignee_id = fields.Many2one('res.users', 'Шалгагч (МАБ шинжээч)', tracking=True)

    detected_at = fields.Datetime('Илэрсэн', default=fields.Datetime.now, required=True, tracking=True)
    reported_at = fields.Datetime('Бүртгэсэн', readonly=True)
    investigation_at = fields.Datetime('Шалгаж эхэлсэн', readonly=True)
    resolved_at = fields.Datetime('Шийдвэрлэсэн', readonly=True)
    closed_at = fields.Datetime('Хаасан', readonly=True)
    sla_deadline = fields.Datetime('SLA хугацаа', compute='_compute_sla_deadline', store=True)
    sla_status = fields.Selection([
        ('on_track', 'Хугацаандаа'),
        ('breached', 'Хугацаа хэтэрсэн'),
        ('met', 'Хугацаандаа шийдсэн'),
    ], 'SLA төлөв', compute='_compute_sla_status', search='_search_sla_status')

    # Хөрөнгийн бүртгэл ба эрсдэл нь «Хязгаарлагдмал» мэдээлэл (A.5.12, A.8.3): энгийн мэдээлэгч
    # (багш, оюутан) холбоосыг харахгүй; МАБ-ын баг шалгалтын үед холбоно.
    asset_ids = fields.Many2many('isms.asset', 'isms_incident_asset_rel', 'incident_id', 'asset_id',
                                 string='Нөлөөлсөн хөрөнгө', tracking=True,
                                 groups='university_isms.group_isms_asset_owner,university_isms.group_isms_auditor')
    risk_ids = fields.Many2many('isms.risk', 'isms_incident_risk_rel', 'incident_id', 'risk_id',
                                string='Холбогдох эрсдэл',
                                groups='university_isms.group_isms_analyst,university_isms.group_isms_auditor')
    control_ids = fields.Many2many('isms.control', 'isms_incident_control_rel', 'incident_id', 'control_id',
                                   string='Холбогдох хяналт',
                                   groups='university_isms.group_isms_analyst,university_isms.group_isms_auditor')
    detection_key = fields.Char('Автомат илрүүлэлтийн түлхүүр', readonly=True, copy=False, index=True,
                                help='Мониторингийн дүрмээр (A.8.16) автоматаар үүссэн инцидентийн давхардлаас сэргийлэх')
    impact_c = fields.Boolean('Нууцлал (C)')
    impact_i = fields.Boolean('Бүрэн бүтэн байдал (I)')
    impact_a = fields.Boolean('Хүртээмж (A)')
    personal_data_breach = fields.Boolean('Хувийн мэдээллийн зөрчил', tracking=True)
    data_subjects_count = fields.Integer('Өртсөн мэдээллийн эзний тоо')
    notification_done = fields.Boolean('Холбогдох талд мэдэгдсэн', tracking=True)
    notification_note = fields.Text('Мэдэгдлийн тэмдэглэл')

    containment = fields.Text('Хязгаарлах арга хэмжээ (containment)')
    root_cause = fields.Text('Үндсэн шалтгаан')
    resolution = fields.Text('Авсан арга хэмжээ, шийдэл')
    lessons_learned = fields.Text('Сургамж (A.5.27)')

    _sql_constraints = [('code_uniq', 'unique(code)', 'Инцидентийн дугаар давхардахгүй.')]

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s %s' % (rec.code, rec.name) if rec.code and rec.code != '/' else rec.name

    def _group_expand_states(self, states, domain):
        return [key for key, _label in STATES]

    @api.depends('severity', 'detected_at', 'reported_at')
    def _compute_sla_deadline(self):
        for rec in self:
            start = rec.reported_at or rec.detected_at
            rec.sla_deadline = start and start + timedelta(hours=SLA_HOURS.get(rec.severity, 72))

    def _compute_sla_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.sla_deadline:
                rec.sla_status = False
            elif rec.resolved_at:
                rec.sla_status = 'met' if rec.resolved_at <= rec.sla_deadline else 'breached'
            else:
                rec.sla_status = 'breached' if now > rec.sla_deadline else 'on_track'

    def _search_sla_status(self, operator, value):
        if operator not in ('=', '!=', 'in', 'not in'):
            raise UserError(_('SLA төлөвөөр зөвхөн =, in хайлт хийнэ.'))
        wanted = {value} if isinstance(value, str) else set(value or [])
        self.env['isms.incident'].flush_model(['sla_deadline', 'resolved_at'])
        self.env.cr.execute("""
            SELECT id, CASE
                WHEN sla_deadline IS NULL THEN NULL
                WHEN resolved_at IS NOT NULL AND resolved_at <= sla_deadline THEN 'met'
                WHEN resolved_at IS NOT NULL THEN 'breached'
                WHEN (now() AT TIME ZONE 'UTC') > sla_deadline THEN 'breached'
                ELSE 'on_track' END
            FROM isms_incident""")
        ids = [row[0] for row in self.env.cr.fetchall() if row[1] in wanted]
        positive = operator in ('=', 'in')
        return [('id', 'in' if positive else 'not in', ids)]

    # ------------------------------------------------------------ monitoring (A.8.16)
    @api.model
    def _isms_detect_bruteforce(self, login, window_minutes=None, threshold=None):
        """Нэг нэвтрэх нэр дээрх амжилтгүй нэвтрэлт босгоос давбал автоматаар инцидент үүсгэнэ."""
        if not login:
            return self.browse()
        params = self.env['ir.config_parameter'].sudo()
        threshold = threshold or int(params.get_param('university_isms.bruteforce_threshold', 5))
        window_minutes = window_minutes or int(params.get_param('university_isms.bruteforce_window_minutes', 15))
        since = fields.Datetime.now() - timedelta(minutes=window_minutes)
        failures = self.env['isms.audit.log'].sudo().search([
            ('action', '=', 'login_failed'), ('login', '=', login), ('timestamp', '>=', since)])
        if len(failures) < threshold:
            return self.browse()
        key = 'bruteforce:%s' % login
        Incident = self.sudo().with_context(active_test=False)
        recent = Incident.search([('detection_key', '=', key), ('state', 'not in', ('resolve', 'close'))], limit=1)
        if recent:
            return recent
        ips = sorted({ip for ip in failures.mapped('ip_address') if ip})
        controls = self.env['isms.control'].sudo().search([('code', 'in', ('5.17', '8.5', '8.16'))])
        incident = Incident._isms_internal().create({
            'name': 'Автомат илрүүлэлт: «%s» данс руу олон удаагийн амжилтгүй нэвтрэлт' % login,
            'category': 'unauthorized_access',
            'severity': 'high',
            'reporter_id': SUPERUSER_ID,
            'reporter_type': 'system',
            'detected_at': min(failures.mapped('timestamp')),
            'detection_key': key,
            'impact_c': True,
            'control_ids': [(6, 0, controls.ids)],
            'description': ('%d минутад %d амжилтгүй нэвтрэлт (босго %d). IP: %s. Дүрэм: '
                            'university_isms.bruteforce_threshold / bruteforce_window_minutes (A.8.16).')
                           % (window_minutes, len(failures), threshold, ', '.join(ips) or 'тодорхойгүй'),
        })
        incident.action_report()
        # Дотоод token-той context-ийг дуудагч руу буцаахгүй (дараагийн хэрэглэгчийн үйлдэлд урсахаас сэргийлнэ)
        return self.browse(incident.ids)

    # ------------------------------------------------------------ security
    # Төлөв, хугацааны тэмдэг, мэдээлэгчийг зөвхөн сервер талын workflow өөрчилнө (RPC/kanban drag ч мөн
    # ижил шалгалтаар дамжина). UI товч дангаараа хамгаалалт биш.
    _PROTECTED = {'reported_at', 'investigation_at', 'resolved_at', 'closed_at', 'detection_key'}
    _REPORTER_FIELDS = {'name', 'description', 'category', 'severity', 'detected_at', 'reporter_type',
                         'asset_ids', 'impact_c', 'impact_i', 'impact_a', 'personal_data_breach',
                         'data_subjects_count'}
    _TRANSITIONS = {
        ('incident', 'report'): 'action_report',
        ('report', 'investigate'): 'action_investigate',
        ('investigate', 'resolve'): 'action_resolve',
        ('resolve', 'close'): 'action_close',
        ('resolve', 'investigate'): 'action_reopen',
        ('close', 'investigate'): 'action_reopen',
    }

    def _is_isms_team(self):
        return self.env.user.has_group('university_isms.group_isms_analyst')

    _LINK_FIELD_GROUPS = {
        'asset_ids': ('university_isms.group_isms_asset_owner', 'university_isms.group_isms_auditor'),
        'risk_ids': ('university_isms.group_isms_analyst',),
        'control_ids': ('university_isms.group_isms_analyst',),
    }

    def _check_link_fields(self, vals):
        """Odoo field `groups` нь create-д хамгаалдаггүй тул хязгаарлагдмал бүртгэлийн холбоосыг шалгана."""
        for fname, groups in self._LINK_FIELD_GROUPS.items():
            if fname in vals and not any(self.env.user.has_group(g) for g in groups):
                raise AccessError(_('«%s» талбарыг зөвхөн МАБ-ын баг холбоно.') % self._fields[fname].string)

    @api.model_create_multi
    def create(self, vals_list):
        if not self._isms_is_internal():
            for vals in vals_list:
                if vals.get('state', 'incident') != 'incident' or self._PROTECTED & set(vals):
                    raise AccessError(_('Инцидентийг зөвхөн «Incident» үе шатаас эхлүүлнэ.'))
                if not self._is_isms_team() and vals.get('reporter_id', self.env.uid) != self.env.uid:
                    raise AccessError(_('Өөр хүний нэрийн өмнөөс инцидент мэдээлэх эрхгүй.'))
                self._check_link_fields(vals)
        for vals in vals_list:
            if not vals.get('code') or vals['code'] == '/':
                vals['code'] = self._isms_next_code('isms.incident')
        return super().create(vals_list)

    def write(self, vals):
        if self._isms_is_internal():
            return super().write(vals)
        if self._PROTECTED & set(vals):
            raise AccessError(_('Үе шатын хугацааг гараар өөрчлөх боломжгүй.'))
        self._check_link_fields(vals)
        if not self._is_isms_team():
            forbidden = set(vals) - self._REPORTER_FIELDS - {'state'}
            forbidden = {f for f in forbidden if not f.startswith(('message_', 'activity_'))}
            if forbidden:
                raise AccessError(_('Мэдээлэгч дараах талбарыг өөрчлөх эрхгүй: %s') % ', '.join(sorted(forbidden)))
        vals = dict(vals)
        target = vals.pop('state', None)
        business = {k for k in vals if not k.startswith(('message_', 'activity_'))}
        if business and any(rec.state == 'close' for rec in self):
            raise UserError(_('Хаагдсан инцидентийг засах боломжгүй. CISO «Дахин нээх» шаардлагатай.'))
        res = super().write(vals) if vals else True
        if target:
            for rec in self.filtered(lambda r: r.state != target):
                method = self._TRANSITIONS.get((rec.state, target))
                if not method:
                    raise UserError(_('%s: «%s» → «%s» шилжилт зөвшөөрөгдөхгүй.') % (
                        rec.code, dict(STATES)[rec.state], dict(STATES)[target]))
                getattr(rec, method)()
        return res

    def _require_group(self, xmlid, label):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise AccessError(_('Энэ үйлдлийг зөвхөн %s гүйцэтгэнэ.') % label)

    # ------------------------------------------------------------ workflow
    def action_report(self):
        for rec in self.filtered(lambda r: r.state == 'incident'):
            rec._isms_internal().write({'state': 'report', 'reported_at': fields.Datetime.now()})
        return True

    def action_investigate(self):
        self._require_group('university_isms.group_isms_analyst', _('МАБ шинжээч'))
        for rec in self.filtered(lambda r: r.state == 'report'):
            rec._isms_internal().write({
                'state': 'investigate',
                'investigation_at': fields.Datetime.now(),
                'assignee_id': rec.assignee_id.id or self.env.user.id,
            })
        return True

    def action_resolve(self):
        self._require_group('university_isms.group_isms_analyst', _('МАБ шинжээч'))
        for rec in self.filtered(lambda r: r.state == 'investigate'):
            if not (rec.root_cause and rec.resolution):
                raise UserError(_('%s: «Үндсэн шалтгаан» болон «Авсан арга хэмжээ»-г бөглөнө үү.') % rec.code)
            if rec.personal_data_breach and not rec.notification_note:
                raise UserError(_('%s: хувийн мэдээллийн зөрчил — мэдээллийн эзэн, эрх бүхий байгууллагад '
                                  'мэдэгдэх эсэх шийдвэрийг «Мэдэгдлийн тэмдэглэл»-д бичнэ үү.') % rec.code)
            rec._isms_internal().write({'state': 'resolve', 'resolved_at': fields.Datetime.now()})
        return True

    def action_close(self):
        self._require_group('university_isms.group_isms_manager', _('МАБ менежер (CISO)'))
        for rec in self.filtered(lambda r: r.state == 'resolve'):
            if not rec.lessons_learned:
                raise UserError(_('%s: хаахаас өмнө «Сургамж»-ийг бичнэ үү (A.5.27).') % rec.code)
            rec._isms_internal().write({'state': 'close', 'closed_at': fields.Datetime.now()})
        return True

    def action_reopen(self):
        self._require_group('university_isms.group_isms_manager', _('МАБ менежер (CISO)'))
        self.filtered(lambda r: r.state in ('resolve', 'close'))._isms_internal().write(
            {'state': 'investigate', 'resolved_at': False, 'closed_at': False})
        return True
