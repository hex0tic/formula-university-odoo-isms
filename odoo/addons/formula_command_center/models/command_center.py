"""ISMS Command Center: эрхийн ORM дүрмээр шүүгдсэн KPI ба heatmap.

Зарчим:
* Бүх тоо ``self.env`` (хэрэглэгчийн эрх)-ээр тооцогдоно; ``sudo()`` ашиглахгүй. Record rule
  ба ACL нь тоонд автоматаар нөлөөлнө.
* Модел уншиж чадахгүй хэрэглэгчид тухайн хэсгийг ``available: False`` гэж буцаана; тоо
  огт гаргахгүй.
* Drill-down: KPI бүр ``{model, domain, name}`` тодорхойлогчтой. Domain нь серверт баригдсан
  (whitelisted) утгуудаас бүрдэнэ; клиент талаас ирсэн domain хүлээн авахгүй.
"""
from datetime import timedelta

from odoo import _, api, fields, models

from odoo.addons.university_isms.models.risk import IMPACT, LEVELS, LIKELIHOOD, matrix_level

INCIDENT_PERIODS = (0, 30, 90, 365)  # 0 = бүх хугацаа
OPEN_INCIDENT_STATES = ['incident', 'report', 'investigate']
TONES = ('neutral', 'success', 'warning', 'danger')


def _drill(model, domain, name):
    return {'model': model, 'domain': list(domain), 'name': name}


class FormulaCommandCenter(models.AbstractModel):
    _name = 'formula.command.center'
    _description = 'ISMS Command Center (KPI, heatmap, drill-down)'

    # ------------------------------------------------------------------ public API
    @api.model
    def get_dashboard_data(self, filters=None):
        """Хэрэглэгчийн эрхээр шүүгдсэн dashboard өгөгдөл (JSON-safe)."""
        filters = self._sanitize_filters(filters)
        today = fields.Date.context_today(self)
        cutoff = fields.Datetime.now() - timedelta(days=filters['incident_days']) \
            if filters['incident_days'] else None
        # Домайн дотор string хэлбэрээр байна: клиент рүү JSON-safe domain явна
        ctx = {'today': fields.Date.to_string(today),
               'cutoff': fields.Datetime.to_string(cutoff) if cutoff else None}

        sections = {
            'assets': self._section_assets(ctx),
            'risks': self._section_risks(ctx),
            'heatmap': self._section_heatmap(),
            'controls': self._section_controls(),
            'incidents': self._section_incidents(ctx),
            'policies': self._section_policies(ctx),
            'treatment': self._section_treatment(ctx),
            'audit': self._section_audit(),
        }
        return {
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
            'filters': filters,
            'incident_period_options': list(INCIDENT_PERIODS),
            'kpis': self._build_kpis(sections),
            'sections': sections,
        }

    # ------------------------------------------------------------------ helpers
    @api.model
    def _sanitize_filters(self, filters):
        filters = filters if isinstance(filters, dict) else {}
        try:
            days = int(filters.get('incident_days') or 0)
        except (TypeError, ValueError):
            days = 0
        if days not in INCIDENT_PERIODS:
            days = 0
        return {'incident_days': days}

    @api.model
    def _can_read(self, model):
        return bool(self.env[model].has_access('read'))

    @api.model
    def _unavailable(self, model):
        return {'available': False, 'model': model,
                'reason': _('Энэ мэдээллийг харах эрх байхгүй.')}

    @api.model
    def _selection_labels(self, model, fname):
        field_info = self.env[model].fields_get([fname], attributes=['selection'])
        return field_info.get(fname, {}).get('selection', [])

    @api.model
    def _group_counts(self, model, base_domain, fname, selection, drill_name):
        """Нэг read_group-ээр бүлэглэсэн тоо; бүх сонголтыг (0-тэй ч) буцаана."""
        rows = self.env[model]._read_group(base_domain, groupby=[fname], aggregates=['__count'])
        counts = {value: count for value, count in rows}
        result = []
        for key, label in selection:
            domain = list(base_domain) + [(fname, '=', key)]
            result.append({
                'key': key,
                'label': label,
                'count': counts.get(key, 0),
                'drill': _drill(model, domain, '%s: %s' % (drill_name, label)),
            })
        return result

    @api.model
    def _count(self, model, domain):
        return self.env[model].search_count(domain)

    # ------------------------------------------------------------------ sections
    @api.model
    def _section_assets(self, ctx):
        model = 'isms.asset'
        if not self._can_read(model):
            return self._unavailable(model)
        high_domain = [('risk_level', '=', 'high')]
        return {
            'available': True,
            'total': self._count(model, []),
            'high_risk': self._count(model, high_domain),
            'by_classification': self._group_counts(
                model, [], 'classification',
                self._selection_labels(model, 'classification'), _('Хөрөнгө')),
            'drill_total': _drill(model, [], _('Хөрөнгийн бүртгэл')),
            'drill_high_risk': _drill(model, high_domain, _('Өндөр эрсдэлтэй хөрөнгө')),
        }

    @api.model
    def _section_risks(self, ctx):
        model = 'isms.risk'
        if not self._can_read(model):
            return self._unavailable(model)
        accepted_domain = [('treatment', '=', 'accept'), ('accepted_by_id', '!=', False)]
        open_domain = [('accepted_by_id', '=', False)]
        residual_domain = [('residual_level', '!=', False)]
        return {
            'available': True,
            'total': self._count(model, []),
            'open': self._count(model, open_domain),
            'accepted': self._count(model, accepted_domain),
            'residual_assessed': self._count(model, residual_domain),
            'high': self._count(model, [('level', '=', 'high')]),
            'by_level': self._group_counts(model, [], 'level', LEVELS, _('Эрсдэл')),
            'residual_by_level': self._group_counts(
                model, residual_domain, 'residual_level', LEVELS, _('Үлдэгдэл эрсдэл')),
            'drill_total': _drill(model, [], _('Эрсдэлийн бүртгэл')),
            'drill_open': _drill(model, open_domain, _('Нээлттэй эрсдэл')),
            'drill_accepted': _drill(model, accepted_domain, _('Батлагдсан хүлээн зөвшөөрөлт')),
            'drill_high': _drill(model, [('level', '=', 'high')], _('Өндөр эрсдэл')),
        }

    @api.model
    def _heatmap_mode(self, model, base_domain, lfield, ifield, title):
        """5x5 тор: мөр = магадлал 5..1, багана = нөлөөлөл 1..5."""
        counts = {}
        domain = list(base_domain) + [(lfield, '!=', False), (ifield, '!=', False)]
        for lik, imp, count in self.env[model]._read_group(
                domain, groupby=[lfield, ifield], aggregates=['__count']):
            counts[(lik, imp)] = count
        cells = []
        for lik_key, _lik_label in LIKELIHOOD:
            for imp_key, _imp_label in IMPACT:
                cell_domain = list(base_domain) + [(lfield, '=', lik_key), (ifield, '=', imp_key)]
                cells.append({
                    'likelihood': lik_key,
                    'impact': imp_key,
                    'score': int(lik_key) * int(imp_key),
                    'level': matrix_level(lik_key, imp_key),
                    'count': counts.get((lik_key, imp_key), 0),
                    'drill': _drill(model, cell_domain,
                                    _('%s: магадлал %s, нөлөөлөл %s') % (title, lik_key, imp_key)),
                })
        return {'total': sum(counts.values()), 'cells': cells}

    @api.model
    def _section_heatmap(self):
        model = 'isms.risk'
        if not self._can_read(model):
            return self._unavailable(model)
        return {
            'available': True,
            'inherent': self._heatmap_mode(model, [], 'likelihood', 'impact', _('Анхдагч эрсдэл')),
            'residual': self._heatmap_mode(model, [], 'residual_likelihood', 'residual_impact',
                                           _('Үлдэгдэл эрсдэл')),
        }

    @api.model
    def _section_controls(self):
        model = 'isms.control'
        if not self._can_read(model):
            return self._unavailable(model)
        selected_domain = [('selected', '=', True)]
        return {
            'available': True,
            'catalog': self._count(model, []),
            'selected': self._count(model, selected_domain),
            'by_implementation': self._group_counts(
                model, selected_domain, 'implementation',
                self._selection_labels(model, 'implementation'), _('Хяналт')),
            'drill_catalog': _drill(model, [], _('Annex A хяналт')),
            'drill_selected': _drill(model, selected_domain, _('Сонгосон хяналт')),
        }

    @api.model
    def _section_incidents(self, ctx):
        model = 'isms.incident'
        if not self._can_read(model):
            return self._unavailable(model)
        base = [('detected_at', '>=', ctx['cutoff'])] if ctx['cutoff'] else []
        open_domain = base + [('state', '!=', 'close')]
        overdue_domain = base + [('state', 'in', OPEN_INCIDENT_STATES), ('sla_status', '=', 'breached')]
        on_track_domain = base + [('state', 'in', OPEN_INCIDENT_STATES), ('sla_status', '=', 'on_track')]
        return {
            'available': True,
            'open': self._count(model, open_domain),
            'sla_overdue': self._count(model, overdue_domain),
            'sla_on_track': self._count(model, on_track_domain),
            'by_state': self._group_counts(model, base, 'state',
                                           self._selection_labels(model, 'state'), _('Инцидент')),
            'open_by_severity': self._group_counts(model, open_domain, 'severity',
                                                   self._selection_labels(model, 'severity'),
                                                   _('Нээлттэй инцидент')),
            'drill_open': _drill(model, open_domain, _('Нээлттэй инцидент')),
            'drill_overdue': _drill(model, overdue_domain, _('SLA хугацаа хэтэрсэн инцидент')),
            'drill_on_track': _drill(model, on_track_domain, _('SLA хугацаандаа буй инцидент')),
        }

    @api.model
    def _section_policies(self, ctx):
        model = 'isms.policy'
        if not self._can_read(model):
            return self._unavailable(model)
        approved = [('state', '=', 'approved')]
        overdue = approved + [('next_review_date', '<', ctx['today'])]
        return {
            'available': True,
            'approved': self._count(model, approved),
            'review_overdue': self._count(model, overdue),
            'drill_approved': _drill(model, approved, _('Батлагдсан бодлого')),
            'drill_review_overdue': _drill(model, overdue, _('Хугацаа хэтэрсэн бодлогын хянах')),
        }

    @api.model
    def _section_treatment(self, ctx):
        model = 'project.task'
        # Хариу арга хэмжээний даалгавар нь эрсдэлд холбогдсон тул эрсдэл уншиж чадах хэрэглэгчид л
        # харагдана (project.task нь employees-д нээлттэй төсөл тул тусад нь хамгаална).
        if not (self._can_read(model) and self._can_read('isms.risk')):
            return self._unavailable(model)
        base = [('isms_risk_id', '!=', False)]
        open_domain = base + [('is_closed', '=', False)]
        overdue = open_domain + [('date_deadline', '<', ctx['today'])]
        return {
            'available': True,
            'total': self._count(model, base),
            'open': self._count(model, open_domain),
            'overdue': self._count(model, overdue),
            'drill_open': _drill(model, open_domain, _('Нээлттэй хариу арга хэмжээ')),
            'drill_overdue': _drill(model, overdue, _('Хугацаа хэтэрсэн даалгавар')),
        }

    @api.model
    def _section_audit(self):
        model = 'isms.audit.log'
        if not self._can_read(model):
            return self._unavailable(model)
        Log = self.env[model]
        labels = dict(self._selection_labels(model, 'action'))
        items = []
        for rec in Log.search([], limit=10):
            items.append({
                'id': rec.id,
                'timestamp': fields.Datetime.to_string(rec.timestamp),
                'action': rec.action,
                'action_label': labels.get(rec.action, rec.action),
                'model': rec.model or '',
                'model_name': rec.model_name or '',
            })
        return {
            'available': True,
            'total': self._count(model, []),
            'recent': items,
            'drill': _drill(model, [], _('Аудит лог')),
        }

    # ------------------------------------------------------------------ KPI cards
    @api.model
    def _build_kpis(self, sections):
        def kpi(key, section, label, value_fn, drill_fn, tone='neutral', extra=None):
            data = sections.get(section) or {}
            available = bool(data.get('available'))
            card = {
                'key': key,
                'section': section,
                'label': label,
                'tone': tone if tone in TONES else 'neutral',
                'available': available,
                'value': value_fn(data) if available else None,
                'drill': drill_fn(data) if available else None,
            }
            if extra:
                card.update(extra(data) if available else {})
            return card

        return [
            kpi('assets_total', 'assets', _('Хөрөнгө'),
                lambda d: d['total'], lambda d: d['drill_total']),
            kpi('assets_high_risk', 'assets', _('Өндөр эрсдэлтэй хөрөнгө'),
                lambda d: d['high_risk'], lambda d: d['drill_high_risk'], 'danger'),
            kpi('risks_total', 'risks', _('Эрсдэл'),
                lambda d: d['total'], lambda d: d['drill_total']),
            kpi('risks_high', 'risks', _('Өндөр түвшний эрсдэл'),
                lambda d: d['high'], lambda d: d['drill_high'], 'danger'),
            kpi('risks_open', 'risks', _('Нээлттэй эрсдэл'),
                lambda d: d['open'], lambda d: d['drill_open'], 'warning'),
            kpi('risks_accepted', 'risks', _('Батлагдсан хүлээн зөвшөөрөлт'),
                lambda d: d['accepted'], lambda d: d['drill_accepted'], 'success'),
            kpi('controls_selected', 'controls', _('Сонгосон хяналт'),
                lambda d: d['selected'], lambda d: d['drill_selected'],
                extra=lambda d: {'of': d['catalog']}),
            kpi('controls_implemented', 'controls', _('Хэрэгжсэн хяналт'),
                lambda d: self._implemented_count(d), lambda d: self._implemented_drill(d), 'success'),
            kpi('incidents_open', 'incidents', _('Нээлттэй инцидент'),
                lambda d: d['open'], lambda d: d['drill_open'], 'warning'),
            kpi('incidents_sla_overdue', 'incidents', _('SLA хугацаа хэтэрсэн'),
                lambda d: d['sla_overdue'], lambda d: d['drill_overdue'], 'danger'),
            kpi('policies_approved', 'policies', _('Батлагдсан бодлого'),
                lambda d: d['approved'], lambda d: d['drill_approved']),
            kpi('policies_review_overdue', 'policies', _('Дахин хянах хугацаа хэтэрсэн'),
                lambda d: d['review_overdue'], lambda d: d['drill_review_overdue'], 'warning'),
            kpi('treatment_open', 'treatment', _('Нээлттэй хариу арга хэмжээ'),
                lambda d: d['open'], lambda d: d['drill_open']),
            kpi('treatment_overdue', 'treatment', _('Хугацаа хэтэрсэн даалгавар'),
                lambda d: d['overdue'], lambda d: d['drill_overdue'], 'danger'),
        ]

    @api.model
    def _implemented_count(self, controls):
        return sum(row['count'] for row in controls['by_implementation'] if row['key'] == 'yes')

    @api.model
    def _implemented_drill(self, controls):
        for row in controls['by_implementation']:
            if row['key'] == 'yes':
                return row['drill']
        return None
