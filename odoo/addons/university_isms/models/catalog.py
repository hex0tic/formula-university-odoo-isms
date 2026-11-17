from odoo import fields, models


class IsmsThreat(models.Model):
    _name = 'isms.threat'
    _description = 'Аюул занал (Threat)'
    _inherit = ['isms.audit.mixin']
    _order = 'code'
    _rec_names_search = ['code', 'name']

    code = fields.Char('Код', required=True, index=True)
    name = fields.Char('Аюул занал', required=True)
    category = fields.Selection([
        ('deliberate', 'Санаатай хүний үйлдэл'),
        ('accidental', 'Санамсаргүй хүний алдаа'),
        ('technical', 'Техникийн доголдол'),
        ('environmental', 'Байгаль, орчны'),
        ('supplier', 'Нийлүүлэгч, гуравдагч тал'),
    ], 'Ангилал', required=True, default='deliberate')
    description = fields.Text('Тайлбар')
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_uniq', 'unique(code)', 'Аюул заналын код давхардахгүй.')]

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.name) if rec.code else rec.name


class IsmsVulnerability(models.Model):
    _name = 'isms.vulnerability'
    _description = 'Эмзэг байдал (Vulnerability)'
    _inherit = ['isms.audit.mixin']
    _order = 'code'
    _rec_names_search = ['code', 'name']

    code = fields.Char('Код', required=True, index=True)
    name = fields.Char('Эмзэг байдал', required=True)
    category = fields.Selection([
        ('technical', 'Техникийн'),
        ('process', 'Процесс, журам'),
        ('people', 'Хүний'),
        ('physical', 'Физик'),
    ], 'Ангилал', required=True, default='technical')
    description = fields.Text('Тайлбар')
    active = fields.Boolean(default=True)

    _sql_constraints = [('code_uniq', 'unique(code)', 'Эмзэг байдлын код давхардахгүй.')]

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.name) if rec.code else rec.name
