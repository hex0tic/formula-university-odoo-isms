{
    'name': 'Formula Integration Hub (SSO, LMS, мэдэгдэл, SIEM, API)',
    'version': '18.0.1.0.0',
    'category': 'Services/Integration',
    'summary': 'Гадаад системийн интеграцийн хязгаар: SSO, Moodle, имэйл, SIEM, API (feature flag-тай, анхдагчаар унтраалттай)',
    'description': """
Formula Integration Hub
=======================

* Интеграцийн endpoint тохиргоо, нууцын лавлагаа (утга биш), feature flag (анхдагчаар унтраалттай)
* Гаралтын дараалал (outbox): idempotency түлхүүр, exponential backoff, dead-letter, cron dispatcher
* INT-01 SSO: OIDC тохиргоо, IdP бүлгийн дүрмийн allowlist (админ эрх автоматаар олгохгүй), login үеийн provisioning
* INT-02 Moodle: Web Service функцүүд, ERP нь эрсдэл/дүнгийн эх сурвалж; LMS дүн зөвхөн campus.grade.change ноорог
* INT-03 Мэдэгдэл: хэрэглэгчийн тохиргоо, mail template, mail queue, event log
* INT-04 SIEM: нэвтрэлт, инцидент, эрхийн өөрчлөлтийн privacy-aware үйл явдал (HMAC, түүхий IP/нэр байхгүй)
* INT-05 API: /api/formula/v1 Bearer API key, per-key rate limit, record rule-ээр хязгаарлагдана
""",
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'AGPL-3',
    'depends': ['base', 'mail', 'campus_university', 'university_isms'],
    'data': [
        'security/integration_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'data/mail_template_data.xml',
        'views/endpoint_views.xml',
        'views/event_views.xml',
        'views/mapping_notify_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
