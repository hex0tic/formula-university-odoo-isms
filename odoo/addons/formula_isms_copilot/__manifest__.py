{
    'name': 'Formula ISMS туслах (Copilot)',
    'version': '18.0.1.0.0',
    'category': 'Services/ISMS',
    'summary': 'Зөвхөн унших, эрхэд суурилсан ISMS хайлт, хураангуй, санал (AI-01..AI-05)',
    'description': """
Formula ISMS туслах (Phase 7, AI-01..AI-05)
==========================================

* Бодлого, Annex A хяналт (SoA), эрсдэл, хөрөнгө, инцидент, олдвор, нотолгоо, аудит лог дээр
  хайлт хийж, хариултыг бичлэгийн холбоосоор баримтжуулна. Бүх хайлт хэрэглэгчийн ORM эрхээр
  (ACL + record rule) явагдана; sudo() ашиглахгүй.
* Анхдагч хөдөлгүүр нь детерминистик, дотоод (сүлжээ ашиглахгүй) тодорхойлогч хураангуй.
* Гадаад LLM провайдерын адаптер нь анхдагчаар унтраалттай. Идэвхжүүлэхэд админ тохируулга,
  өгөгдлийн бодлогын зөвшөөрөл, PII маскчилт шаардлагатай; алдаа гарвал дотоод хөдөлгүүр руу буцна.
* Prompt injection-ий хамгаалалт: бичлэгийн текст өгөгдөл гэж хүлээн авна, заавар шиг текст
  шүүгдэж тэмдэглэгдэнэ. Туслах руу бичих (approve, close, grant, accept, delete, grade) эрхгүй;
  ийм хүсэлтэд татгалзаж зөв ажлын урсгалын холбоос өгнө.
* Санал (AI-03): эрсдэл -> Annex A хяналт, инцидент -> хураангуй, хяналт -> дутуу нотолгоо.
* Асуулт бүрийг аудит лог (formula.copilot.query.log)-д хадгална; хариултын текст хадгалахгүй.
""",
    'author': 'Formula5 баг (ШУТИС МХТС)',
    'license': 'LGPL-3',
    'depends': ['web', 'university_isms'],
    'data': [
        'security/ir.model.access.csv',
        'data/copilot_data.xml',
        'views/copilot_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'formula_isms_copilot/static/src/copilot/copilot.scss',
            'formula_isms_copilot/static/src/copilot/copilot.js',
            'formula_isms_copilot/static/src/copilot/copilot.xml',
        ],
    },
    'application': False,
    'installable': True,
}
