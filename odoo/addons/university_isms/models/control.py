"""ISO/IEC 27001:2022 Annex A хяналтууд ба Statement of Applicability (Clause 6.1.3 d)."""
from odoo import api, fields, models

THEMES = [
    ('organizational', '5. Зохион байгуулалтын'),
    ('people', '6. Хүний'),
    ('physical', '7. Физик'),
    ('technological', '8. Технологийн'),
]


class IsmsControl(models.Model):
    _name = 'isms.control'
    _description = 'Annex A хяналт / SoA'
    _inherit = ['mail.thread', 'isms.audit.mixin']
    _order = 'sequence, id'
    _rec_names_search = ['code', 'name', 'name_mn']

    code = fields.Char('Хяналтын дугаар', required=True, index=True)
    sequence = fields.Integer('Дараалал', default=100)
    name = fields.Char('Хяналт (EN)', required=True)
    name_mn = fields.Char('Хяналт (MN)')
    theme = fields.Selection(THEMES, 'Сэдэв', required=True)
    is_new_2022 = fields.Boolean('2022 онд шинээр нэмэгдсэн')

    # Statement of Applicability
    selected = fields.Boolean('Controls Mapping-д сонгосон', tracking=True,
                              help='Багийн 20–25 хяналтын жагсаалтад багтсан эсэх')
    applicable = fields.Boolean('Хамааралтай', default=True, tracking=True)
    implementation = fields.Selection([
        ('yes', 'Тийм'),
        ('partial', 'Хэсэгчилсэн'),
        ('no', 'Үгүй'),
    ], 'Хэрэгжсэн үү?', default='no', tracking=True)
    justification = fields.Text('Тайлбар / шалтгаан, үндэслэл')
    odoo_implementation = fields.Text('Odoo дахь хэрэгжилт')
    evidence = fields.Text('Нотолгоо')
    responsible_id = fields.Many2one('res.users', 'Хариуцагч', tracking=True)
    risk_ids = fields.Many2many('isms.risk', 'isms_risk_control_rel', 'control_id', 'risk_id',
                                string='Холбогдох эрсдэл')
    asset_ids = fields.Many2many('isms.asset', 'isms_asset_control_rel', 'control_id', 'asset_id',
                                 string='Холбогдох хөрөнгө')
    risk_count = fields.Integer('Эрсдэлийн тоо', compute='_compute_risk_count')

    _sql_constraints = [('code_uniq', 'unique(code)', 'Хяналтын дугаар давхардахгүй.')]

    @api.depends('risk_ids')
    def _compute_risk_count(self):
        for rec in self:
            rec.risk_count = len(rec.risk_ids)

    @api.depends('code', 'name', 'name_mn')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = 'A.%s %s' % (rec.code, rec.name_mn or rec.name)

    def action_open_risks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'A.%s — эрсдэл' % self.code,
            'res_model': 'isms.risk',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.risk_ids.ids)],
        }
