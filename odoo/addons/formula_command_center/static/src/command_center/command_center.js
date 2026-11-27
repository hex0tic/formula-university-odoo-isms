/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const MODEL = "formula.command.center";
const LIKELIHOOD_ROWS = ["5", "4", "3", "2", "1"];
const IMPACT_COLS = ["1", "2", "3", "4", "5"];
const LEVEL_LABELS = { low: _t("Бага"), medium: _t("Дунд"), high: _t("Өндөр") };
const PERIOD_OPTIONS = [
    { value: 0, label: _t("Бүх хугацаа") },
    { value: 30, label: _t("Сүүлийн 30 хоног") },
    { value: 90, label: _t("Сүүлийн 90 хоног") },
    { value: 365, label: _t("Сүүлийн 365 хоног") },
];
const DENIED = _t("Энэ хэсгийг харах эрх байхгүй.");
const PRIMARY_CARDS = [
    ["incidents_open", "bell", _t("Шийдвэрлэх шатанд байгаа")],
    ["risks_total", "crosshairs", _t("Эрсдэлийн бүртгэл")],
    ["controls_implemented", "shield", _t("Хэрэгжсэн хяналт")],
    ["assets_total", "cubes", _t("Мэдээллийн хөрөнгийн бүртгэл")],
];
const PRIORITIES = [
    ["incidents_sla_overdue", "clock-o", _t("Зөрчлийн хариу өгөх хугацаа хэтэрсэн")],
    ["risks_high", "exclamation-triangle", _t("Өндөр түвшний анхдагч эрсдэл")],
    ["treatment_overdue", "tasks", _t("Эрсдэлийн арга хэмжээ хоцорсон")],
    ["policies_review_overdue", "file-text-o", _t("Бодлого дахин хянах хугацаа хэтэрсэн")],
];

export class FormulaCommandCenter extends Component {
    static template = "formula_command_center.Dashboard";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.periodOptions = PERIOD_OPTIONS;
        this.denied = DENIED;
        this.state = useState({
            loading: true,
            error: false,
            data: null,
            mode: "residual",
            incidentDays: 0,
        });
        useSetupAction({});
        onWillStart(() => { this.load(); });
    }

    async load() {
        if (this._requestInFlight) {
            return;
        }
        this._requestInFlight = true;
        this.state.loading = true;
        this.state.error = false;
        try {
            this.state.data = await this.orm.call(MODEL, "get_dashboard_data", [
                { incident_days: this.state.incidentDays },
            ]);
        } catch (error) {
            console.error("Command Center: dashboard data could not be loaded", error);
            this.state.error = true;
        } finally {
            this.state.loading = false;
            this._requestInFlight = false;
        }
    }

    // ------------------------------------------------------------ getters
    get sections() {
        return (this.state.data && this.state.data.sections) || {};
    }

    get kpis() {
        return (this.state.data && this.state.data.kpis) || [];
    }

    get primaryKpis() {
        const cards = new Map(this.kpis.map((card) => [card.key, card]));
        return PRIMARY_CARDS.flatMap(([key, icon, hint]) => {
            const card = cards.get(key);
            return card?.available ? [{ ...card, icon, hint }] : [];
        });
    }

    get secondaryKpis() {
        const primary = new Set(PRIMARY_CARDS.map(([key]) => key));
        return this.kpis.filter((card) => card.available && !primary.has(card.key));
    }

    get priorities() {
        const cards = new Map(this.kpis.map((card) => [card.key, card]));
        return PRIORITIES.flatMap(([key, icon, title]) => {
            const card = cards.get(key);
            return card?.available ? [{ ...card, icon, title }] : [];
        });
    }

    get trend() {
        return this.sections.incident_trend || { available: false };
    }

    get trendWeeks() {
        if (!this.trend.available) {
            return [];
        }
        const peak = Math.max(1, ...this.trend.weeks.map((week) => week.count));
        return this.trend.weeks.map((week, index) => ({
            ...week,
            current: index === this.trend.weeks.length - 1,
            height: Math.round(week.count * 100 / peak),
            ariaLabel: _t("%s: %s зөрчил", week.start, week.count),
        }));
    }

    get generatedAt() {
        return this.state.data ? this.formatTs(this.state.data.generated_at) : "";
    }

    get heatAvailable() {
        return Boolean(this.sections.heatmap && this.sections.heatmap.available);
    }

    get heatData() {
        return this.heatAvailable ? this.sections.heatmap[this.state.mode] : null;
    }

    get heatTotal() {
        return this.heatData ? this.heatData.total : 0;
    }

    get heatRows() {
        const data = this.heatData;
        if (!data) {
            return [];
        }
        const byKey = {};
        for (const cell of data.cells) {
            byKey[`${cell.likelihood}-${cell.impact}`] = cell;
        }
        return LIKELIHOOD_ROWS.map((likelihood) => ({
            likelihood,
            cells: IMPACT_COLS.map((impact) => {
                const cell = byKey[`${likelihood}-${impact}`];
                const levelLabel = LEVEL_LABELS[cell.level] || "";
                return {
                    key: `${likelihood}-${impact}`,
                    likelihood,
                    impact,
                    level: cell.level || "none",
                    count: cell.count,
                    drill: cell.drill,
                    ariaLabel: _t(
                        "Магадлал %s, нөлөөлөл %s, оноо %s: %s эрсдэл, түвшин: %s",
                        likelihood,
                        impact,
                        cell.score,
                        cell.count,
                        levelLabel
                    ),
                };
            }),
        }));
    }

    get controls() {
        return this.sections.controls || { available: false };
    }

    get implementationRows() {
        const controls = this.controls;
        if (!controls.available) {
            return [];
        }
        const base = controls.selected || 0;
        return controls.by_implementation.map((row) => ({
            ...row,
            pct: base ? Math.round((row.count * 100) / base) : 0,
        }));
    }

    get incidents() {
        return this.sections.incidents || { available: false };
    }

    get assets() {
        return this.sections.assets || { available: false };
    }

    get risks() {
        return this.sections.risks || { available: false };
    }

    get audit() {
        return this.sections.audit || { available: false };
    }

    get treatment() {
        return this.sections.treatment || { available: false };
    }

    get hasAnyData() {
        return Boolean(this.state.data);
    }

    levelLabel(level) {
        return LEVEL_LABELS[level] || level;
    }

    formatTs(value) {
        if (!value) {
            return "";
        }
        return formatDateTime(deserializeDateTime(value));
    }

    // ------------------------------------------------------------ actions
    setMode(mode) {
        this.state.mode = mode === "inherent" ? "inherent" : "residual";
    }

    onPeriodChange(ev) {
        const days = parseInt(ev.target.value, 10);
        this.state.incidentDays = Number.isNaN(days) ? 0 : days;
        this.load();
    }

    openDrill(drill) {
        if (!drill) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: drill.name,
            res_model: drill.model,
            domain: drill.domain,
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    }
}

registry.category("actions").add("formula_command_center", FormulaCommandCenter);
