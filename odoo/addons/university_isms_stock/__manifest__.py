{
    'name': 'University ISMS — Inventory bridge',
    'version': '18.0.1.1.0',
    'category': 'Services/ISMS',
    'summary': 'ISMS хөрөнгийн бүртгэлийг Odoo Inventory-ийн бараа, серийн дугаар, байршилтай холбоно (A.5.9, A.5.11, A.7.10, A.7.14)',
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['university_isms', 'stock'],
    'data': ['views/isms_stock_views.xml'],
    'installable': True,
    'auto_install': False,
}
