{
    'name': 'Formula Incident Console (ISMS)',
    'version': '18.0.1.0.0',
    'category': 'Services/ISMS',
    'summary': 'SOC-гийн маягийн инцидентийн консол: SLA, шилжилт, цагийн тэнхлэг, эрхийн шалгалт',
    'description': """
Formula Incident Console (ISMS, Phase 3 WF-01/02/04/07/08)
=========================================================

* Инцидентийн жагсаалт: ноцтой байдал, үе шат, SLA үлдсэн хугацаа, хугацаа хэтэрсэн тэмдэг,
  шинжээч, мэдээлэгч, нөлөөлсөн хөрөнгө, нотлох баримтын тоо.
* Дэлгэрэнгүй: цагийн тэнхлэг (chatter + аудит лог), шалгалтын тэмдэглэл, холбогдох Helpdesk
  тасалбар (зөвхөн унших эрхтэй бол), боломжтой үе шилжилтүүд ба шаардлагатай талбарууд.
* Бүх өгөгдөл хэрэглэгчийн ORM эрхээр (ACL + record rule) шүүгдэнэ; sudo() ашиглахгүй.
* Шилжилтийг үндсэн моделийн action_* методууд гүйцэтгэнэ; сервер бүрт дахин шалгана.
""",
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['web', 'university_isms'],
    'data': [
        'views/incident_console_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'formula_incident_console/static/src/incident_console/incident_console.scss',
            'formula_incident_console/static/src/incident_console/incident_console.js',
            'formula_incident_console/static/src/incident_console/incident_console.xml',
        ],
    },
    'application': False,
    'installable': True,
}
