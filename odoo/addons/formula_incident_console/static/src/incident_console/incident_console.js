/** @odoo-module **/

// Formula Incident Console (ISMS). Бүх өгөгдөл formula.incident.console-ийн серверийн
// методуудаас ирнэ (хэрэглэгчийн ORM эрхээр). Шилжилтийг isms.incident-ийн action_* методууд
// гүйцэтгэнэ; клиентийн шалгалт нь зөвхөн UX-ийн мэдээлэл юм.

import { Component, onWillStart, onWillUnmount, onMounted, useEffect, useRef, useState } from "@odoo/owl";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const CONSOLE_MODEL = "formula.incident.console";
const INCIDENT_MODEL = "isms.incident";
const TICK_MS = 60 * 1000;
const NOTE_FIELDS = ["containment", "root_cause", "resolution", "lessons_learned", "notification_note"];
const ACCESS_ERROR = "odoo.exceptions.AccessError";
const EMPTY_FILTERS = { state: "", severity: "", overdue: false, mine: false, open: false, unassigned: false, query: "" };
const QUEUES = [
    { key: "all", label: _t("Бүх зөрчил"), icon: "list-ul" },
    { key: "open", label: _t("Шийдвэрлэж буй"), icon: "folder-open-o" },
    { key: "overdue", label: _t("Хугацаа хэтэрсэн"), icon: "clock-o" },
    { key: "unassigned", label: _t("Хариуцагчгүй"), icon: "user-o" },
];

const STATE_OPTIONS = [
    { key: "incident", label: _t("Илэрсэн") },
    { key: "report", label: _t("Бүртгэсэн") },
    { key: "investigate", label: _t("Шалгаж буй") },
    { key: "resolve", label: _t("Шийдвэрлэсэн") },
    { key: "close", label: _t("Хаасан") },
];
const SEVERITY_OPTIONS = [
    { key: "critical", label: _t("Ноцтой") },
    { key: "high", label: _t("Өндөр") },
    { key: "medium", label: _t("Дунд") },
    { key: "low", label: _t("Бага") },
];

function isAccessError(error) {
    return Boolean(error && error.data && error.data.name === ACCESS_ERROR);
}

function errorText(error, fallback) {
    if (error && error.data && error.data.message) {
        return error.data.message;
    }
    return fallback;
}

// Секундийг хүний уншихуйц хугацаа болгоно (минутын нарийвчлалтай).
function formatDuration(totalSeconds) {
    const seconds = Math.max(0, Math.floor(totalSeconds));
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (days > 0) {
        return _t("%s өдөр %s цаг", days, hours);
    }
    if (hours > 0) {
        return _t("%s цаг %s мин", hours, minutes);
    }
    return _t("%s мин", minutes);
}

export class FormulaIncidentConsole extends Component {
    static template = "formula_incident_console.Console";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.stateOptions = STATE_OPTIONS;
        this.severityOptions = SEVERITY_OPTIONS;
        this.drawerTitle = useRef("drawerTitle");
        this.drawerClose = useRef("drawerClose");
        this.listTitle = useRef("listTitle");
        this.state = useState({
            loading: true,
            error: false,
            denied: false,
            rows: [],
            total: 0,
            truncated: false,
            filters: { ...EMPTY_FILTERS },
            search: "",
            summary: null,
            loadedAt: Date.now(),
            now: Date.now(),
            selectedId: null,
            detail: null,
            detailLoading: false,
            detailError: "",
            pendingAction: null,
            saving: false,
            notes: {},
        });
        this.requestSeq = 0;
        this.detailSeq = 0;
        this.timer = null;
        useEffect(
            (selectedId, loading, detail) => {
                if (selectedId === null || this.focusIncident !== selectedId) {
                    return;
                }
                if (loading) {
                    this.drawerClose.el?.focus();
                    return;
                }
                this.focusIncident = null;
                if (detail) {
                    this.drawerTitle.el?.focus();
                }
            },
            () => [this.state.selectedId, this.state.detailLoading, Boolean(this.state.detail)]
        );
        useSetupAction({});
        onWillStart(() => { this.loadList(); });
        // Нэг л interval: SLA-ийн тоолуурыг минут тутам шинэчилнэ. Unmount дээр цэвэрлэнэ.
        onMounted(() => {
            this.timer = setInterval(() => {
                this.state.now = Date.now();
            }, TICK_MS);
        });
        onWillUnmount(() => {
            if (this.timer) {
                clearInterval(this.timer);
                this.timer = null;
            }
        });
    }

    // ------------------------------------------------------------ data loading
    async loadList() {
        const seq = ++this.requestSeq;
        this.state.loading = true;
        this.state.error = false;
        this.state.denied = false;
        try {
            const data = await this.orm.call(CONSOLE_MODEL, "get_incident_rows", [{ ...this.state.filters }]);
            if (seq !== this.requestSeq) {
                return;
            }
            this.state.rows = data.rows;
            this.state.total = data.total;
            this.state.summary = data.summary;
            this.state.truncated = data.truncated;
            this.state.loadedAt = Date.now();
            this.state.now = this.state.loadedAt;
        } catch (error) {
            if (seq !== this.requestSeq) {
                return;
            }
            if (isAccessError(error)) {
                this.state.denied = true;
            } else {
                console.error("Incident Console: инцидентийн жагсаалт ачаалж чадсангүй", error);
                this.state.error = true;
            }
        } finally {
            if (seq === this.requestSeq) {
                this.state.loading = false;
            }
        }
    }

    async openIncident(incidentId, trigger) {
        if (this.isBusy) {
            return;
        }
        if (trigger) {
            this.returnFocus = trigger;
        }
        this.focusIncident = incidentId;
        this.state.selectedId = incidentId;
        this.state.detail = null;
        this.state.detailError = "";
        this.state.detailLoading = true;
        await this.fetchDetail(incidentId);
    }

    async fetchDetail(incidentId) {
        const seq = ++this.detailSeq;
        try {
            const detail = await this.orm.call(CONSOLE_MODEL, "get_incident_detail", [incidentId]);
            if (seq !== this.detailSeq || this.state.selectedId !== incidentId) {
                return null;
            }
            detail.row.loadedAt = Date.now();
            this.state.detail = detail;
            this.syncNotes(detail);
            this.state.detailError = "";
            return detail;
        } catch (error) {
            if (seq === this.detailSeq && this.state.selectedId === incidentId) {
                console.error("Incident Console: дэлгэрэнгүй ачаалж чадсангүй", error);
                this.state.detailError = isAccessError(error) ? "denied" : "error";
            }
            return null;
        } finally {
            if (seq === this.detailSeq && this.state.selectedId === incidentId) {
                this.state.detailLoading = false;
            }
        }
    }

    syncNotes(detail) {
        const investigation = detail.investigation || {};
        const notes = {};
        for (const field of NOTE_FIELDS) {
            notes[field] = investigation[field] || "";
        }
        this.state.notes = notes;
    }

    closeDetail() {
        if (this.isBusy) {
            return;
        }
        this.detailSeq++;
        this.focusIncident = null;
        this.state.selectedId = null;
        this.state.detail = null;
        this.state.detailError = "";
        this.state.detailLoading = false;
        const trigger = this.returnFocus;
        this.returnFocus = null;
        requestAnimationFrame(() => {
            (trigger?.isConnected ? trigger : this.listTitle.el)?.focus();
        });
    }

    onRootKeydown(ev) {
        if (ev.key === "Escape" && this.state.selectedId !== null && !this.isBusy) {
            ev.preventDefault();
            this.closeDetail();
        }
    }

    // ------------------------------------------------------------ filters
    onFilterChange(key, value) {
        this.state.filters[key] = value;
        if (key === "state" && value) {
            Object.assign(this.state.filters, { open: false, overdue: false, unassigned: false });
        }
        this.loadList();
    }

    get hasActiveFilters() {
        const f = this.state.filters;
        return Object.values(f).some(Boolean) || Boolean(this.state.search);
    }

    clearFilters() {
        this.state.filters = { ...EMPTY_FILTERS };
        this.state.search = "";
        this.loadList();
    }

    get queues() {
        return QUEUES.map((queue) => ({ ...queue, count: this.state.summary?.[queue.key] }));
    }

    get currentQueue() {
        const { overdue, unassigned, open } = this.state.filters;
        return overdue ? "overdue" : unassigned ? "unassigned" : open ? "open" : "all";
    }

    selectQueue(key) {
        Object.assign(this.state.filters, { state: "", overdue: key === "overdue", unassigned: key === "unassigned", open: key === "open" });
        this.loadList();
    }

    applySearch(ev) {
        ev.preventDefault();
        if (this.state.loading) {
            return;
        }
        this.state.filters.query = this.state.search.trim();
        this.state.search = this.state.filters.query;
        this.loadList();
    }

    get stageSteps() {
        const current = STATE_OPTIONS.findIndex((step) => step.key === this.state.detail?.row.state);
        return STATE_OPTIONS.map((step, index) => ({
            ...step, current: index === current, done: index < current, number: index + 1,
        }));
    }

    // ------------------------------------------------------------ SLA countdown
    liveRemaining(row) {
        if (row.sla_remaining_seconds === null || row.sla_remaining_seconds === undefined) {
            return null;
        }
        return row.sla_remaining_seconds - Math.max(0, this.state.now - (row.loadedAt || this.state.loadedAt)) / 1000;
    }

    slaLabel(row) {
        const live = this.liveRemaining(row);
        if (live === null) {
            return row.state === "close" || row.state === "resolve" ? _t("SLA хаагдсан") : _t("SLA хугацаа алга");
        }
        if (live < 0) {
            return _t("Хугацаа хэтэрсэн: %s", formatDuration(-live));
        }
        return _t("Үлдсэн: %s", formatDuration(live));
    }

    slaTone(row) {
        const live = this.liveRemaining(row);
        if (live === null) {
            return "neutral";
        }
        if (live < 0) {
            return "danger";
        }
        if (live < 4 * 3600) {
            return "warning";
        }
        return "ok";
    }

    formatTs(value) {
        if (!value) {
            return "—";
        }
        return formatDateTime(deserializeDateTime(value));
    }

    // ------------------------------------------------------------ transitions
    get transitions() {
        return (this.state.detail && this.state.detail.transitions) || [];
    }

    get blockedReasons() {
        return this.transitions.filter((t) => !t.allowed && t.reason);
    }

    async runTransition(action) {
        const detail = this.state.detail;
        if (!detail || this.isBusy) {
            return;
        }
        const incidentId = detail.row.id;
        const fromState = detail.row.state;
        this.state.pendingAction = action;
        try {
            try {
                await this.orm.call(INCIDENT_MODEL, action, [[incidentId]]);
            } catch (error) {
                this.notification.add(
                    errorText(error, _t("Шилжилт амжилтгүй боллоо. Эрх болон шаардлагатай талбараа шалгана уу.")),
                    { type: "danger" }
                );
                await this.refreshAfterChange(incidentId);
                return;
            }
            const refreshed = await this.refreshAfterChange(incidentId);
            if (refreshed && refreshed.row.state !== fromState) {
                this.notification.add(_t("Төлөв шинэчлэгдлээ: %s", refreshed.row.state_label), { type: "success" });
            } else if (refreshed) {
                this.notification.add(_t("Төлөв өөрчлөгдсөнгүй. Өөр хэрэглэгч аль хэдийн шилжүүлсэн байж магадгүй."), {
                    type: "warning",
                });
            }
        } finally {
            this.state.pendingAction = null;
        }
    }

    async refreshAfterChange(incidentId) {
        await this.loadList();
        if (this.state.selectedId !== incidentId) {
            return null;
        }
        return this.fetchDetail(incidentId);
    }

    // ------------------------------------------------------------ investigation notes
    get canSaveNotes() {
        return Boolean(this.state.detail && this.state.detail.can_edit_investigation);
    }

    get impactLabel() {
        const impact = (this.state.detail && this.state.detail.impact) || {};
        const parts = [];
        if (impact.c) {
            parts.push(_t("Нууцлал"));
        }
        if (impact.i) {
            parts.push(_t("Бүрэн бүтэн байдал"));
        }
        if (impact.a) {
            parts.push(_t("Хүртээмж"));
        }
        return parts.length ? parts.join(", ") : _t("тодорхойлоогүй");
    }

    get noteDirty() {
        const investigation = (this.state.detail && this.state.detail.investigation) || {};
        return NOTE_FIELDS.some((field) => (this.state.notes[field] || "") !== (investigation[field] || ""));
    }

    async saveNotes() {
        const detail = this.state.detail;
        if (!detail || this.state.saving || this.state.pendingAction || !this.canSaveNotes) {
            return;
        }
        const investigation = detail.investigation || {};
        const values = {};
        for (const field of NOTE_FIELDS) {
            const value = this.state.notes[field] || "";
            if (value !== (investigation[field] || "")) {
                values[field] = value;
            }
        }
        if (!Object.keys(values).length) {
            this.notification.add(_t("Өөрчлөлт алга."), { type: "info" });
            return;
        }
        this.state.saving = true;
        try {
            const updated = await this.orm.call(CONSOLE_MODEL, "save_investigation", [detail.row.id, values]);
            if (this.state.selectedId === detail.row.id) {
                updated.row.loadedAt = Date.now();
                this.state.detail = updated;
                this.syncNotes(updated);
            }
            this.notification.add(_t("Шалгалтын тэмдэглэл хадгалагдлаа."), { type: "success" });
        } catch (error) {
            this.notification.add(errorText(error, _t("Хадгалах боломжгүй байна.")), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    // ------------------------------------------------------------ helpers
    openTicket(ticket) {
        if (!ticket) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: ticket.name,
            res_model: "helpdesk.ticket",
            res_id: ticket.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    get isBusy() {
        return Boolean(this.state.pendingAction || this.state.saving);
    }
}

registry.category("actions").add("formula_incident_console", FormulaIncidentConsole);
