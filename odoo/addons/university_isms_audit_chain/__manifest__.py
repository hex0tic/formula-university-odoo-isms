{
    'name': 'University ISMS Audit Chain and Log Forwarding',
    'version': '18.0.1.0.0',
    'category': 'Services/ISMS',
    'summary': 'Аудит логийн hash гинж, DB түвшний хамгаалалт, гадаад дамжуулалт ба хадгалалтын бодлого (ISO/IEC 27001:2022 A.8.15, A.5.28)',
    'description': """
Аудит логийн гинжин хэш (hash chain), PostgreSQL trigger-ээр хамгаалалт, JSONL файл болон
HTTP(S) endpoint руу багцлан дамжуулах дараалал, хадгалалтын бодлого, гинжийн шалгалт
ба мониторингийн шалгалт (audit_chain_integrity).

Хязгаарлалт: PostgreSQL superuser trigger-ийг унтраах боломжтой тул энэ модуль ганцаараа
бүрэн tamper-evidence өгөхгүй. Бодит tamper-evidence нь hash гинж + гадаад (дамжуулсан) хэш
анкерлэлтээс бүрдэнэ. Дэлгэрэнгүйг README (module docs) болон SEC-02 тайланд үзнэ үү.
""",
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['university_isms', 'university_isms_monitoring_plus'],
    'data': [
        'security/ir.model.access.csv',
        'views/audit_chain_views.xml',
        'data/ir_cron_data.xml',
        'data/control_test_seed.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'application': False,
}
