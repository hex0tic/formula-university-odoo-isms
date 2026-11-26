{
    'name': 'University ISMS Control Tests and Monitoring',
    'version': '18.0.1.0.0',
    'category': 'Services/ISMS',
    'summary': 'Хяналтын тестийн төлөвлөгөө, автомат хяналт (cron) ба олдвор үүсгэх (ISO/IEC 27001:2022 9.1, A.8.16)',
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['university_isms_capa'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/control_test_views.xml',
        'views/menus.xml',
        'data/control_test_seed.xml',
    ],
    'installable': True,
    'application': False,
}
