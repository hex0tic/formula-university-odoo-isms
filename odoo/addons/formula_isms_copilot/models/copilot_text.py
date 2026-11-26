"""Туслахын текстийн туслах функцүүд (ORM-гүй, цэвэр Python).

* токенчлол ба хайлтын үг,
* бичлэгийн текстийг өгөгдөл гэж цэвернэх, заавар шиг текстийг шүүж тэмдэглэх (prompt injection),
* PII маскчилт (имэйл, IP, оюутны код, хэрэглэгчийн нэр),
* татгалзах (action request) ангилал.
"""
import re

AUTO_LABEL = 'Автомат хураангуй — аудитын нотолгоо биш'
SUGGESTION_LABEL = 'Санал — шийдвэрийг эрх бүхий хүн гаргана'
DISCLAIMER = (
    'Энэ хариулт автоматаар бэлтгэгдсэн бөгөөд аудитын нотолгоо биш. '
    'Эх бичлэгийг нээж баталгаажуулна уу.'
)
INJECTION_MARK = '[шүүгдсэн: заавар шиг текст]'

STOPWORDS = frozenset({
    'ба', 'бол', 'юу', 'вэ', 'ямар', 'нь', 'уу', 'үү', 'юм', 'бэ', 'байна', 'байгаа', 'харуул',
    'өгөх', 'хэн', 'хаана', 'хэд', 'тухай', 'талаар', 'гэж', 'вэ', 'бас', 'эсвэл', 'дээр',
    'the', 'and', 'what', 'which', 'show', 'list', 'about', 'for', 'with', 'how', 'many', 'are',
    'is', 'of', 'to', 'in', 'on', 'me', 'give', 'tell', 'please', 'does', 'do', 'an', 'a', 'or',
})

# Бичлэгийн текстэд заавар шиг хэсгийг илрүүлэх (prompt injection). Илэрвэл тэмдэглэж, шүүнэ.
INJECTION_RULES = [
    re.compile(r'ignore\s+(?:all\s+|the\s+|any\s+)?(?:previous|prior|above|earlier)\s+'
               r'(?:instructions?|prompts?|messages?|rules?)', re.I),
    re.compile(r'disregard\s+(?:all\s+|the\s+|any\s+|your\s+)?(?:previous|prior|above|earlier|system)\b', re.I),
    re.compile(r'forget\s+(?:all\s+|the\s+)?(?:previous|prior|above)\b', re.I),
    re.compile(r'\b(?:system|assistant|developer)\s*:', re.I),
    re.compile(r'\byou\s+are\s+now\b', re.I),
    re.compile(r'\bnew\s+instructions?\b', re.I),
    re.compile(r'\bact\s+as\s+(?:an?\s+|the\s+)?', re.I),
    re.compile(r'</?\s*(?:system|instructions?|prompt|source)\b[^>]*>', re.I),
    re.compile(r'\[/?inst\]', re.I),
    re.compile(r'<\|[^|>]{1,40}\|>'),
    re.compile(r'(?:өмнөх|дээрх|бүх)\s+(?:бүх\s+)?заавар\w*', re.I),
    re.compile(r'заавар\w*\s+(?:үл|бүү|мартаж|анхаарахгүй)\w*', re.I),
    re.compile(r'(?:шинэ|дараах)\s+заавар\w*', re.I),
    re.compile(r'систем\w*\s*:', re.I),
]

# Татгалзах ангилал: (кодын түлхүүр, илрүүлэгч, тайлбар)
REFUSAL_RULES = [
    ('approve', re.compile(r'(батлаарай|батлаач|батлах|батлаад|баталж|батал\b|батлуул|батална\s+уу|\bapprove\b|\bsign\s+off\b)', re.I),
     'Бодлого, SoA-г батлах'),
    ('close_incident', re.compile(r'(хаа(?:х|ж|гаарай|ач|я|чих)\b|\bclose\s+(?:the\s+|this\s+|it\b)?(?:incident|ticket|finding|it\b|this\b))', re.I),
     'Инцидент, олдворыг хаах'),
    ('accept_risk', re.compile(r'(хүлээн\s+зөвшөөр(?!сөн|сэн|өгдсөн)|хүлээн\s+зөвшөөрч|\baccept\s+(?:the\s+|this\s+)?risk\b|\baccept\s+it\b)', re.I),
     'Эрсдэл хүлээн зөвшөөрөх'),
    ('grant_access', re.compile(r'(эрх\s*(?:өг|олго|нэм)|олгоорой|олгож\s+өг|\bgrant\b|\bgive\s+(?:me\s+|them\s+)?access\b)', re.I),
     'Эрх олгох'),
    ('change_grade', re.compile(r'(дүн\w*\s*(?:өөрчил|засаарай|засах|тавь|өг|солих)|оноо\w*\s*(?:өөрчил|засаарай|засах|тавь|өг|солих)|'
                                r'\b(?:change|set|update)\s+(?:the\s+)?(?:grade|mark|score)s?\b)', re.I),
     'Дүн, оноо өөрчлөх'),
    ('delete', re.compile(r'(устга\w*|\bdelete\b|\bremove\s+(?:it|this|the)\b)', re.I), 'Устгах'),
    ('modify', re.compile(r'(өөрчил(?:өөрэй|өх|ье|ж\s+өг)\b|засаарай|засаж\s+өг|засна\s+уу|солиорой|\bchange\s+the\s+status\b|\bupdate\s+the\s+status\b)', re.I),
     'Төлөв, талбар өөрчлөх'),
]

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
IPV4_RE = re.compile(r'\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b')
IPV6_RE = re.compile(r'\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b')
STUDENT_RE = re.compile(r'\b(?:[A-Za-z]{1,4}\d{5,}|\d{7,10})\b')


def stem(token):
    """Монгол хэлний залгаврыг тайван таслах (эрсдэлүүд ~ эрсдэл)."""
    return token if len(token) <= 4 else token[:len(token) - 2]


def tokenize(question, limit=8):
    tokens = []
    for tok in re.findall(r'[^\W_]+', (question or '').lower()):
        if len(tok) < 2 or tok in STOPWORDS:
            continue
        if tok not in tokens:
            tokens.append(tok)
        if len(tokens) >= limit:
            break
    return tokens


def extract_codes(question):
    """A.5.15, 5.15, INC-12 гэх мэт кодыг олно. 'A.' угтварыг хасаж хоёр хувилбар буцаана."""
    codes = []
    for raw in re.findall(r'\b[A-Za-z]{1,6}[.\-]\d[\w.\-]*|\b\d{1,2}\.\d{1,2}(?:\.\d{1,2})?\b', question or ''):
        for value in (raw, re.sub(r'^[Aa]\.', '', raw)):
            if value and value.lower() not in [c.lower() for c in codes]:
                codes.append(value)
    return codes


def sanitize_text(text, max_len=4000):
    """Бичлэгийн текстийг өгөгдөл болгоно: зай цэвэрлэж, заавар шиг хэсгийг шүүнэ.

    Буцаах утга: (цэвэр текст, injection илэрсэн эсэх)."""
    flat = re.sub(r'\s+', ' ', (text or ''))[:max_len].strip()
    flagged = False
    for pattern in INJECTION_RULES:
        if pattern.search(flat):
            flagged = True
            flat = pattern.sub(INJECTION_MARK, flat)
    return flat, flagged


def make_snippet(clean_text, tokens, width=200):
    if not clean_text:
        return ''
    low = clean_text.lower()
    pos = -1
    for tok in tokens:
        needle = stem(tok)
        found = low.find(needle)
        if found >= 0 and (pos < 0 or found < pos):
            pos = found
    start = max(0, pos - width // 3) if pos >= 0 else 0
    snippet = clean_text[start:start + width]
    if start > 0:
        snippet = '…' + snippet
    if start + width < len(clean_text):
        snippet += '…'
    return snippet


def redact(text, user_names=()):
    """Имэйл, IP, оюутны код, хэрэглэгчийн нэрийг маскална (гадаад провайдер ба аудит лог)."""
    text = EMAIL_RE.sub('[EMAIL]', text or '')
    text = IPV4_RE.sub('[IP]', text)
    text = IPV6_RE.sub('[IP]', text)
    text = STUDENT_RE.sub('[ID]', text)
    for name in sorted({n for n in user_names if n and len(n) >= 3}, key=len, reverse=True):
        text = re.sub(re.escape(name), '[USER]', text, flags=re.IGNORECASE)
    return text


def detect_refusal(question):
    """Асуулт нь бичих/шийдвэрлэх үйлдэл хүсэж байгаа эсэх. Буцаах: (түлхүүр, тайлбар) эсвэл None."""
    for key, pattern, label in REFUSAL_RULES:
        if pattern.search(question or ''):
            return key, label
    return None


def text_of_html(html_value):
    from odoo.tools import html2plaintext
    return html2plaintext(html_value or '')
