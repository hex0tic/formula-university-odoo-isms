"""INT-02 Moodle LMS adapter.

Өгөгдлийн эзэмшил (data ownership):
* ERP = хичээлийн бүртгэл, элсэлт (enrolment), эцсийн дүн (campus.enrollment.score)-ийн эх сурвалж.
* Moodle руу: хичээлийн бүлэг (course), хэрэглэгч (user), элсэлт (manual enrol) ERP-ээс л явна.
* Moodle-ээс: зөвхөн үйл ажиллагааны дүнг САНАЛ болгон авна. Энэ нь campus.grade.change ноорог
  болно. Moodle дүн бичихгүй, enrolment-ийг устгахгүй/өөрчлөхгүй.
* Давхардал: formula.integration.mapping (дотоод ↔ гадаад ID) + outbox idempotency түлхүүр.
* Зөрчил: ERP давуу эрхтэй. Mapping зөрчилтэй бол дарж бичихгүй, алдаа/алгасалт гэж бүртгэнэ.

Moodle Web Services функцүүд (нэрийг Moodle баримтаас авсан; live дээр NOT VERIFIED):
  core_course_create_courses, core_user_create_users, enrol_manual_enrol_users,
  gradereport_user_get_grade_items (унших).
"""
import json
import logging

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

WS_COURSE_CREATE = 'core_course_create_courses'
WS_USER_CREATE = 'core_user_create_users'
WS_ENROL_MANUAL = 'enrol_manual_enrol_users'
WS_GRADE_ITEMS = 'gradereport_user_get_grade_items'
STUDENT_ROLE_ID = 5  # Moodle-ийн стандарт student role; site-д тохируулахдаа шалгана
GRADE_MIN, GRADE_MAX = 0.0, 100.0


class FormulaMoodleAdapter(models.AbstractModel):
    _name = 'formula.moodle.adapter'
    _description = 'Moodle LMS adapter (Web Services)'

    # ------------------------------------------------------------ ERP → Moodle
    @api.model
    def enqueue_offering_sync(self, endpoint, offering):
        """Хичээлийн бүлгийг Moodle course болгон илгээх. Аль хэдийн холбогдсон бол алгасна."""
        if not endpoint.enabled or endpoint.kind != 'lms':
            return self.env['formula.integration.event'].browse()
        mapped = self.env['formula.integration.mapping'].remote_for(endpoint, 'campus.offering', offering.id)
        if mapped:
            return self.env['formula.integration.event'].browse()
        short = ('%s-%s' % (offering.course_id.code, offering.semester or ''))[:100]
        payload = {
            'wsfunction': WS_COURSE_CREATE,
            'params': {'courses': [{
                'fullname': (offering.name or short)[:254],
                'shortname': short,
                'categoryid': 1,
                'idnumber': 'ERP-OFF-%s' % offering.id,
            }]},
            'erp_refs': [{'model': 'campus.offering', 'id': offering.id}],
        }
        return self.env['formula.integration.event'].enqueue(
            endpoint, 'lms.course.create', payload, 'lms:course:%s' % offering.id)

    @api.model
    def enqueue_student_sync(self, endpoint, student):
        """Оюутныг Moodle хэрэглэгч болгон илгээх. Нууц үг илгээхгүй (auth=nologin; SSO-р нэвтэрнэ)."""
        if not endpoint.enabled or endpoint.kind != 'lms':
            return self.env['formula.integration.event'].browse()
        if self.env['formula.integration.mapping'].remote_for(endpoint, 'campus.student', student.id):
            return self.env['formula.integration.event'].browse()
        parts = (student.name or '').split(None, 1)
        payload = {
            'wsfunction': WS_USER_CREATE,
            'params': {'users': [{
                'username': (student.student_code or '').lower()[:100],
                'firstname': (parts[0] if parts else student.student_code or '')[:100],
                'lastname': (parts[1] if len(parts) > 1 else '-')[:100],
                'email': student.institutional_email or '',
                'auth': 'nologin',
            }]},
            'erp_refs': [{'model': 'campus.student', 'id': student.id}],
        }
        return self.env['formula.integration.event'].enqueue(
            endpoint, 'lms.user.create', payload, 'lms:user:%s' % student.id)

    @api.model
    def enqueue_enrolment_sync(self, endpoint, enrollment):
        """ERP элсэлтийг Moodle manual enrolment болгон илгээнэ. Холбоос дутуу бол алгасна (ERP дараа дахин оролдоно)."""
        if not endpoint.enabled or endpoint.kind != 'lms':
            return self.env['formula.integration.event'].browse()
        mapping = self.env['formula.integration.mapping']
        remote_user = mapping.remote_for(endpoint, 'campus.student', enrollment.student_id.id)
        remote_course = mapping.remote_for(endpoint, 'campus.offering', enrollment.offering_id.id)
        if not remote_user or not remote_course:
            return self.env['formula.integration.event'].browse()
        payload = {
            'wsfunction': WS_ENROL_MANUAL,
            'params': {'enrolments': [{
                'roleid': STUDENT_ROLE_ID,
                'userid': int(remote_user),
                'courseid': int(remote_course),
            }]},
        }
        return self.env['formula.integration.event'].enqueue(
            endpoint, 'lms.enrol.create', payload, 'lms:enrol:%s' % enrollment.id)

    @api.model
    def after_delivery(self, endpoint, event, body_text):
        """Moodle create-ийн хариуг ERP холбоос болгон бүртгэнэ. Хариу дарааллаар таарна."""
        payload = json.loads(event.payload_json or '{}')
        refs = payload.get('erp_refs') or []
        if not refs:
            return
        data = json.loads(body_text or '[]')
        if not isinstance(data, list) or len(data) != len(refs):
            raise UserError(_('LMS хариу хүлээгдсэнтэй таарахгүй байна.'))
        for ref, item in zip(refs, data):
            remote = item.get('id') if isinstance(item, dict) else None
            if remote is None:
                continue
            self.env['formula.integration.mapping'].link(endpoint, ref['model'], ref['id'], remote, 'lms')

    # ------------------------------------------------------------ Moodle → ERP (зөвлөмж)
    @api.model
    def import_grade_suggestions(self, endpoint, items):
        """Moodle үйл ажиллагааны дүнг САНАЛ болгон campus.grade.change ноорог үүсгэнэ.

        Дүн (campus.enrollment.score) хэзээ ч бичигдэхгүй. Нэг санал давхардахгүй (mapping-ээр).
        Буцаах утга: {'created': [change_id...], 'skipped': [{'index', 'reason'}...]}.
        """
        user = self.env.user
        if not self.env.su and not (user.has_group('campus_university.group_campus_registrar') or
                                    user.has_group('campus_university.group_campus_lecturer')):
            raise AccessError(_('Дүнгийн санал импортлох эрх байхгүй.'))
        if endpoint.kind != 'lms' or not endpoint.enabled:
            raise UserError(_('LMS интеграц идэвхгүй байна.'))
        mapping = self.env['formula.integration.mapping']
        Change = self.env['campus.grade.change']
        summary = {'created': [], 'skipped': []}
        for index, item in enumerate(items or []):
            try:
                remote_user = str(item['remote_user_id'])
                remote_course = str(item['remote_course_id'])
                remote_item = str(item['remote_item_id'])
                score = float(item['grade'])
            except (KeyError, TypeError, ValueError):
                summary['skipped'].append({'index': index, 'reason': 'invalid'})
                continue
            if not GRADE_MIN <= score <= GRADE_MAX:
                summary['skipped'].append({'index': index, 'reason': 'out_of_range'})
                continue
            dedupe_key = 'grade:%s:%s:%s:%s' % (remote_user, remote_course, remote_item, score)
            if mapping.lookup(endpoint, 'campus.grade.change', dedupe_key):
                summary['skipped'].append({'index': index, 'reason': 'duplicate'})
                continue
            student = mapping.lookup(endpoint, 'campus.student', remote_user)
            offering = mapping.lookup(endpoint, 'campus.offering', remote_course)
            if not student or not offering:
                summary['skipped'].append({'index': index, 'reason': 'unmapped'})
                continue
            enrollment = self.env['campus.enrollment'].search([
                ('student_id', '=', student.local_id), ('offering_id', '=', offering.local_id)], limit=1)
            if not enrollment:
                summary['skipped'].append({'index': index, 'reason': 'no_enrollment'})
                continue
            try:
                with self.env.cr.savepoint():
                    change = Change.create({
                        'enrollment_id': enrollment.id,
                        'proposed_score': score,
                        'reason': 'Moodle үйл ажиллагааны дүнгийн санал (%s). ERP дээр шалгаж батална.' % remote_item,
                        'evidence_ref': 'moodle:item:%s' % remote_item,
                    })
                    mapping.link(endpoint, 'campus.grade.change', change.id, dedupe_key, 'grade_suggestion')
                summary['created'].append(change.id)
            except (AccessError, UserError, ValidationError) as exc:
                summary['skipped'].append({'index': index, 'reason': 'rejected: %s' % exc.__class__.__name__})
        return summary
