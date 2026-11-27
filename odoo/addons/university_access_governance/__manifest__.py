{
    'name': 'University Access Governance (хандалтын засаглал)',
    'version': '18.0.1.1.0',
    'category': 'Services/ISMS',
    'summary': 'Эрхийн дахин баталгаажуулалт, түр ба давуу эрхийн хүсэлт, эрхийн тайлан '
               '(GOV-01, GOV-03, GOV-04, GOV-05)',
    'description': """
Хандалтын засаглал
==================
* Эрхийн дахин баталгаажуулалтын кампанит ажил (30/90 хоног эсвэл тохируулсан давтамж),
  хянагч томилох, хугацаа, хугацаа хэтэрсэн мөрийг эскалац хийх (A.5.18).
* Түр ба давуу эрхийн хүсэлт: үндэслэл, батлах, хугацаа дуусахад автоматаар хасах (A.5.18, A.8.2).
* Давуу эрхийн тайлан: зөвхөн эрх бүхий ажилтнуудад, нууц үг ба TOTP нууцгүй (A.8.2, A.5.15).
* Өөрийгөө баталгаажуулах, өөрийн хүсэлтийг батлах, эрхийн хуваарилалтыг сервер талд хориглоно (GOV-05).
""",
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr', 'university_isms', 'university_access_review'],
    'data': [
        'security/ir.model.access.csv',
        'security/access_governance_security.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/access_governance_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
