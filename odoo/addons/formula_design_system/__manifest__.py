# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
{
    "name": "Formula Design System",
    "summary": "Design tokens, backend restyling and light/dark theme toggle for Formula ERP",
    "version": "18.0.1.0.0",
    "category": "Themes/Backend",
    "author": "Formula5 баг (ШУТИС МХТС)",
    "license": "LGPL-3",
    "depends": ["web"],
    "installable": True,
    "application": False,
    "auto_install": False,
    "assets": {
        "web.assets_backend": [
            # Light tokens are always loaded; dark overrides only ship with web.assets_web_dark.
            "formula_design_system/static/src/scss/fds_tokens.scss",
            "formula_design_system/static/src/scss/fds_base.scss",
            "formula_design_system/static/src/scss/fds_components.scss",
            "formula_design_system/static/src/js/theme_toggle.js",
            "formula_design_system/static/src/xml/theme_toggle.xml",
        ],
        # Odoo 18 CE selects this bundle server-side when the color_scheme cookie is "dark"
        # (see web/views/webclient_templates.xml). It includes web.assets_web and therefore
        # web.assets_backend, so the dark token overrides are appended after the light ones.
        "web.assets_web_dark": [
            "formula_design_system/static/src/scss/fds_tokens.dark.scss",
            "formula_design_system/static/src/scss/fds_dark_surfaces.scss",
        ],
    },
}
