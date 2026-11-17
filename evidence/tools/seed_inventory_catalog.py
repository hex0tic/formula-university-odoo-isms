"""Odoo shell: idempotent Inventory catalog for sixteen synthetic case assets.

Information assets are non-stock service catalog entries; physical hardware
gets one representative DEMO serial. No purchase, valuation or stock count is
fabricated, and no physical equipment is claimed to have been installed.
"""
import json

result = []
for asset in env["isms.asset"].search([], order="code"):
    product = env["product.product"].search([("default_code", "=", asset.code)], limit=1)
    physical = asset.asset_type == "hardware"
    values = {
        "name": asset.name, "default_code": asset.code,
        "type": "consu" if physical else "service", "sale_ok": False, "purchase_ok": False,
        "isms_catalog_asset_id": asset.id,
    }
    if physical:
        values.update({"is_storable": True, "tracking": "serial"})
    if product:
        product.write(values)
    else:
        product = env["product.product"].create(values)
    asset.product_id = product
    serial = False
    if physical:
        serial = "DEMO-" + asset.code + "-001"
        lot = env["stock.lot"].search([("name", "=", serial), ("product_id", "=", product.id)], limit=1)
        if not lot:
            lot = env["stock.lot"].create({"name": serial, "product_id": product.id, "company_id": env.company.id})
        asset.lot_id = lot
    result.append({"asset": asset.code, "product_id": product.id, "type": product.type,
                   "representative_demo_serial": serial, "owner": asset.owner_id.login,
                   "classification": asset.classification, "location": asset.location})
assert len(result) >= 10
env.cr.commit()
print("INVENTORY_RESULT_JSON=" + json.dumps({"result": "PASS", "count": len(result), "records": result}, ensure_ascii=False))
