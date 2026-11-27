"""Инцидентийн консол (WF-01, WF-02, WF-04).

Зарчим:
* Бүх уншилт ``self.env`` (хэрэглэгчийн эрх)-ээр явна: ACL, record rule, field groups.
  ``sudo()`` ашиглахгүй. Хандах эрхгүй бичлэг нь жагсаалтад огт орохгүй, detail дээр AccessError.
* Шилжилтийн жагсаалт нь үндсэн моделийн group дүрмийг (``isms.incident._require_group``-тэй
  ижил бүлгүүд) болон бичих эрхийг (``check_access('write')``) шалгаж тооцно. Энэ нь зөвхөн
  UI-д зориулсан мэдээлэл; жинхэнэ шалгалтыг ``action_*`` методууд өөрөө хийнэ.
* Helpdesk тасалбар, нотлох баримт, аудит лог зэргийг хэрэглэгчийн ORM эрхээр уншина;
  эрхгүй бол хоосон эсвэл ``available: False`` гэж буцаана (оршин байгаа эсэхийг илрүүлэхгүй).
"""
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext

ANALYST_GROUP = 'university_isms.group_isms_analyst'
MANAGER_GROUP = 'university_isms.group_isms_manager'
AUDITOR_GROUP = 'university_isms.group_isms_auditor'
REPORTER_GROUP = 'university_isms.group_isms_reporter'

# Үе шатын талбар: шалгалтын тэмдэглэл (view-д analyst/auditor-т харагдана)
INVESTIGATION_FIELDS = ('containment', 'root_cause', 'resolution', 'lessons_learned', 'notification_note')
INVESTIGATION_GROUPS = (ANALYST_GROUP, AUDITOR_GROUP)
EDITABLE_NOTE_FIELDS = ('containment', 'root_cause', 'resolution', 'lessons_learned', 'notification_note')
OPEN_STATES = ('incident', 'report', 'investigate')
CLOSED_STATES = ('resolve', 'close')
STATE_LABELS = {
    'incident': 'Илэрсэн',
    'report': 'Бүртгэсэн',
    'investigate': 'Шалгаж буй',
    'resolve': 'Шийдвэрлэсэн',
    'close': 'Хаасан',
}
SEVERITY_LABELS = {'low': 'Бага', 'medium': 'Дунд', 'high': 'Өндөр', 'critical': 'Ноцтой'}
LIST_LIMIT = 200
TIMELINE_LIMIT = 40
AUDIT_LIMIT = 30

# Үе шилжилтийн жагсаалт. ``group`` нь моделийн _require_group-тэй адил; ``role`` нь хэрэглэгчид
# харуулах тайлбар. Бүх шалгалтыг моделийн метод өөрөө дахин хийнэ.
TRANSITIONS = (
    {'action': 'action_report', 'label': 'Бүртгэх', 'sources': ('incident',),
     'target': 'report', 'group': None, 'role': None},
    {'action': 'action_investigate', 'label': 'Шалгаж эхлэх', 'sources': ('report',),
     'target': 'investigate', 'group': ANALYST_GROUP, 'role': 'МАБ шинжээч'},
    {'action': 'action_resolve', 'label': 'Шийдвэрлэснээр тэмдэглэх', 'sources': ('investigate',),
     'target': 'resolve', 'group': ANALYST_GROUP, 'role': 'МАБ шинжээч'},
    {'action': 'action_close', 'label': 'Зөрчил хаах', 'sources': ('resolve',),
     'target': 'close', 'group': MANAGER_GROUP, 'role': 'МАБ менежер (CISO)'},
    {'action': 'action_reopen', 'label': 'Дахин нээх', 'sources': ('resolve', 'close'),
     'target': 'investigate', 'group': MANAGER_GROUP, 'role': 'МАБ менежер (CISO)'},
)
TRANSITION_ACTIONS = {spec['action']: spec for spec in TRANSITIONS}


class FormulaIncidentConsole(models.AbstractModel):
    _name = 'formula.incident.console'
    _description = 'Инцидентийн консол (жагсаалт, дэлгэрэнгүй, шилжилт)'

    # ------------------------------------------------------------------ public API
    @api.model
    def get_incident_rows(self, filters=None):
        """Хэрэглэгчид харагдах инцидентүүд, SLA-гийн яаралтай байдлаар эрэмбэлсэн."""
        Incident = self.env['isms.incident']
        Incident.check_access('read')
        now = fields.Datetime.now()
        domain = self._build_domain(filters, now)
        active = [('state', 'in', OPEN_STATES)]
        overdue = [('sla_deadline', '<', now)]
        unassigned = [('assignee_id', '=', False)]
        records = Incident.search(domain + active, limit=LIST_LIMIT, order='sla_deadline asc, id desc')
        if len(records) < LIST_LIMIT:
            records |= Incident.search(domain + [('state', 'in', CLOSED_STATES)],
                                       limit=LIST_LIMIT - len(records), order='detected_at desc, id desc')
        total = Incident.search_count(domain)
        return {
            'rows': [self._row(rec, now) for rec in records],
            'summary': {
                'all': Incident.search_count([]) if domain else total,
                'open': Incident.search_count(active),
                'overdue': Incident.search_count(active + overdue),
                'unassigned': Incident.search_count(active + unassigned),
            },
            'total': total,
            'limit': LIST_LIMIT,
            'truncated': total > LIST_LIMIT,
            'generated_at': fields.Datetime.to_string(now),
            'filters': self._sanitize_filters(filters),
            'options': {
                'states': [{'key': k, 'label': v} for k, v in STATE_LABELS.items()],
                'severities': [{'key': k, 'label': v} for k, v in SEVERITY_LABELS.items()],
            },
        }

    @api.model
    def get_incident_detail(self, incident_id):
        """Нэг инцидентийн дэлгэрэнгүй. Хандах эрхгүй бол AccessError (ижил хариу, оршихгүй гэж илрүүлэхгүй)."""
        Incident = self.env['isms.incident']
        Incident.check_access('read')
        try:
            incident_id = int(incident_id)
        except (TypeError, ValueError):
            raise UserError(_('Инцидентийн дугаар буруу байна.'))
        rec = Incident.search([('id', '=', incident_id)], limit=1)
        if not rec:
            raise AccessError(_('Инцидент олдсонгүй эсвэл энэ бичлэгийг харах эрх байхгүй.'))
        now = fields.Datetime.now()
        investigation_visible = self._investigation_visible()
        detail = {
            'row': self._row(rec, now),
            'description': rec.description or '',
            'impact': {
                'c': bool(rec.impact_c), 'i': bool(rec.impact_i), 'a': bool(rec.impact_a),
                'personal_data_breach': bool(rec.personal_data_breach),
                'data_subjects_count': rec.data_subjects_count,
                'notification_done': bool(rec.notification_done),
            },
            'timestamps': {
                'detected_at': self._dt(rec.detected_at),
                'reported_at': self._dt(rec.reported_at),
                'investigation_at': self._dt(rec.investigation_at),
                'resolved_at': self._dt(rec.resolved_at),
                'closed_at': self._dt(rec.closed_at),
            },
            'assets': self._assets(rec),
            'attachment_count': self._attachment_count(rec),
            'ticket': self._helpdesk_ticket(rec),
            'investigation': self._investigation(rec) if investigation_visible else None,
            'investigation_visible': investigation_visible,
            'can_edit_investigation': self._can_edit_investigation(rec),
            'timeline': self._timeline(rec),
            'audit': self._audit(rec),
            'transitions': self._transitions(rec),
        }
        return detail

    @api.model
    def save_investigation(self, incident_id, values):
        """Шалгалтын тэмдэглэл хадгалах. Талбарыг жагсаалтаар хязгаарлана; ORM write эрхийг серверт шалгана."""
        Incident = self.env['isms.incident']
        Incident.check_access('write')
        rec = Incident.search([('id', '=', int(incident_id or 0))], limit=1)
        if not rec:
            raise AccessError(_('Инцидент олдсонгүй эсвэл энэ бичлэгийг засах эрх байхгүй.'))
        values = values if isinstance(values, dict) else {}
        clean = {}
        for fname in EDITABLE_NOTE_FIELDS:
            if fname in values:
                clean[fname] = values[fname] or False
        if not clean:
            raise UserError(_('Хадгалах талбар алга.'))
        rec.write(clean)
        return self.get_incident_detail(rec.id)

    # ------------------------------------------------------------------ filters
    @api.model
    def _sanitize_filters(self, filters):
        filters = filters if isinstance(filters, dict) else {}
        states = {key for key in STATE_LABELS}
        severities = set(SEVERITY_LABELS)
        state = filters.get('state') or ''
        severity = filters.get('severity') or ''
        query = filters.get('query')
        return {
            'state': state if isinstance(state, str) and state in states else '',
            'severity': severity if isinstance(severity, str) and severity in severities else '',
            'overdue': bool(filters.get('overdue')),
            'mine': bool(filters.get('mine')),
            'unassigned': filters.get('unassigned') is True,
            'open': filters.get('open') is True,
            'query': query.strip()[:100] if isinstance(query, str) else '',
        }

    @api.model
    def _build_domain(self, filters, now):
        clean = self._sanitize_filters(filters)
        domain = []
        if clean['state']:
            domain.append(('state', '=', clean['state']))
        if clean['severity']:
            domain.append(('severity', '=', clean['severity']))
        if clean['overdue']:
            domain += [('sla_deadline', '<', now)]
        if clean['unassigned']:
            domain += [('assignee_id', '=', False)]
        if clean['open'] or clean['overdue'] or clean['unassigned']:
            domain += [('state', 'in', OPEN_STATES)]
        if clean['mine']:
            domain += ['|', ('assignee_id', '=', self.env.uid), ('reporter_id', '=', self.env.uid)]
        if clean['query']:
            query = clean['query'].replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            domain += ['|', ('code', 'ilike', query), ('name', 'ilike', query)]
        return domain

    # ------------------------------------------------------------------ row helpers
    @api.model
    def _row(self, rec, now):
        is_open = rec.state not in CLOSED_STATES
        remaining = None
        if rec.sla_deadline:
            remaining = int((rec.sla_deadline - now).total_seconds())
        return {
            'id': rec.id,
            'code': rec.code,
            'name': rec.name,
            'state': rec.state,
            'state_label': STATE_LABELS.get(rec.state, rec.state),
            'severity': rec.severity,
            'severity_label': SEVERITY_LABELS.get(rec.severity, rec.severity),
            'category': rec.category,
            'category_label': dict(rec._fields['category'].selection).get(rec.category, rec.category),
            'detected_at': self._dt(rec.detected_at),
            'sla_deadline': self._dt(rec.sla_deadline),
            'sla_remaining_seconds': remaining if is_open else None,
            'sla_overdue': bool(is_open and remaining is not None and remaining < 0),
            'sla_status': rec.sla_status or False,
            'assignee': self._user(rec.assignee_id),
            'reporter': self._user(rec.reporter_id),
            'is_open': is_open,
        }

    @api.model
    def _dt(self, value):
        return fields.Datetime.to_string(value) if value else False

    @api.model
    def _user(self, user):
        if not user:
            return False
        return {'id': user.id, 'name': user.display_name}

    @api.model
    def _field_visible(self, record, fname):
        try:
            record.check_field_access_rights('read', [fname])
            return True
        except AccessError:
            return False

    @api.model
    def _investigation_visible(self):
        return any(self.env.user.has_group(group) for group in INVESTIGATION_GROUPS)

    @api.model
    def _investigation(self, rec):
        return {fname: getattr(rec, fname) or '' for fname in INVESTIGATION_FIELDS}

    @api.model
    def _can_edit_investigation(self, rec):
        if rec.state == 'close' or not self.env.user.has_group(ANALYST_GROUP):
            return False
        try:
            rec.check_access('write')
        except AccessError:
            return False
        return True

    @api.model
    def _assets(self, rec):
        if not self._field_visible(rec, 'asset_ids'):
            return {'available': False, 'items': []}
        try:
            items = [{'id': asset.id, 'name': asset.display_name} for asset in rec.asset_ids]
        except AccessError:
            return {'available': False, 'items': []}
        return {'available': True, 'items': items}

    @api.model
    def _attachment_count(self, rec):
        return self.env['ir.attachment'].search_count([
            ('res_model', '=', 'isms.incident'), ('res_id', '=', rec.id)])

    @api.model
    def _helpdesk_ticket(self, rec):
        """Холбогдох Helpdesk тасалбар; модуль суулгаагүй эсвэл харах эрхгүй бол None."""
        if 'helpdesk.ticket' not in self.env.registry:
            return None
        Ticket = self.env['helpdesk.ticket']
        if 'isms_incident_id' not in Ticket._fields or not Ticket.has_access('read'):
            return None
        ticket = Ticket.search([('isms_incident_id', '=', rec.id)], limit=1)
        if not ticket:
            return None
        return {'id': ticket.id, 'name': ticket.display_name,
                'stage': ticket.stage_id.display_name if ticket.stage_id else False}

    @api.model
    def _transitions(self, rec):
        result = []
        for spec in TRANSITIONS:
            if rec.state not in spec['sources']:
                continue
            reason = self._transition_block_reason(rec, spec)
            result.append({
                'action': spec['action'],
                'label': spec['label'],
                'target': spec['target'],
                'target_label': STATE_LABELS[spec['target']],
                'allowed': not reason,
                'reason': reason or '',
            })
        return result

    @api.model
    def _transition_block_reason(self, rec, spec):
        """Хоосон мөр = сервер энэ шилжилтийг зөвшөөрнө гэж тооцоолсон (UI-ийн мэдээлэл, баталгаа биш)."""
        if spec['group'] and not (self.env.su or self.env.user.has_group(spec['group'])):
            return 'Энэ шилжилтийг зөвхөн %s гүйцэтгэнэ.' % spec['role']
        try:
            rec.check_access('write')
        except AccessError:
            return 'Энэ бичлэгийг өөрчлөх эрх байхгүй.'
        if spec['action'] == 'action_resolve':
            missing = []
            if not rec.root_cause:
                missing.append('«Үндсэн шалтгаан»')
            if not rec.resolution:
                missing.append('«Авсан арга хэмжээ, шийдэл»')
            if rec.personal_data_breach and not rec.notification_note:
                missing.append('«Мэдэгдлийн тэмдэглэл»')
            if missing:
                return 'Эхлээд бөглөнө үү: %s.' % ', '.join(missing)
        if spec['action'] == 'action_close' and not rec.lessons_learned:
            return 'Эхлээд «Сургамж»-ийг бөглөнө үү.'
        return ''

    @api.model
    def _timeline(self, rec):
        Message = self.env['mail.message']
        messages = Message.search([
            ('model', '=', 'isms.incident'), ('res_id', '=', rec.id),
            ('message_type', 'in', ('comment', 'notification')),
        ], order='date desc, id desc', limit=TIMELINE_LIMIT)
        result = []
        for msg in messages:
            # mail.tracking.value нь зөвхөн base.group_system-д шууд харагддаг (Odoo chatter-ийн загвар).
            # Иймд sudo-оор уншиж, зөвхөн хэрэглэгчийн харах эрхтэй талбарын утгыг үлдээнэ
            # (_filter_has_field_access). Мессежийг хэрэглэгчийн ORM эрхээр л сонгоно.
            tracking = []
            values = msg.sudo().tracking_value_ids._filter_has_field_access(self.env)
            for tv in values:
                tracking.append({
                    'field': tv.field_id.field_description or '',
                    'old': tv.old_value_char or '',
                    'new': tv.new_value_char or '',
                })
            result.append({
                'id': msg.id,
                'date': self._dt(msg.date),
                'author': msg.author_id.display_name if msg.author_id else (msg.email_from or ''),
                'text': (html2plaintext(msg.body or '') or '').strip()[:500],
                'tracking': tracking,
            })
        return result

    @api.model
    def _audit(self, rec):
        Audit = self.env['isms.audit.log']
        if not Audit.has_access('read'):
            return {'available': False, 'items': []}
        logs = Audit.search([('model', '=', 'isms.incident'), ('res_id', '=', rec.id)],
                            order='timestamp desc, id desc', limit=AUDIT_LIMIT)
        items = [{
            'id': log.id,
            'timestamp': self._dt(log.timestamp),
            'action': log.action,
            'user': log.login or (log.user_id.display_name if log.user_id else ''),
            'changes': (log.changes or '')[:500],
        } for log in logs]
        return {'available': True, 'items': items}
