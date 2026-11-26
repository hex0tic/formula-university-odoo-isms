"""ISO/IEC 27001:2022 Annex A Control Explorer (WF-05).

Зарчим:
* Каталог, дэлгэрэнгүй, холбоос бүр хэрэглэгчийн ORM эрхээр уншина. ``sudo()`` ашиглахгүй.
* Холбоосын жагсаалт (эрсдэл, хөрөнгө, бодлого, инцидент) зөвхөн хэрэглэгч уншиж чадах бичлэгийг
  агуулна. Уншиж чадахгүй бичлэгийг алгасна, тоонд ч оруулахгүй.
* Уншиж чадахгүй талбар (тайлбар, нотолгоо, эрсдэл/хөрөнгийн холбоос) нь ``readable: False``
  гэж тэмдэглэгдэнэ; утгыг нь буцаахгүй.
* Дүгнэлтийн шалгалтууд нь компьютерээр тооцсон шалгалт. Аудитын дүгнэлт биш.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.university_isms.models.control import THEMES

MAX_LIMIT = 200
MAX_SEARCH_LEN = 100
THEME_KEYS = tuple(key for key, _label in THEMES)
THEME_LABELS = dict(THEMES)
IMPLEMENTATION_KEYS = ('yes', 'partial', 'no')
TRI_STATE = ('all', 'yes', 'no')
DISCLAIMER = ('Энэ шалгалтууд нь системийн өгөгдөл дээр тооцсон автомат шалгалт бөгөөд '
              'аудитын дүгнэлт биш.')

# Холбоосын бичлэгийн талбарууд (харагдах хэлбэр). Модел бүрт нэг л тодорхойлолт.
REF_FIELDS = {
    'isms.risk': ('code', 'name', 'level', 'state'),
    'isms.asset': ('code', 'name'),
    'isms.policy': ('code', 'name', 'state', 'next_review_date'),
    'isms.incident': ('code', 'name', 'state', 'severity'),
}


class FormulaControlExplorer(models.AbstractModel):
    _name = 'formula.control.explorer'
    _description = 'ISO Control Explorer: каталог, SoA дэлгэрэнгүй, холбоос, тооцсон шалгалт'

    # ================================================================== public API
    @api.model
    def get_catalog(self, filters=None):
        """Annex A каталог: шүүсэн жагсаалт, нийлбэр, шүүлтүүрийн сонголт."""
        Control = self.env['isms.control']
        if not Control.has_access('read'):
            return self._unavailable(_('Хяналтын каталогийг харах эрх байхгүй.'))
        f = self._sanitize_filters(filters)
        domain = self._build_domain(f)
        labels = self._labels('isms.control', 'implementation')
        records = Control.search(domain, limit=f['limit'], order='sequence, id')
        return {
            'available': True,
            'filters': f,
            'items': [self._catalog_item(rec, labels) for rec in records],
            'total': Control.search_count(domain),
            'summary': self._summary(f),
            'options': self._options(),
        }

    @api.model
    def get_control_detail(self, control_id):
        """Нэг хяналтын SoA талбарууд, холбоосууд, нотолгоо, тооцсон шалгалтууд."""
        Control = self.env['isms.control']
        if not Control.has_access('read'):
            return self._unavailable(_('Хяналтыг харах эрх байхгүй.'))
        try:
            control_id = int(control_id)
        except (TypeError, ValueError):
            return {'available': False, 'not_found': True, 'reason': _('Хяналт олдсонгүй.')}
        control = Control.browse(control_id).exists()
        if not control:
            return {'available': False, 'not_found': True, 'reason': _('Хяналт олдсонгүй.')}
        try:
            control.check_access('read')
        except AccessError:
            return {'available': False, 'reason': _('Энэ хяналтыг харах эрх байхгүй.')}

        impl_labels = self._labels('isms.control', 'implementation')
        risks, risk_has_link = self._forward_links(control, 'risk_ids', 'isms.risk',
                                                   _('Холбогдох эрсдэл'))
        assets, _asset_raw = self._forward_links(control, 'asset_ids', 'isms.asset',
                                                 _('Холбогдох хөрөнгө'))
        policies, _policy_raw = self._reverse_links(control, 'isms.policy', 'control_ids',
                                                    'policies', _('Холбогдох бодлого'))
        incidents, _incident_raw = self._reverse_links(control, 'isms.incident', 'control_ids',
                                                       'incidents', _('Холбогдох инцидент'))
        links = {'risks': risks, 'assets': assets, 'policies': policies, 'incidents': incidents}
        findings = self._findings(control, risks, risk_has_link, policies, impl_labels)
        return {
            'available': True,
            'control': self._catalog_item(control, impl_labels),
            'justification': self._text_field(control, 'justification'),
            'odoo_implementation': self._text_field(control, 'odoo_implementation'),
            'evidence': self._text_field(control, 'evidence'),
            'links': links,
            'next_review': self._next_review(policies),
            'findings': findings,
            'findings_summary': self._findings_summary(findings),
            'disclaimer': DISCLAIMER,
        }

    # ================================================================== filters
    @api.model
    def _sanitize_filters(self, filters):
        f = filters if isinstance(filters, dict) else {}
        theme = f.get('theme') or ''
        if theme not in THEME_KEYS:
            theme = ''
        selected = f.get('selected') or 'all'
        applicable = f.get('applicable') or 'all'
        implementation = f.get('implementation') or 'all'
        try:
            owner_id = int(f.get('owner_id') or 0)
        except (TypeError, ValueError):
            owner_id = 0
        try:
            limit = int(f.get('limit') or MAX_LIMIT)
        except (TypeError, ValueError):
            limit = MAX_LIMIT
        return {
            'theme': theme,
            'selected': selected if selected in TRI_STATE else 'all',
            'applicable': applicable if applicable in TRI_STATE else 'all',
            'implementation': implementation if implementation in ('all',) + IMPLEMENTATION_KEYS
            else 'all',
            'new_2022': bool(f.get('new_2022')),
            'owner_id': owner_id if owner_id > 0 else 0,
            'search': str(f.get('search') or '').strip()[:MAX_SEARCH_LEN],
            'limit': min(max(limit, 1), MAX_LIMIT),
        }

    @api.model
    def _build_domain(self, f, skip_theme=False):
        """Шүүлтүүрээс домайн бүтээнэ. Бүх утга сервер талд whitelist-ээр шалгагдсан."""
        domain = []
        if f['theme'] and not skip_theme:
            domain.append(('theme', '=', f['theme']))
        if f['selected'] != 'all':
            domain.append(('selected', '=', f['selected'] == 'yes'))
        if f['applicable'] != 'all':
            domain.append(('applicable', '=', f['applicable'] == 'yes'))
        if f['implementation'] != 'all':
            domain.append(('implementation', '=', f['implementation']))
        if f['new_2022']:
            domain.append(('is_new_2022', '=', True))
        if f['owner_id']:
            domain.append(('responsible_id', '=', f['owner_id']))
        if f['search']:
            term = f['search']
            domain += ['|', '|', ('code', 'ilike', term), ('name', 'ilike', term),
                       ('name_mn', 'ilike', term)]
        return domain

    @api.model
    def _summary(self, f):
        Control = self.env['isms.control']
        domain = self._build_domain(f)
        theme_domain = self._build_domain(f, skip_theme=True)
        theme_rows = dict(Control._read_group(theme_domain, groupby=['theme'],
                                              aggregates=['__count']))
        impl_rows = dict(Control._read_group(domain, groupby=['implementation'],
                                             aggregates=['__count']))
        impl_labels = self._labels('isms.control', 'implementation')
        return {
            'catalog': Control.search_count([]),
            'matching': Control.search_count(domain),
            'selected': Control.search_count(domain + [('selected', '=', True)]),
            'applicable': Control.search_count(domain + [('applicable', '=', True)]),
            'theme_all': Control.search_count(theme_domain),
            'by_theme': [{'key': key, 'label': label, 'count': theme_rows.get(key, 0)}
                         for key, label in THEMES],
            'by_implementation': [{'key': key, 'label': impl_labels.get(key, key),
                                   'count': impl_rows.get(key, 0)}
                                  for key in IMPLEMENTATION_KEYS],
        }

    @api.model
    def _options(self):
        Control = self.env['isms.control']
        owners = []
        rows = Control._read_group([('responsible_id', '!=', False)], groupby=['responsible_id'],
                                   aggregates=['__count'])
        for user, _count in rows:
            owners.append({'id': user.id, 'name': user.name or ''})
        owners.sort(key=lambda o: o['name'].lower())
        return {
            'owners': owners,
            'themes': [{'key': key, 'label': label} for key, label in THEMES],
        }

    # ================================================================== catalog item
    @api.model
    def _catalog_item(self, rec, impl_labels):
        impl = rec.implementation or 'no'
        return {
            'id': rec.id,
            'code': rec.code or '',
            'name': rec.name or '',
            'name_mn': rec.name_mn or '',
            'theme': rec.theme or '',
            'theme_label': THEME_LABELS.get(rec.theme, rec.theme or ''),
            'is_new_2022': bool(rec.is_new_2022),
            'selected': bool(rec.selected),
            'applicable': bool(rec.applicable),
            'implementation': impl,
            'implementation_label': impl_labels.get(impl, impl),
            'owner': self._user_ref(rec.responsible_id),
            'gap_implementation': bool(rec.selected and impl != 'yes'),
        }

    @api.model
    def _user_ref(self, user):
        return {'id': user.id, 'name': user.name or ''} if user else None

    # ================================================================== links
    @api.model
    def _refs(self, records):
        """Холбоосын бичлэгийн хураангуй (талбар бүр уншигдах эрхтэй бичлэгээс)."""
        if not records:
            return []
        model = records._name
        spec = REF_FIELDS[model]
        labels = {}
        for fname in spec:
            if records._fields[fname].type == 'selection':
                labels[fname] = self._labels(model, fname)
        today = fields.Date.context_today(self)
        refs = []
        for rec in records:
            item = {'id': rec.id, 'model': model}
            for fname in spec:
                value = rec[fname]
                if fname in labels:
                    item[fname] = value or False
                    item[fname + '_label'] = labels[fname].get(value, value or '')
                elif fname == 'next_review_date':
                    item[fname] = fields.Date.to_string(value) if value else False
                else:
                    item[fname] = value or ''
            if model == 'isms.policy':
                item['review_overdue'] = bool(
                    rec.state == 'approved' and rec.next_review_date
                    and rec.next_review_date < today)
            refs.append(item)
        return refs

    @api.model
    def _section(self, key, label, model, records=None, reason=None, available=True):
        records = records if records is not None else self.env[model].browse()
        return {
            'key': key,
            'label': label,
            'model': model,
            'available': available,
            'reason': reason or False,
            'count': len(records),
            'ids': records.ids,
            'records': self._refs(records),
        }

    @api.model
    def _forward_links(self, control, fname, comodel_name, label):
        """Хяналтын Many2many (risk_ids, asset_ids). Талбарын groups + comodel ACL шалгана.

        Буцаах утга: (section, has_hidden_or_visible_link).
        Many2many уншихад ORM эрхийн дүрэм хэрэглэгдэх тул ``control[fname]`` нь зөвхөн уншиж
        чадах бичлэгүүдийг буцаана. «Ямар ч холбоос бий эсэх»-ийг ``sudo()``-оор зөвхөн boolean-ээр
        шалгана: ID эсвэл тоо API-д гарахгүй. Үр дүн нь уншиж чадахгүй холбоостой үед «эрсдэлгүй»
        гэж буруу дүгнэхээс сэргийлнэ (findings-д л ашиглагдана).
        """
        key = fname.replace('_ids', 's')
        comodel = self.env[comodel_name]
        if not control._fields[fname].is_accessible(self.env) or not comodel.has_access('read'):
            return self._section(key, label, comodel_name, available=False,
                                 reason=_('Энэ холбоосыг харах эрх таньд байхгүй.')), None
        has_any_link = bool(control.sudo()[fname])
        visible_ids = control[fname].ids
        records = comodel.with_context(active_test=False).search([('id', 'in', visible_ids)]) \
            if visible_ids else comodel.browse()
        return self._section(key, label, comodel_name, records), has_any_link

    @api.model
    def _reverse_links(self, control, comodel_name, fname, key, label):
        """Бодлого, инцидент: comodel-ийн Many2many-ээр урвуу хайна. Талбарын groups шалгана."""
        comodel = self.env[comodel_name]
        if not comodel._fields[fname].is_accessible(self.env) or not comodel.has_access('read'):
            return self._section(key, label, comodel_name, available=False,
                                 reason=_('Энэ холбоосыг харах эрх таньд байхгүй.')), None
        records = comodel.with_context(active_test=False).search([(fname, 'in', control.ids)])
        return self._section(key, label, comodel_name, records), None

    @api.model
    def _text_field(self, control, fname):
        if not control._fields[fname].is_accessible(self.env):
            return {'readable': False, 'value': None}
        return {'readable': True, 'value': control[fname] or ''}

    @api.model
    def _next_review(self, policies):
        """Хяналт дээр дахин хянах огноо байхгүй. Холбоотой бодлогын огноог уншиж чадах хэсгээр харуулна."""
        dates = sorted(ref['next_review_date'] for ref in policies['records']
                       if ref.get('next_review_date'))
        return {
            'control_field': False,
            'reason': _('Хяналтын бүртгэлд дахин хянах огноо байхгүй. Доорх огноо нь холбоотой '
                        'бодлогоос уншсан утга.'),
            'earliest': dates[0] if dates else False,
            'policy_dates_available': policies['available'],
        }

    # ================================================================== findings
    @api.model
    def _findings(self, control, risks, risk_has_link, policies, impl_labels):
        """Компьютерээр тооцсон шалгалтууд. status: gap | ok | na | not_evaluated."""
        out = []

        def add(key, label, status, severity, detail):
            out.append({'key': key, 'label': label, 'status': status,
                        'severity': severity, 'detail': detail})

        sel = bool(control.selected)
        app = bool(control.applicable)
        impl = control.implementation or 'no'
        impl_label = impl_labels.get(impl, impl)
        justification_ok = control._fields['justification'].is_accessible(self.env)
        evidence_ok = control._fields['evidence'].is_accessible(self.env)
        not_eval = _('Таны эрхээр энэ шалгалтыг бүрэн хийх боломжгүй.')

        # 1. Сонгосон хяналтын хэрэгжилт
        label = _('Сонгосон хяналт хэрэгжсэн эсэх')
        if not sel:
            add('selected_implementation', label, 'na', 'neutral',
                _('Controls Mapping-д сонгоогүй тул шалгахгүй.'))
        elif impl == 'yes':
            add('selected_implementation', label, 'ok', 'success',
                _('Сонгосон бөгөөд хэрэгжсэн гэж тэмдэглэсэн.'))
        else:
            add('selected_implementation', label, 'gap',
                'danger' if impl == 'no' else 'warning',
                _('Сонгосон боловч хэрэгжилт: %s.') % impl_label)

        # 2. Сонгосон хяналтын тайлбар
        label = _('Сонгосон хяналтын тайлбар')
        if not sel:
            add('selected_justification', label, 'na', 'neutral',
                _('Controls Mapping-д сонгоогүй тул шалгахгүй.'))
        elif not justification_ok:
            add('selected_justification', label, 'not_evaluated', 'neutral', not_eval)
        elif (control.justification or '').strip():
            add('selected_justification', label, 'ok', 'success', _('Тайлбар бичигдсэн.'))
        else:
            add('selected_justification', label, 'gap', 'warning',
                _('Сонгосон боловч тайлбар / үндэслэл бичигдээгүй.'))

        # 3. Сонгосон хяналтын нотолгоо
        label = _('Сонгосон хяналтын нотолгоо')
        if not sel:
            add('selected_evidence', label, 'na', 'neutral',
                _('Controls Mapping-д сонгоогүй тул шалгахгүй.'))
        elif not evidence_ok:
            add('selected_evidence', label, 'not_evaluated', 'neutral', not_eval)
        elif (control.evidence or '').strip():
            add('selected_evidence', label, 'ok', 'success', _('Нотолгоо бичигдсэн.'))
        else:
            add('selected_evidence', label, 'gap', 'warning',
                _('Сонгосон боловч нотолгооны тайлбар бичигдээгүй.'))

        # 4. Сонгосон хяналтад холбоотой эрсдэл
        label = _('Сонгосон хяналтад холбоотой эрсдэл')
        readable_risks = risks['count'] if risks['available'] else None
        if not sel:
            add('selected_risk', label, 'na', 'neutral',
                _('Controls Mapping-д сонгоогүй тул шалгахгүй.'))
        elif not risks['available'] or risk_has_link is None:
            add('selected_risk', label, 'not_evaluated', 'neutral', not_eval)
        elif readable_risks:
            add('selected_risk', label, 'ok', 'success',
                _('Таны харж буй %s эрсдэл холбогдсон.') % readable_risks)
        elif risk_has_link:
            # Холбоос байгаа ч таны эрхээр харагдахгүй: «эрсдэлгүй» гэж дүгнэхгүй
            add('selected_risk', label, 'not_evaluated', 'neutral', not_eval)
        else:
            add('selected_risk', label, 'gap', 'warning', _('Холбогдох эрсдэл бүртгэгдээгүй.'))

        # 5. Хамааралтай / хамааралгүй тэмдэглэгээ
        label = _('Хамааралтай тэмдэглэгээний зөрчил')
        if not app and sel:
            add('applicability_consistent', label, 'gap', 'warning',
                _('Хамааралгүй гэж тэмдэглэсэн боловч Controls Mapping-д сонгосон байна.'))
        else:
            add('applicability_consistent', label, 'ok', 'success', _('Зөрчилгүй.'))

        # 6. Хамааралгүй гэсэн үндэслэл
        label = _('Хамааралгүй гэсэн үндэслэл')
        if app:
            add('not_applicable_justification', label, 'na', 'neutral',
                _('Хамааралтай хяналт тул шалгахгүй.'))
        elif not justification_ok:
            add('not_applicable_justification', label, 'not_evaluated', 'neutral', not_eval)
        elif (control.justification or '').strip():
            add('not_applicable_justification', label, 'ok', 'success',
                _('Үндэслэл бичигдсэн.'))
        else:
            add('not_applicable_justification', label, 'gap', 'warning',
                _('Хамааралгүй гэсэн боловч үндэслэл бичигдээгүй.'))

        # 7. Хэрэгжсэн боловч сонгоогүй
        label = _('Хэрэгжсэн боловч сонгоогүй')
        if impl == 'yes' and not sel:
            add('implemented_not_selected', label, 'gap', 'info',
                _('Хэрэгжсэн гэж тэмдэглэсэн боловч Controls Mapping-д сонгоогүй.'))
        else:
            add('implemented_not_selected', label, 'na', 'neutral',
                _('Хэрэгжилт «Тийм» биш эсвэл сонгосон тул шалгахгүй.'))

        # 8. Хариуцагч
        label = _('Хариуцагч оноогдсон эсэх')
        if control.responsible_id:
            add('owner', label, 'ok', 'success',
                _('Хариуцагч: %s') % (control.responsible_id.name or ''))
        else:
            add('owner', label, 'gap', 'warning', _('Хариуцагч оноогоогүй.'))

        # 9. Холбоотой бодлогын дахин хянах хугацаа (уншиж чадах бодлогоор)
        label = _('Холбоотой бодлогын дахин хянах хугацаа')
        overdue = [ref for ref in policies['records'] if ref.get('review_overdue')]
        dated = [ref for ref in policies['records'] if ref.get('next_review_date')]
        if overdue:
            add('policy_review', label, 'gap', 'warning',
                _('Дахин хянах хугацаа хэтэрсэн бодлого: %s.') % len(overdue))
        elif dated:
            add('policy_review', label, 'ok', 'success',
                _('Холбоотой бодлогын хянах хугацаа хэтрээгүй.'))
        else:
            add('policy_review', label, 'na', 'neutral',
                _('Таны харж буй холбоотой бодлогын хянах огноо байхгүй.'))

        return out

    @api.model
    def _findings_summary(self, findings):
        summary = {'gap': 0, 'ok': 0, 'na': 0, 'not_evaluated': 0}
        for item in findings:
            summary[item['status']] = summary.get(item['status'], 0) + 1
        return summary

    # ================================================================== helpers
    @api.model
    def _labels(self, model, fname):
        info = self.env[model].fields_get([fname], attributes=['selection'])
        return dict(info.get(fname, {}).get('selection', []))

    @api.model
    def _unavailable(self, reason):
        return {'available': False, 'reason': reason}
