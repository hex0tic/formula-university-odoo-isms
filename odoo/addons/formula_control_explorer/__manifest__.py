{
    'name': 'Formula ISO Control Explorer (ISMS)',
    'version': '18.0.1.0.0',
    'category': 'Services/ISMS',
    'summary': 'ISO/IEC 27001:2022 Annex A 93 хяналтын каталог, SoA дэлгэрэнгүй, холбоос, тооцсон шалгалт',
    'description': """
ISO Control Explorer (Formula ERP, Phase 3, WF-05)
==================================================

* Annex A 93 хяналтын каталог: тэмдэглэгээ, сэдэв, хэрэгжилт, хариуцагчаар шүүнэ.
* Хяналт бүрийн SoA талбар, хариуцагч, холбоотой эрсдэл, хөрөнгө, бодлого, инцидент.
* Бүх өгөгдөл хэрэглэгчийн ORM эрхээр уншигдана (sudo() ашиглахгүй). Уншиж чадахгүй
  бичлэг, талбарыг жагсаалтад оруулахгүй.
* Тооцсон шалгалтууд (computed checks) нь аудитын дүгнэлт биш.
* Засвар: зөвхөн стандарт «Хяналт» маягтаар хийгдэнэ.
""",
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['web', 'university_isms'],
    'data': [
        'views/control_explorer_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'formula_control_explorer/static/src/control_explorer/control_explorer.scss',
            'formula_control_explorer/static/src/control_explorer/control_explorer.js',
            'formula_control_explorer/static/src/control_explorer/control_explorer.xml',
        ],
    },
    'application': False,
    'installable': True,
}
