from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'university_isms_stock')
class TestIsmsStock(TransactionCase):
    def test_asset_linked_to_serial_and_location(self):
        product = self.env['product.product'].create({
            'name': 'Тест сервер', 'is_storable': True, 'tracking': 'serial'})
        lot = self.env['stock.lot'].create({'name': 'SRV-TEST-001', 'product_id': product.id})
        location = self.env.ref('stock.stock_location_stock')
        self.env['stock.quant']._update_available_quantity(product, location, 1, lot_id=lot)
        asset = self.env['isms.asset'].create({
            'name': 'Тест сервер', 'asset_type': 'hardware', 'product_id': product.id, 'lot_id': lot.id})
        self.assertEqual(asset.stock_location_id, location)
        self.assertEqual(lot.isms_asset_count, 1)
