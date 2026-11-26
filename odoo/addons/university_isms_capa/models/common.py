"""CAPA / эрсдлийн зөвшөөрлийн урсгалын туслах функцүүд (сервер талын эрхийн шалгалт).

Эрхийг UI-гаас хамаарахгүйгээр бодит хэрэглэгчийн группоор шалгана. `sudo()` болон
`isms_transition` токеноор хийгдэх дотоод бичилт нь зөвхөн эдгээр шалгалтаас хойш дуудагдана.
"""
from odoo import _
from odoo.exceptions import AccessError

GROUP_OWNER = 'university_isms.group_isms_asset_owner'
GROUP_ANALYST = 'university_isms.group_isms_analyst'
GROUP_AUDITOR = 'university_isms.group_isms_auditor'
GROUP_CISO = 'university_isms.group_isms_manager'


def require_group(env, xmlid, label):
    """Бодит хэрэглэгч (sudo-гүй) тухайн группд байгаа эсэхийг шалгана."""
    if not env.user.has_group(xmlid):
        raise AccessError(_('Энэ үйлдлийг зөвхөн %s гүйцэтгэнэ.') % label)
