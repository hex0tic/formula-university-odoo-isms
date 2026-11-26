"""Backend asset bundle compile test: SCSS алдаа гарвал энэ тест унана.

``ir.attachment``-д хадгалагдсан хуучин хувилбарыг ашиглахгүйн тулд ``preprocess_css()``-ээр
эх SCSS-ийг шууд компайлдаж ``css_errors``-ыг шалгана (Odoo 18 ``AssetsBundle`` API).
Дараа нь ``css()``-ийг дуудаж гаралтын замыг (attachment) мөн баталгаажуулна.
"""
from xml.etree import ElementTree

from odoo.tests import TransactionCase, tagged

SCSS_SELECTOR = '.o_formula_control_explorer'


@tagged('post_install', '-at_install', 'formula_control_explorer')
class TestBackendAssetsCompile(TransactionCase):

    def test_backend_bundle_compiles_without_css_errors(self):
        bundle = self.env['ir.qweb']._get_asset_bundle('web.assets_backend', debug_assets=False)
        compiled = bundle.preprocess_css()
        self.assertEqual(bundle.css_errors, [],
                         'SCSS compile errors in web.assets_backend: %s' % bundle.css_errors)
        self.assertIn(SCSS_SELECTOR, compiled,
                      'Control Explorer SCSS is not part of the compiled backend bundle')

        attachment = bundle.css()
        self.assertEqual(bundle.css_errors, [],
                         'CSS output step reported errors: %s' % bundle.css_errors)
        self.assertTrue(attachment, 'css() did not return a stored bundle')

    def test_control_explorer_js_and_templates_transpile(self):
        """Owl JS-ийг серверт transpile хийж (синтаксийн алдааг барина), XML template-ийг шалгана."""
        bundle = self.env['ir.qweb']._get_asset_bundle('web.assets_backend', debug_assets=False)
        js_assets = [asset for asset in bundle.javascripts
                     if 'formula_control_explorer' in asset.url]
        self.assertTrue(js_assets, 'Control Explorer JS is not part of web.assets_backend')
        for asset in js_assets:
            # asset.content нь @odoo-module хөрвүүлэлт (transpile_javascript); алдаатай бол exception
            transpiled = asset.content
            self.assertIn('formula_control_explorer', transpiled)

        xml_assets = [asset for asset in bundle.templates
                      if 'formula_control_explorer' in asset.url]
        self.assertTrue(xml_assets, 'Control Explorer templates are not part of the bundle')
        for asset in xml_assets:
            root = ElementTree.fromstring(asset.content)
            names = [node.get('t-name') for node in root.iter('t')]
            self.assertIn('formula_control_explorer.Explorer', names)
