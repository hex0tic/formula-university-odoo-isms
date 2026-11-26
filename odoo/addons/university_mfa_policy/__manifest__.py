{
    'name': 'University MFA Step-up Policy',
    'version': '18.0.1.0.0',
    'category': 'Services/ISMS',
    'summary': 'Давуу эрхтэй хэрэглэгчийн чухал үйлдэлд TOTP шаардах, түгжихгүйгээр шат дараатай нэвтрүүлэх (A.8.5)',
    'description': """
Давуу эрхтэй хэрэглэгч (Settings, Access Rights, CISO, сургалтын алба) TOTP идэвхжүүлээгүй бол
тогтоосон огнооноос хойш бодлого батлах, зөрчил хаах, эрсдэл хүлээн зөвшөөрөх, дүн батлах,
эрх өөрчлөх үйлдлийг сервер хориглоно. Нэвтрэлтийг хаахгүй тул хэрэглэгч түгжигдэхгүй.
Огноо тохируулаагүй үед зөвхөн сануулга харуулна.
""",
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['auth_totp', 'university_isms', 'campus_university', 'university_access_review'],
    'data': ['data/ir_config_parameter_data.xml'],
    'assets': {
        'web.assets_backend': ['university_mfa_policy/static/src/mfa_notice.js'],
    },
    'installable': True,
}
