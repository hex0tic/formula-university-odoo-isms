// Formula Design System: light/dark theme toggle in the systray.
//
// Odoo 18 Community chooses the stylesheet bundle on the server: when the
// "color_scheme" cookie equals "dark" it serves web.assets_web_dark instead of
// web.assets_web (see web/views/webclient_templates.xml). The toggle therefore
// stores the choice in that cookie and reloads the page. The cookie is per
// browser (one year), not per user account; it survives reloads.

import { Component, useState } from "@odoo/owl";
import { cookie } from "@web/core/browser/cookie";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const COOKIE_NAME = "color_scheme";

export function readThemeCookie() {
    try {
        return cookie.get(COOKIE_NAME) === "dark" ? "dark" : "light";
    } catch {
        return "light";
    }
}

export class FdsThemeToggle extends Component {
    static template = "formula_design_system.ThemeToggle";
    static props = {};

    setup() {
        this.state = useState({ theme: readThemeCookie() });
    }

    get isDark() {
        return this.state.theme === "dark";
    }

    get label() {
        return this.isDark ? _t("Цайвар горим руу шилжих") : _t("Бараан горим руу шилжих");
    }

    onToggle() {
        const next = this.isDark ? "light" : "dark";
        cookie.set(COOKIE_NAME, next);
        this.state.theme = next;
        // The stylesheet bundle is selected by the server, so a reload applies it.
        window.location.reload();
    }
}

export const fdsThemeToggleItem = {
    Component: FdsThemeToggle,
};

registry.category("systray").add("formula_design_system.theme_toggle", fdsThemeToggleItem, {
    sequence: 2,
});
