{
    'name': 'University ISMS (ISO/IEC 27001:2022)',
    'version': '18.0.1.0.0',
    'category': 'Services/ISMS',
    'summary': 'Их сургуулийн МАБ-ын удирдлагын тогтолцоо: хөрөнгө, эрсдэл, Annex A/SoA, '
               'инцидент, бодлого, аудит лог, RBAC',
    'description': """
Formula University-ийн ISMS платформ
=============================================
* Мэдээллийн хөрөнгийн бүртгэл (A.5.9, A.5.12)
* Эрсдэлийн бүртгэл, 5x5 матриц, хариу арга хэмжээ (Clause 6.1.2-6.1.3)
* ISO/IEC 27001:2022 Annex A 93 хяналт ба Statement of Applicability
* Инцидентийн удирдлага: Incident, Report, Investigate, Resolve, Close (A.5.24-5.28)
* ISMS бодлогын бүртгэл, танилцсан бүртгэл (A.5.1, A.5.37)
* Өөрчлөх, устгах боломжгүй аудит лог (A.8.15, A.8.16) ба 5 түвшний RBAC (A.5.15, A.8.2)
""",
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr', 'project'],
    'data': [
        'security/isms_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/isms.control.csv',
        'data/isms_catalog_data.xml',
        'data/project_data.xml',
        'views/audit_views.xml',
        'views/catalog_views.xml',
        'views/control_views.xml',
        'views/asset_views.xml',
        'views/risk_views.xml',
        'views/incident_views.xml',
        'views/policy_views.xml',
        'views/project_task_views.xml',
        'report/isms_reports.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
}
