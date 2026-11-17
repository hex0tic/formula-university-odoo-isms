# Odoo shell-ээр ажиллана: орчны суурь тохиргоо (нэг удаа, дахин ажиллуулахад аюулгүй).
# - Компанийн мэдээлэл: зохиомол «Formula University» (decisions.md D02)
# - admin-ийн анхдагч нууц үгийг .env-ийн санамсаргүй утгаар солих (A.5.17)
# - Нууц үгийн хамгийн бага урт (auth_password_policy, A.5.17)
import base64
import os

company = env.ref('base.main_company')
mnt = env.ref('base.MNT')
mnt.active = True
company.write({
    'name': 'Formula University',
    'country_id': env.ref('base.mn').id,
    'currency_id': mnt.id,
    'city': 'Улаанбаатар',
    'street': 'Төв кампус, I байр',
    'website': 'https://formula-university.example',
    'email': 'isms@formula-university.example',
    'company_registry': 'ЗОХИОМОЛ КЕЙС',
})
logo = '/mnt/extra-addons/university_isms/static/img/formula_logo.png'
if os.path.exists(logo):
    company.logo = base64.b64encode(open(logo, 'rb').read())  # D08: Formula University

admin = env.ref('base.user_admin')
password = os.environ.get('ODOO_ADMIN_PASSWORD')
vals = {'tz': 'Asia/Ulaanbaatar'}
if password:
    vals['password'] = password
admin.write(vals)

env['ir.config_parameter'].sudo().set_param('auth_password_policy.minlength', 10)
# A.5.16/A.5.18: чөлөөт бүртгэлийг (b2c) хааж, зөвхөн урилгаар данс олгоно (b2b)
env['ir.config_parameter'].sudo().set_param('auth_signup.invitation_scope', 'b2b')
env.cr.commit()
print('BOOTSTRAP OK company=%s admin_password_changed=%s minlength=%s signup=%s' % (
    company.name, bool(password), env['ir.config_parameter'].get_param('auth_password_policy.minlength'),
    env['ir.config_parameter'].get_param('auth_signup.invitation_scope')))
