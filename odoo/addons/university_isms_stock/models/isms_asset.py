from odoo import api, fields, models


class IsmsAsset(models.Model):
    _inherit = 'isms.asset'

    product_id = fields.Many2one('product.product', 'Inventory бараа', tracking=True,
                                 help='Тоног төхөөрөмжийн хөрөнгийг Inventory-ийн бараатай холбоно')
    lot_id = fields.Many2one('stock.lot', 'Серийн дугаар', tracking=True,
                             domain="[('product_id', '=', product_id)]")
    stock_location_id = fields.Many2one('stock.location', 'Агуулахын байршил',
                                        related='lot_id.location_id', readonly=True)

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        if self.lot_id and not self.product_id:
            self.product_id = self.lot_id.product_id


class StockLot(models.Model):
    _inherit = 'stock.lot'

    isms_asset_ids = fields.One2many('isms.asset', 'lot_id', 'ISMS хөрөнгө', groups='university_isms.group_isms_asset_owner,university_isms.group_isms_auditor')
    isms_asset_count = fields.Integer('ISMS хөрөнгө', compute='_compute_isms_asset_count', groups='university_isms.group_isms_asset_owner,university_isms.group_isms_auditor')

    def _compute_isms_asset_count(self):
        for lot in self:
            lot.isms_asset_count = len(lot.sudo().isms_asset_ids)

    def action_open_isms_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'ISMS хөрөнгө',
            'res_model': 'isms.asset',
            'view_mode': 'list,form',
            'domain': [('lot_id', '=', self.id)],
            'context': {'default_lot_id': self.id, 'default_product_id': self.product_id.id,
                        'default_asset_type': 'hardware'},
        }
