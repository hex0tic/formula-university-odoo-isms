from odoo import fields, models


class ProductAssetCatalog(models.Model):
    _inherit = "product.product"

    # ISMS-ийн хязгаарлагдмал мэдээллийг зөвхөн хөрөнгө эзэмшигч, шинжээч, аудиторт (A.5.12, A.8.3)
    isms_catalog_asset_id = fields.Many2one("isms.asset", string="ISMS хөрөнгө", ondelete="restrict",
                                            groups="university_isms.group_isms_asset_owner,university_isms.group_isms_auditor")
    isms_catalog_owner_id = fields.Many2one(related="isms_catalog_asset_id.owner_id", string="Эзэмшигч", groups="university_isms.group_isms_asset_owner,university_isms.group_isms_auditor")
    isms_catalog_classification = fields.Selection(related="isms_catalog_asset_id.classification", string="Ангилал", groups="university_isms.group_isms_asset_owner,university_isms.group_isms_auditor")
    isms_catalog_location = fields.Char(related="isms_catalog_asset_id.location", string="Байршил", groups="university_isms.group_isms_asset_owner,university_isms.group_isms_auditor")
    isms_catalog_risk = fields.Selection(related="isms_catalog_asset_id.risk_level", string="Эрсдэл", groups="university_isms.group_isms_asset_owner,university_isms.group_isms_auditor")

    _sql_constraints = [("asset_unique", "unique(isms_catalog_asset_id)", "Хөрөнгийн Inventory холбоос давхардахгүй.")]
