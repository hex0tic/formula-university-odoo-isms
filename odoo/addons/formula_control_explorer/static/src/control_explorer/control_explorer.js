/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { deserializeDate, formatDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const MODEL = "formula.control.explorer";
const SEARCH_DELAY_MS = 250;
const TABS = [
    { key: "soa", label: _t("SoA") },
    { key: "links", label: _t("Холбоос") },
    { key: "evidence", label: _t("Нотолгоо") },
    { key: "findings", label: _t("Дүгнэлт") },
];
const SELECTED_OPTIONS = [
    { value: "all", label: _t("Бүгд") },
    { value: "yes", label: _t("Сонгосон") },
    { value: "no", label: _t("Сонгоогүй") },
];
const APPLICABLE_OPTIONS = [
    { value: "all", label: _t("Бүгд") },
    { value: "yes", label: _t("Хамааралтай") },
    { value: "no", label: _t("Хамааралгүй") },
];
const IMPLEMENTATION_OPTIONS = [
    { value: "all", label: _t("Бүгд") },
    { value: "yes", label: _t("Тийм") },
    { value: "partial", label: _t("Хэсэгчилсэн") },
    { value: "no", label: _t("Үгүй") },
];
const FINDING_STATUS = {
    gap: { label: _t("Саад"), tone: "danger" },
    ok: { label: _t("Зөв"), tone: "success" },
    na: { label: _t("Хамаарахгүй"), tone: "neutral" },
    not_evaluated: { label: _t("Шалгах боломжгүй"), tone: "muted" },
};
const DEFAULT_FILTERS = {
    theme: "",
    selected: "all",
    applicable: "all",
    implementation: "all",
    new_2022: false,
    owner_id: 0,
    search: "",
};

export class FormulaControlExplorer extends Component {
    static template = "formula_control_explorer.Explorer";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.tbodyRef = useRef("tbody");
        this.drawerRef = useRef("drawer");
        this.tablistRef = useRef("tablist");
        this.catalogToken = 0;
        this.detailToken = 0;
        this.searchTimer = null;
        this.returnFocus = null;
        this.tabs = TABS;
        this.selectedOptions = SELECTED_OPTIONS;
        this.applicableOptions = APPLICABLE_OPTIONS;
        this.implementationOptions = IMPLEMENTATION_OPTIONS;
        this.state = useState({
            loading: true,
            error: false,
            data: null,
            filters: { ...DEFAULT_FILTERS },
            activeIndex: 0,
            drawerOpen: false,
            selectedId: null,
            detailLoading: false,
            detailError: false,
            detail: null,
            tab: "soa",
        });
        useSetupAction({});
        onWillStart(() => this.load());
        onWillUnmount(() => {
            clearTimeout(this.searchTimer);
        });
    }

    // ------------------------------------------------------------ data loading
    async load() {
        const token = ++this.catalogToken;
        this.state.loading = true;
        this.state.error = false;
        try {
            const data = await this.orm.call(MODEL, "get_catalog", [{ ...this.state.filters }]);
            if (token !== this.catalogToken) {
                return;
            }
            this.state.data = data;
            const last = Math.max(0, data.items.length - 1);
            this.state.activeIndex = Math.min(this.state.activeIndex, last);
        } catch (error) {
            if (token !== this.catalogToken) {
                return;
            }
            console.error("Control Explorer: catalog could not be loaded", error);
            this.state.error = true;
        } finally {
            if (token === this.catalogToken) {
                this.state.loading = false;
            }
        }
    }

    async loadDetail(controlId) {
        const token = ++this.detailToken;
        this.state.detailLoading = true;
        this.state.detailError = false;
        this.state.detail = null;
        try {
            const detail = await this.orm.call(MODEL, "get_control_detail", [controlId]);
            if (token !== this.detailToken) {
                return;
            }
            this.state.detail = detail;
        } catch (error) {
            if (token !== this.detailToken) {
                return;
            }
            console.error("Control Explorer: control detail could not be loaded", error);
            this.state.detailError = true;
        } finally {
            if (token === this.detailToken) {
                this.state.detailLoading = false;
            }
        }
    }

    // ------------------------------------------------------------ getters
    get data() {
        return this.state.data;
    }

    get items() {
        return (this.state.data && this.state.data.items) || [];
    }

    get summary() {
        return (this.state.data && this.state.data.summary) || null;
    }

    get options() {
        return (this.state.data && this.state.data.options) || { owners: [], themes: [] };
    }

    get hasFilters() {
        const f = this.state.filters;
        return Boolean(
            f.theme ||
                f.selected !== "all" ||
                f.applicable !== "all" ||
                f.implementation !== "all" ||
                f.new_2022 ||
                f.owner_id ||
                f.search
        );
    }

    get implementedCount() {
        if (!this.summary) {
            return 0;
        }
        const row = this.summary.by_implementation.find((r) => r.key === "yes");
        return row ? row.count : 0;
    }

    get detail() {
        return this.state.detail;
    }

    get detailAvailable() {
        return Boolean(this.detail && this.detail.available);
    }

    get tabList() {
        return this.tabs;
    }

    get findingStatusLabels() {
        return FINDING_STATUS;
    }

    get linkSections() {
        if (!this.detailAvailable) {
            return [];
        }
        const links = this.detail.links;
        return [links.risks, links.assets, links.policies, links.incidents];
    }

    get findingsSummary() {
        return (this.detail && this.detail.findings_summary) || {};
    }

    get selectedItem() {
        return this.items.find((item) => item.id === this.state.selectedId) || null;
    }

    // ------------------------------------------------------------ formatting
    formatDateValue(value) {
        if (!value) {
            return "";
        }
        return formatDate(deserializeDate(value));
    }

    findingTone(status) {
        return (FINDING_STATUS[status] && FINDING_STATUS[status].tone) || "neutral";
    }

    findingLabel(status) {
        return (FINDING_STATUS[status] && FINDING_STATUS[status].label) || status;
    }

    implementationTone(impl, selected) {
        if (impl === "yes") {
            return "success";
        }
        if (impl === "partial") {
            return "warning";
        }
        return selected ? "danger" : "neutral";
    }

    // ------------------------------------------------------------ filters
    onSearchInput(ev) {
        this.state.filters.search = ev.target.value;
        clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(() => this.load(), SEARCH_DELAY_MS);
    }

    onSearchKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            clearTimeout(this.searchTimer);
            this.load();
        }
    }

    onFilterChange(key, ev) {
        const raw = ev.target.value;
        this.state.filters[key] = key === "owner_id" ? parseInt(raw, 10) || 0 : raw;
        this.load();
    }

    onNewToggle(ev) {
        this.state.filters.new_2022 = ev.target.checked;
        this.load();
    }

    selectTheme(key) {
        this.state.filters.theme = key;
        this.state.activeIndex = 0;
        this.load();
    }

    resetFilters() {
        clearTimeout(this.searchTimer);
        this.state.filters = { ...DEFAULT_FILTERS };
        this.state.activeIndex = 0;
        this.load();
    }

    // ------------------------------------------------------------ table keyboard
    onRowKeydown(ev, index) {
        const count = this.items.length;
        if (!count) {
            return;
        }
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const step = ev.key === "ArrowDown" ? 1 : -1;
            this.moveTo(Math.min(count - 1, Math.max(0, index + step)));
        } else if (ev.key === "Home") {
            ev.preventDefault();
            this.moveTo(0);
        } else if (ev.key === "End") {
            ev.preventDefault();
            this.moveTo(count - 1);
        } else if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.openDetail(this.items[index], ev.currentTarget);
        }
    }

    onRowFocus(index) {
        this.state.activeIndex = index;
    }

    moveTo(index) {
        this.state.activeIndex = index;
        const rows = this.tbodyRef.el ? this.tbodyRef.el.querySelectorAll("tr[data-row]") : [];
        if (rows[index]) {
            rows[index].focus();
        }
    }

    // ------------------------------------------------------------ drawer
    openDetail(item, trigger) {
        if (!item) {
            return;
        }
        this.returnFocus = trigger || document.activeElement;
        this.state.selectedId = item.id;
        this.state.drawerOpen = true;
        this.state.tab = "soa";
        this.loadDetail(item.id);
        setTimeout(() => {
            if (this.drawerRef.el) {
                this.drawerRef.el.focus();
            }
        });
    }

    closeDetail() {
        this.state.drawerOpen = false;
        this.detailToken++;
        this.state.detailLoading = false;
        const target = this.returnFocus;
        this.returnFocus = null;
        if (target && typeof target.focus === "function") {
            setTimeout(() => target.focus());
        }
    }

    retryDetail() {
        if (this.state.selectedId) {
            this.loadDetail(this.state.selectedId);
        }
    }

    onDrawerKeydown(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            this.closeDetail();
        }
    }

    selectTab(key) {
        this.state.tab = key;
        setTimeout(() => {
            const button = this.tablistRef.el
                ? this.tablistRef.el.querySelector(`[data-tab="${key}"]`)
                : null;
            if (button) {
                button.focus();
            }
        });
    }

    onTabKeydown(ev, index) {
        const count = this.tabs.length;
        let next = null;
        if (ev.key === "ArrowRight") {
            next = (index + 1) % count;
        } else if (ev.key === "ArrowLeft") {
            next = (index - 1 + count) % count;
        } else if (ev.key === "Home") {
            next = 0;
        } else if (ev.key === "End") {
            next = count - 1;
        }
        if (next !== null) {
            ev.preventDefault();
            this.selectTab(this.tabs[next].key);
        }
    }

    // ------------------------------------------------------------ open in standard views
    openForm() {
        if (!this.detailAvailable) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: this.detail.control.code,
            res_model: "isms.control",
            res_id: this.detail.control.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openRecord(ref) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: ref.code || ref.name,
            res_model: ref.model,
            res_id: ref.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openSectionList(section) {
        if (!section || !section.count) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: section.label,
            res_model: section.model,
            domain: [["id", "in", section.ids]],
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    }
}

registry.category("actions").add("formula_control_explorer", FormulaControlExplorer);
