{
    'name': 'University ISMS: нотлох баримт, бодлогын баталгаажуулалт, аудитын экспорт',
    'version': '18.0.1.0.0',
    'category': 'Services/ISMS',
    'summary': 'ISMS-01 Evidence Vault, ISMS-06 бодлогын баталгаажуулалт, ISMS-08 аудитад бэлэн экспорт',
    'description': """
University ISMS: continuous assurance (Phase 4)
==============================================
* Нотлох баримтын сан (ISMS-01): хяналттай холбоо, эзэмшигч, хувилбарын гинж, SHA-256 нийлбэр
  (серверт тооцно), хянагч ба батлалтын төлөв, хугацаа. Батлагдсан нотолгоо өөрчлөгдөхгүй.
* Бодлогын баталгаажуулалт (ISMS-06): кампанит ажил, хамрах хүрээ, хүчинтэй хугацаа, хувилбар,
  ажилтан бүр өөрөө баталгаажуулна, шинэ хувилбараар хуучирна, хугацаа дуусна.
* Аудитын экспорт (ISMS-08): хяналт × нотолгоо индекс (CSV), батлагдсан файлууд, дутуу хяналтын
  жагсаалт, манифест. Хэрэглэгчийн өөрийн эрхээр өгөгдөл сонгоно.
""",
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['university_isms'],
    'data': [
        'security/evidence_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/evidence_views.xml',
        'views/attestation_views.xml',
        'views/export_views.xml',
        'views/menus.xml',
    ],
    'application': False,
    'installable': True,
}
