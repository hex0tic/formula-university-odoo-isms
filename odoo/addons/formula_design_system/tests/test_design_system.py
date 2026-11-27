# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase, tagged

ADDON = "formula_design_system"
LIGHT_TOKENS = f"{ADDON}/static/src/scss/fds_tokens.scss"
DARK_TOKENS = f"{ADDON}/static/src/scss/fds_tokens.dark.scss"
BASE_SCSS = f"{ADDON}/static/src/scss/fds_base.scss"
COMPONENTS_SCSS = f"{ADDON}/static/src/scss/fds_components.scss"
TOGGLE_JS = f"{ADDON}/static/src/js/theme_toggle.js"
TOGGLE_XML = f"{ADDON}/static/src/xml/theme_toggle.xml"


@tagged("post_install", "-at_install", "formula_design_system")
class TestFormulaDesignSystemAssets(TransactionCase):

    def _bundle_paths(self, bundle_name):
        asset = self.env["ir.asset"]
        params = asset._get_asset_params()
        # Each entry is (path, full_path, bundle, last_modified); paths start with "/".
        return [entry[0].lstrip("/") for entry in asset._get_asset_paths(bundle_name, params)]

    def test_backend_bundle_registers_light_assets(self):
        paths = self._bundle_paths("web.assets_backend")
        for path in (LIGHT_TOKENS, BASE_SCSS, COMPONENTS_SCSS, TOGGLE_JS, TOGGLE_XML):
            self.assertIn(path, paths, "%s missing from web.assets_backend" % path)

    def test_dark_tokens_only_in_dark_bundle(self):
        self.assertNotIn(DARK_TOKENS, self._bundle_paths("web.assets_backend"))
        dark_paths = self._bundle_paths("web.assets_web_dark")
        self.assertIn(DARK_TOKENS, dark_paths)
        # Dark overrides must come after the light tokens so they win the cascade.
        self.assertLess(dark_paths.index(LIGHT_TOKENS), dark_paths.index(DARK_TOKENS))

    def test_bundles_compile_without_css_errors(self):
        for name in ("web.assets_web", "web.assets_web_dark"):
            with self.subTest(bundle=name):
                bundle = self.env["ir.qweb"]._get_asset_bundle(name, css=True, js=False)
                attachment = bundle.css()
                self.assertFalse(bundle.css_errors, "SCSS compile errors: %s" % bundle.css_errors)
                content = attachment.raw.decode() if attachment else ""
                self.assertIn("--fds-action-fill", content)
                self.assertIn("--fds-danger-fill", content)
