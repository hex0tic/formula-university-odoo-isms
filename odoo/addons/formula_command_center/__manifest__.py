{
    'name': 'Formula Command Center (ISMS)',
    'version': '18.0.1.1.0',
    'category': 'Services/ISMS',
    'summary': 'ISMS Command Center: эрхээс хамаарсан KPI, 5x5 эрсдэлийн heatmap, инцидентийн SLA, хяналтын хамрах хүрээ',
    'description': """
ISMS Command Center (Formula ERP, Phase 2)
==========================================

* Эрхийн ORM дүрмээр шүүгдсэн KPI (хөрөнгө, эрсдэл, хяналт, инцидент, бодлого, хариу арга хэмжээ).
* Эрсдэлийн 5x5 interactive heatmap: анхдагч ба үлдэгдэл эрсдэл, university_isms.matrix_level-ээр өнгөлнө.
* KPI бүрт drill-down (модел + domain): дарахад тухайн бичлэгүүд нээгдэнэ.
* Хандах эрхгүй хэсгүүд алдаа биш, «Хандах эрхгүй» гэж харагдана (sudo ашиглахгүй).
""",
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['web', 'university_isms', 'project'],
    'data': [
        'views/command_center_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'formula_command_center/static/src/command_center/command_center.scss',
            'formula_command_center/static/src/command_center/command_center.js',
            'formula_command_center/static/src/command_center/command_center.xml',
        ],
    },
    'application': False,
    'installable': True,
}
