"""ISMS-08 Аудитад бэлэн нотлох баримтын экспорт.

Экспортыг ХҮСЭГЧ хэрэглэгчийн эрхээр бүтээнэ (sudo ашиглахгүй): хэрэглэгч уншиж чадахгүй нотолгоо
багцад орохгүй, индекст гарахгүй. Багцын агуулга (ZIP):

* index.csv      хяналт × нотолгооны мөр: SoA (хамааралтай, хэрэгжилт, тайлбар), нотолгооны нэр, хувилбар,
                 төлөв, SHA-256, хүчинтэй дуусах огноо, хянагч, багцад орсон эсэх ба шалтгаан
* missing.csv   сонгосон хяналтаас батлагдсан, одоо хүчинтэй нотолгоогүй хяналтууд (шалтгааны кодтой)
* manifest.txt  үүсгэсэн огноо (UTC), үүсгэсэн хэрэглэгч, тоон дүн, файл бүрийн SHA-256, MISSING жагсаалт
* files/        батлагдсан, хүчинтэй, SHA-256 таарсан нотолгооны файлууд (тодорхой нэртэй)

Дүгнэлт гаргахгүй; зөвхөн бүртгэлийн баримтад тулгуурласан фактуудыг бичнэ.
"""
import base64
import csv
import hashlib
import io
import re
import zipfile

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

GROUP_AUDITOR = 'university_isms.group_isms_auditor'
GROUP_MANAGER = 'university_isms.group_isms_manager'

REASON_TEXT = {
    'NO_APPROVED_EVIDENCE': 'Батлагдсан, одоо хүчинтэй нотолгоо алга',
    'APPROVED_EXPIRED': 'Батлагдсан нотолгоо байгаа боловч хугацаа дууссан',
    'DIGEST_MISMATCH': 'Батлагдсан нотолгооны файлын SHA-256 таарахгүй байна',
}
INDEX_HEADER = [
    'control_code', 'control_name', 'soa_applicable', 'soa_implementation', 'soa_justification',
    'evidence_ref', 'evidence_name', 'evidence_version', 'evidence_state', 'evidence_sha256',
    'evidence_valid_until', 'evidence_reviewer', 'evidence_reviewed_at', 'evidence_superseded',
    'digest_check', 'package_status', 'package_file',
]


def _safe_ascii(name):
    return re.sub(r'[^A-Za-z0-9._-]', '_', name or 'evidence')[:120]


def _csv_bytes(header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\n')
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode('utf-8-sig')


def _text(value):
    return '' if value in (False, None) else str(value)


class IsmsEvidenceExport(models.Model):
    _name = 'isms.evidence.export'
    _description = 'Аудитын нотлох баримтын багц'
    _inherit = ['isms.audit.mixin']
    _order = 'id desc'
    _isms_audit_skip_fields = {'write_date', 'write_uid', 'create_date', 'create_uid',
                               'display_name', 'zip_file'}

    name = fields.Char('Багцын нэр', required=True, readonly=True)
    requested_by_id = fields.Many2one('res.users', 'Хүсэлт гаргагч', required=True, readonly=True,
                                      index=True, default=lambda self: self.env.user)
    generated_at = fields.Datetime('Үүсгэсэн огноо (UTC)', required=True, readonly=True,
                                   default=fields.Datetime.now)
    control_ids = fields.Many2many('isms.control', 'isms_evidence_export_control_rel', 'export_id',
                                   'control_id', string='Хамрсан хяналтууд', readonly=True)
    control_count = fields.Integer('Хяналтын тоо', readonly=True)
    covered_count = fields.Integer('Нотолгоотой хяналт', readonly=True)
    missing_count = fields.Integer('Дутуу хяналт', readonly=True)
    file_count = fields.Integer('Багцад орсон файл', readonly=True)
    is_complete = fields.Boolean('Бүрэн эсэх', readonly=True)
    completeness_text = fields.Char('Бүрэн байдал', compute='_compute_completeness_text')
    zip_file = fields.Binary('Багц (ZIP)', attachment=True, readonly=True)
    zip_filename = fields.Char('ZIP файлын нэр', readonly=True)
    zip_sha256 = fields.Char('ZIP SHA-256', readonly=True)

    @api.depends('is_complete', 'missing_count', 'control_count')
    def _compute_completeness_text(self):
        for rec in self:
            if rec.is_complete:
                rec.completeness_text = _('Бүрэн: %s хяналт бүгд нотолгоотой') % rec.control_count
            else:
                rec.completeness_text = _('Дутуу: %(missing)s / %(total)s хяналтад нотолгоо алга') % {
                    'missing': rec.missing_count, 'total': rec.control_count}

    @api.model_create_multi
    def create(self, vals_list):
        if not self._isms_is_internal():
            raise AccessError(_('Аудитын багцыг зөвхөн экспортын шидтэн үүсгэнэ.'))
        for vals in vals_list:
            if vals.get('zip_file'):
                vals['zip_sha256'] = hashlib.sha256(base64.b64decode(vals['zip_file'])).hexdigest()
        return super().create(vals_list)

    def write(self, vals):
        if not self._isms_is_internal():
            raise AccessError(_('Экспортын бүртгэлийг өөрчлөх боломжгүй (аудит).'))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise AccessError(_('Экспортын бүртгэлийг устгах боломжгүй (аудит).'))
        return super().unlink()


class IsmsEvidenceExportWizard(models.TransientModel):
    _name = 'isms.evidence.export.wizard'
    _description = 'Аудитын экспорт үүсгэх шидтэн'

    control_ids = fields.Many2many(
        'isms.control', 'isms_evidence_export_wizard_control_rel', 'wizard_id', 'control_id',
        string='Хяналтууд', required=True,
        default=lambda self: [(6, 0, self.env['isms.control'].search([('selected', '=', True)]).ids)],
        help='Үндсэн утга: Controls Mapping-д сонгосон хяналтууд.')

    def _isms_check_export_right(self):
        user = self.env.user
        if not (user.has_group(GROUP_AUDITOR) or user.has_group(GROUP_MANAGER)):
            raise AccessError(_('Аудитын экспортыг зөвхөн дотоод аудитор эсвэл МАБ менежер (CISO) гаргана.'))

    def _isms_facts(self, evidence, today):
        """Нотолгооны статус. Батлагдсан бол файлыг дахин хэшлэнэ (хэрэглэгчийн эрхээр уншина)."""
        facts = {
            'ev': evidence,
            'approved': evidence.state == 'approved',
            'superseded': bool(evidence.is_superseded),
            'expired': bool(evidence.valid_until and evidence.valid_until < today),
            'check': 'not_checked',
            'raw': None,
        }
        if facts['approved']:
            raw, actual = evidence._isms_read_digest()
            if raw is None:
                facts['check'] = 'missing'
            else:
                facts['raw'] = raw
                facts['check'] = 'match' if actual == evidence.sha256 else 'mismatch'
        if not facts['approved']:
            status = 'NOT_APPROVED'
        elif facts['superseded']:
            status = 'SUPERSEDED'
        elif facts['expired']:
            status = 'EXPIRED'
        elif facts['check'] == 'missing':
            status = 'NO_FILE'
        elif facts['check'] == 'mismatch':
            status = 'DIGEST_MISMATCH'
        else:
            status = 'INCLUDED'
        facts['status'] = status
        facts['current'] = status == 'INCLUDED'
        return facts

    def _isms_build_package(self, controls):
        """Хэрэглэгчийн эрхээр багцын агуулгыг бүтээнэ. (zip bytes, тоон дүн, манифест мөрүүд) буцаана."""
        env = self.env
        today = fields.Date.context_today(self)
        evidences = env['isms.evidence'].search([('control_ids', 'in', controls.ids)], order='id')
        facts_by_id = {ev.id: self._isms_facts(ev, today) for ev in evidences}

        index_rows, missing_rows, files = [], [], {}
        covered = 0
        for control in controls:
            control_evs = evidences.filtered(lambda e: control in e.control_ids)
            current = [facts_by_id[ev.id] for ev in control_evs if facts_by_id[ev.id]['current']]
            if not control_evs:
                index_rows.append(self._isms_index_row(control, None, None))
            for ev in control_evs.sorted('id'):
                facts = facts_by_id[ev.id]
                package_file = ''
                if facts['current'] and ev.id not in files:
                    package_file = 'files/EV-%05d-v%d-%s-%s' % (
                        ev.id, ev.version, ev.sha256[:12], _safe_ascii(ev.file_name))
                    files[ev.id] = (package_file, facts['raw'])
                elif facts['current']:
                    package_file = files[ev.id][0]
                index_rows.append(self._isms_index_row(control, facts, package_file))
            if current:
                covered += 1
            else:
                approved_facts = [f for f in (facts_by_id[ev.id] for ev in control_evs)
                                  if f['approved'] and not f['superseded']]
                if any(f['check'] == 'mismatch' for f in approved_facts):
                    code = 'DIGEST_MISMATCH'
                elif any(f['expired'] for f in approved_facts):
                    code = 'APPROVED_EXPIRED'
                else:
                    code = 'NO_APPROVED_EVIDENCE'
                missing_rows.append([control.code, control.name, code, REASON_TEXT[code]])

        now = fields.Datetime.now()
        user = env.user
        index_bytes = _csv_bytes(INDEX_HEADER, index_rows)
        missing_bytes = _csv_bytes(['control_code', 'control_name', 'reason_code', 'reason_text'], missing_rows)
        manifest = self._isms_manifest(controls, covered, missing_rows, files, now, user)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('index.csv', index_bytes)
            zf.writestr('missing.csv', missing_bytes)
            zf.writestr('manifest.txt', manifest.encode('utf-8'))
            for ev_id in sorted(files):
                path, raw = files[ev_id]
                zf.writestr(path, raw)
        counts = {
            'control_count': len(controls),
            'covered_count': covered,
            'missing_count': len(missing_rows),
            'file_count': len(files),
            'is_complete': not missing_rows,
        }
        return buf.getvalue(), counts, now

    def _isms_index_row(self, control, facts, package_file):
        if facts is None:
            return [control.code, control.name, control.applicable, control.implementation,
                    _text(control.justification), '', '', '', '', '', '', '', '', '', '',
                    'NO_EVIDENCE_RECORD', '']
        ev = facts['ev']
        return [
            control.code, control.name, control.applicable, control.implementation,
            _text(control.justification),
            'EV-%05d' % ev.id, _text(ev.name), ev.version, ev.state, _text(ev.sha256),
            _text(ev.valid_until), _text(ev.reviewer_id.name), _text(ev.reviewed_at),
            'true' if facts['superseded'] else 'false',
            facts['check'], facts['status'], package_file,
        ]

    def _isms_manifest(self, controls, covered, missing_rows, files, now, user):
        lines = [
            'ISMS аудитын нотлох баримтын багц',
            'Үүсгэсэн огноо (UTC): %s' % fields.Datetime.to_string(now),
            'Үүсгэсэн хэрэглэгч: %s (%s)' % (user.login, user.name),
            'Сонгосон хяналтын тоо: %d' % len(controls),
            'Батлагдсан, хүчинтэй, SHA-256 таарсан нотолгоотой хяналт: %d' % covered,
            'Дутуу хяналт (MISSING): %d' % len(missing_rows),
            'Багцад орсон файлын тоо: %d' % len(files),
            '',
            'Файлын жагсаалт (path | бүртгэлийн SHA-256 | сэргээн тооцсон SHA-256):',
        ]
        for ev_id in sorted(files):
            path, raw = files[ev_id]
            stored = self.env['isms.evidence'].browse(ev_id).sha256
            lines.append('%s | %s | %s' % (path, stored, hashlib.sha256(raw).hexdigest()))
        if not files:
            lines.append('(файл алга)')
        lines += ['', 'MISSING:']
        for code, name, reason_code, _text_mn in missing_rows:
            lines.append('%s | %s | %s' % (code, name, reason_code))
        if not missing_rows:
            lines.append('(байхгүй)')
        lines += [
            '',
            'Энэ багц нь бүртгэлийн өгөгдлийн хуулбар юм. Аудитын дүгнэлт, нийцлийн баталгаа агуулаагүй.',
        ]
        return '\n'.join(lines) + '\n'

    def action_generate(self):
        self.ensure_one()
        self._isms_check_export_right()
        if not self.control_ids:
            raise UserError(_('Хамрах хяналтыг хамгийн багадаа нэгээр сонгоно уу.'))
        zip_bytes, counts, now = self._isms_build_package(self.control_ids)
        export = self.env['isms.evidence.export']._isms_internal().create({
            'name': _('ISMS экспорт %s') % now.strftime('%Y%m%d-%H%M%S'),
            'generated_at': now,
            'control_ids': [(6, 0, self.control_ids.ids)],
            'control_count': counts['control_count'],
            'covered_count': counts['covered_count'],
            'missing_count': counts['missing_count'],
            'file_count': counts['file_count'],
            'is_complete': counts['is_complete'],
            'zip_file': base64.b64encode(zip_bytes).decode(),
            'zip_filename': 'isms-evidence-export-%s.zip' % now.strftime('%Y%m%d-%H%M%S'),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'isms.evidence.export',
            'res_id': export.id,
            'view_mode': 'form',
            'target': 'current',
        }
