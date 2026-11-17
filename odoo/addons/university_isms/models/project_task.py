from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    isms_risk_id = fields.Many2one('isms.risk', 'ISMS эрсдэл', index=True, ondelete='set null',
                                   help='Эрсдэлийг бууруулах төлөвлөгөөний (Risk Treatment Plan) даалгавар')
