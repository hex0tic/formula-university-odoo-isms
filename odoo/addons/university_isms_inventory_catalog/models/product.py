from odoo import fields, models


class ProductAssetCatalog(models.Model):
    _inherit = "product.product"

    isms_catalog_asset_id = fields.Many2one("isms.asset", string="ISMS хөрөнгө", ondelete="restrict")
    isms_catalog_owner_id = fields.Many2one(related="isms_catalog_asset_id.owner_id", string="Эзэмшигч")
    isms_catalog_classification = fields.Selection(related="isms_catalog_asset_id.classification", string="Ангилал")
    isms_catalog_location = fields.Char(related="isms_catalog_asset_id.location", string="Байршил")
    isms_catalog_risk = fields.Selection(related="isms_catalog_asset_id.risk_level", string="Эрсдэл")

    _sql_constraints = [("asset_unique", "unique(isms_catalog_asset_id)", "Хөрөнгийн Inventory холбоос давхардахгүй.")]
