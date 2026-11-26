# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
"""Asset bundle compile test: SCSS or Owl errors in campus_portal fail this test.

preprocess_css() compiles the SCSS from source (not a cached attachment) and css_errors must stay empty.
"""
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "campus_portal")
class TestCampusPortalAssets(TransactionCase):

    def test_backend_bundle_compiles_teacher_styles(self):
        bundle = self.env["ir.qweb"]._get_asset_bundle("web.assets_backend", debug_assets=False)
        compiled = bundle.preprocess_css()
        self.assertEqual(bundle.css_errors, [], "SCSS errors in web.assets_backend: %s" % bundle.css_errors)
        self.assertIn(".o_campus_teacher", compiled)

    def test_frontend_bundle_compiles_portal_styles(self):
        bundle = self.env["ir.qweb"]._get_asset_bundle("web.assets_frontend", debug_assets=False)
        compiled = bundle.preprocess_css()
        self.assertEqual(bundle.css_errors, [], "SCSS errors in web.assets_frontend: %s" % bundle.css_errors)
        self.assertIn(".o_campus_portal", compiled)

    def test_teacher_client_action_is_in_backend_bundle(self):
        bundle = self.env["ir.qweb"]._get_asset_bundle("web.assets_backend", debug_assets=False)
        js_assets = [asset for asset in bundle.javascripts if "campus_portal" in asset.url]
        self.assertTrue(js_assets, "campus_portal JavaScript is not part of web.assets_backend")
        self.assertTrue(any("campus_portal_teacher" in asset.content for asset in js_assets))
        xml_assets = [asset for asset in bundle.templates if "campus_portal" in asset.url]
        self.assertTrue(xml_assets, "campus_portal templates are not part of web.assets_backend")
        self.assertTrue(any("campus_portal.TeacherPortal" in asset.content for asset in xml_assets))
