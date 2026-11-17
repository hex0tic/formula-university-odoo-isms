"""ISMS-ийн хяналт, хэмжилт (Clause 9.1), удирдлагын дүн шинжилгээ (Clause 9.3), мониторинг (A.8.16).

* `_cron_daily_monitoring` — өдөр бүр: хянах хугацаа ойртсон бодлого, хугацаа хэтэрсэн эрсдэлийн
  хариу арга хэмжээ, SLA хэтэрсэн инцидентэд хариуцагчид нь Odoo activity (сануулга) үүсгэнэ.
* `_isms_kpis` — удирдлагын дүн шинжилгээний тайлан болон тестэд ашиглах үзүүлэлтүүд.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

REVIEW_SUMMARY = 'ISMS: бодлогыг дахин хянах'
RISK_SUMMARY = 'ISMS: эрсдэлийн хариу арга хэмжээний хугацаа хэтэрсэн'
SLA_SUMMARY = 'ISMS: инцидентийн SLA хэтэрсэн'


class IsmsMonitoring(models.AbstractModel):
    _name = 'isms.monitoring'
    _description = 'ISMS хяналт, мониторинг'

    # ------------------------------------------------------------ reminders
    @api.model
    def _schedule_once(self, record, summary, user, deadline, note):
        """Ижил бичлэг, хэрэглэгч, гарчигтай нээлттэй activity байхгүй бол нэгийг үүсгэнэ."""
        if not user or not user.active:
            return False
        exists = self.env['mail.activity'].sudo().search_count([
            ('res_model', '=', record._name), ('res_id', '=', record.id),
            ('user_id', '=', user.id), ('summary', '=', summary)])
        if exists:
            return False
        try:
            with self.env.cr.savepoint():
                record.sudo().activity_schedule(
                    'mail.mail_activity_data_todo', date_deadline=deadline,
                    summary=summary, note=note, user_id=user.id)
            return True
        except Exception:  # хариуцагч бичлэгийг унших эрхгүй гэх мэт — бусад сануулгыг зогсоохгүй
            _logger.warning('ISMS monitoring: activity skipped for %s,%s user %s',
                            record._name, record.id, user.login, exc_info=True)
            return False

    def _ciso_users(self):
        group = self.env.ref('university_isms.group_isms_manager')
        return group.users.filtered(lambda u: u.active and u.id != self.env.ref('base.user_root').id
                                    and u != self.env.ref('base.user_admin'))

    @api.model
    def _cron_daily_monitoring(self):
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        result = {'policy_review': 0, 'risk_overdue': 0, 'incident_sla': 0}
        cisos = self._ciso_users()

        policies = self.env['isms.policy'].sudo().search([
            ('state', '=', 'approved'), ('next_review_date', '!=', False),
            ('next_review_date', '<=', today + timedelta(days=30))])
        for policy in policies:
            user = policy.owner_id or cisos[:1]
            note = _('%s бодлогын дахин хянах огноо %s (A.5.1, Clause 7.5.2).') % (policy.code, policy.next_review_date)
            result['policy_review'] += self._schedule_once(policy, REVIEW_SUMMARY, user,
                                                           policy.next_review_date, note)

        risks = self.env['isms.risk'].sudo().search([
            ('due_date', '<', today), ('state', 'in', ('respond', 'implement'))])
        for risk in risks:
            note = _('%s: хэрэгжүүлэх хугацаа %s хэтэрсэн (Clause 6.1.3, 8.3).') % (risk.code, risk.due_date)
            result['risk_overdue'] += self._schedule_once(risk, RISK_SUMMARY, risk.owner_id or cisos[:1],
                                                          today, note)

        incidents = self.env['isms.incident'].sudo().search([
            ('state', 'not in', ('resolve', 'close')), ('sla_deadline', '<', now)])
        for incident in incidents:
            users = incident.assignee_id or cisos
            note = _('%s: SLA хугацаа %s хэтэрсэн (A.5.26).') % (incident.code, incident.sla_deadline)
            for user in users:
                result['incident_sla'] += self._schedule_once(incident, SLA_SUMMARY, user, today, note)
        _logger.info('ISMS monitoring: %s', result)
        return result

    # ------------------------------------------------------------ KPIs
    @api.model
    def _isms_kpis(self):
        env = self.env(su=True)
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        since = now - timedelta(days=30)

        def count(model, domain):
            return env[model].search_count(domain)

        def by(model, field, domain=None):
            selection = dict(env[model]._fields[field]._description_selection(env))
            groups = env[model]._read_group(domain or [], [field], ['__count'])
            data = {key: 0 for key in selection}
            for value, total in groups:
                if value:
                    data[value] = total
            return [(selection[key], data[key]) for key in selection]

        applicable = [('applicable', '=', True)]
        internal_users = env['res.users'].search([('share', '=', False), ('active', '=', True),
                                                  ('id', '!=', env.ref('base.user_root').id)])
        approved = env['isms.policy'].search([('state', '=', 'approved')])
        ack_users = len(set(approved.ack_ids.filtered(lambda a: a.version == a.policy_id.version).mapped('user_id').ids))
        tasks = env['project.task'].search([('isms_risk_id', '!=', False)])
        closed = env['isms.incident'].search([('resolved_at', '!=', False)])
        # Импортоор үе шатын цаг нь илэрсэн цагтай тэнцүү (0 цаг) бичигдсэн seed-ийг дунджид оруулахгүй
        hours = [h for h in ((i.resolved_at - (i.reported_at or i.detected_at)).total_seconds() / 3600
                             for i in closed if i.reported_at or i.detected_at) if h > 0]
        role_groups = [
            ('1. Мэдээлэгч', 'university_isms.group_isms_reporter'),
            ('2. Хөрөнгө эзэмшигч', 'university_isms.group_isms_asset_owner'),
            ('3. Дотоод аудитор', 'university_isms.group_isms_auditor'),
            ('4. МАБ шинжээч', 'university_isms.group_isms_analyst'),
            ('5. CISO', 'university_isms.group_isms_manager'),
            ('6. Odoo админ', 'base.group_system'),
        ]
        return {
            'date': today,
            'assets_total': count('isms.asset', []),
            'assets_pii': count('isms.asset', [('personal_data', '=', True)]),
            'assets_high_risk': count('isms.asset', [('risk_level', '=', 'high')]),
            'assets_by_class': by('isms.asset', 'classification'),
            'risks_total': count('isms.risk', []),
            'risks_by_level': by('isms.risk', 'level'),
            'risks_by_current': by('isms.risk', 'current_level'),
            'risks_by_state': by('isms.risk', 'state'),
            'risks_overdue': count('isms.risk', [('is_overdue', '=', True)]),
            'risks_accepted': count('isms.risk', [('treatment', '=', 'accept'), ('accepted_by_id', '!=', False)]),
            'risks_residual_approved': count('isms.risk', [('residual_accepted_by_id', '!=', False)]),
            'tasks_total': len(tasks),
            'tasks_done': len(tasks.filtered(lambda t: t.stage_id.fold or t.state in ('1_done', '1_canceled'))),
            'soa_total': count('isms.control', []),
            'soa_applicable': count('isms.control', applicable),
            'soa_by_impl': by('isms.control', 'implementation', applicable),
            'soa_selected': count('isms.control', [('selected', '=', True)]),
            'incidents_total': count('isms.incident', []),
            'incidents_by_state': by('isms.incident', 'state'),
            'incidents_by_severity': by('isms.incident', 'severity'),
            'incidents_sla_breached': count('isms.incident', [('sla_status', '=', 'breached')]),
            'incidents_pii': count('isms.incident', [('personal_data_breach', '=', True)]),
            'incidents_auto': count('isms.incident', [('detection_key', '!=', False)]),
            'incident_avg_hours': round(sum(hours) / len(hours), 1) if hours else 0,
            'incident_avg_hours_n': len(hours),
            'policies_approved': len(approved),
            'policies_review_due': count('isms.policy', [('state', '=', 'approved'),
                                                         ('next_review_date', '<=', today + timedelta(days=30))]),
            'policy_ack_users': ack_users,
            'users_internal': len(internal_users),
            'users_totp': len(internal_users.filtered(lambda u: u.totp_enabled))
            if 'totp_enabled' in internal_users._fields else 0,
            'users_by_role': [(label, len(env.ref(xmlid).users.filtered(lambda u: u.active and not u.share)))
                              for label, xmlid in role_groups],
            'failed_logins_30d': count('isms.audit.log', [('action', '=', 'login_failed'), ('timestamp', '>=', since)]),
            'access_changes_30d': count('isms.audit.log', [('action', '=', 'access_change'), ('timestamp', '>=', since)]),
            'audit_events_30d': count('isms.audit.log', [('timestamp', '>=', since)]),
        }


class ReportManagementReview(models.AbstractModel):
    _name = 'report.university_isms.report_management_review'
    _description = 'ISMS удирдлагын дүн шинжилгээний тайлан'

    @api.model
    def _get_report_values(self, docids, data=None):
        user = self.env.user
        if not (user.has_group('university_isms.group_isms_analyst')
                or user.has_group('university_isms.group_isms_auditor')):
            from odoo.exceptions import AccessError
            raise AccessError(_('Удирдлагын дүн шинжилгээний тайланг МАБ-ын баг ба аудитор үзнэ.'))
        companies = self.env['res.company'].browse(docids) or self.env.company
        return {
            'doc_ids': companies.ids,
            'doc_model': 'res.company',
            'docs': companies,
            'kpi': self.env['isms.monitoring']._isms_kpis(),
        }
