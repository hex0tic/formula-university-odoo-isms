/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { GradeDecisionDialog } from "./decision_dialog";

const STUDIO = "formula.grade.studio";
const GRADE_CHANGE = "campus.grade.change";
const METHODS = { submit: "action_submit", approve: "action_approve", reject: "action_reject" };
const LIST_LIMIT = 200;
const FALLBACK_ERROR = _t("Сервер хүсэлтийг боловсруулж чадсангүй. Дахин оролдоно уу.");

function errorMessage(error) {
    return (error && error.data && error.data.message) || (error && error.message) || FALLBACK_ERROR;
}

export class FormulaGradeStudio extends Component {
    static template = "formula_grade_studio.Studio";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.filters = [
            { key: "pending", label: _t("Хүлээж буй") },
            { key: "mine", label: _t("Миний хүсэлт") },
            { key: "stale", label: _t("Хуучирсан") },
            { key: "all", label: _t("Бүгд") },
        ];
        this.state = useState({
            filter: "pending",
            loading: true,
            queueError: false,
            accessDenied: false,
            items: [],
            counts: { pending: 0, mine: 0, stale: 0, all: 0 },
            truncated: false,
            selectedId: null,
            detail: null,
            detailLoading: false,
            detailError: false,
            busy: false,
        });
        this.requestToken = 0;
        this.detailToken = 0;
        useSetupAction({});
        onWillStart(() => this.loadQueue());
    }

    // ------------------------------------------------------------ loading
    async loadQueue() {
        this.state.loading = true;
        this.state.queueError = false;
        try {
            const result = await this.orm.call(STUDIO, "get_queue", [{ filter: this.state.filter, limit: LIST_LIMIT }]);
            this.state.accessDenied = Boolean(result.access_denied);
            this.state.items = result.items || [];
            this.state.counts = result.counts || this.state.counts;
            this.state.truncated = Boolean(result.truncated);
            const selected = this.state.selectedId;
            const stillListed = this.state.items.some((item) => item.id === selected);
            if (stillListed) {
                await this.selectRequest(selected);
            } else if (this.state.items.length) {
                await this.selectRequest(this.state.items[0].id);
            } else {
                this.clearDetail();
            }
        } catch (error) {
            console.error("Grade studio: queue could not be loaded", error);
            this.state.queueError = true;
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        await this.loadQueue();
    }

    async setFilter(key) {
        if (this.state.filter === key) {
            return;
        }
        this.state.filter = key;
        this.state.selectedId = null;
        await this.loadQueue();
    }

    async selectRequest(id) {
        const token = ++this.detailToken;
        this.state.selectedId = id;
        this.state.detailLoading = true;
        this.state.detailError = false;
        try {
            const detail = await this.orm.call(STUDIO, "get_request", [id]);
            if (token === this.detailToken) {
                this.state.detail = detail;
            }
        } catch (error) {
            console.error("Grade studio: request could not be loaded", error);
            if (token === this.detailToken) {
                this.state.detail = null;
                this.state.detailError = errorMessage(error);
            }
        } finally {
            if (token === this.detailToken) {
                this.state.detailLoading = false;
            }
        }
    }

    clearDetail() {
        this.detailToken++;
        this.state.selectedId = null;
        this.state.detail = null;
        this.state.detailError = false;
    }

    // ------------------------------------------------------------ decisions
    confirmDecision(kind) {
        const detail = this.state.detail;
        if (!detail || this.state.busy || !detail.actions[kind].allowed) {
            return;
        }
        const id = detail.id;
        const student = detail.student.name;
        if (kind === "reject") {
            this.dialog.add(GradeDecisionDialog, {
                title: _t("Хүсэлтийг татгалзах уу?"),
                body: _t("%s-ийн дүнгийн хүсэлт татгалзагдана. Дүн өөрчлөгдөхгүй.", student),
                confirmLabel: _t("Татгалзах"),
                onConfirm: (note) => this.runDecision(id, kind, note),
            });
            return;
        }
        const body = kind === "approve"
            ? _t("%s-ийн дүн %s-ээс %s болно. Баталсны дараа хувилбар нэмэгдэж, ISMS аудитын бүртгэлд орно.",
                student, String(detail.old_score), String(detail.proposed_score))
            : _t("Хүсэлтийг хянуулахаар илгээнэ. Илгээсний дараа засах боломжгүй.");
        this.dialog.add(ConfirmationDialog, {
            title: kind === "approve" ? _t("Дүнг батлах уу?") : _t("Хүсэлтийг илгээх үү?"),
            body,
            confirmLabel: kind === "approve" ? _t("Батлах") : _t("Илгээх"),
            confirmClass: kind === "approve" ? "btn-primary" : "btn-secondary",
            cancelLabel: _t("Болих"),
            confirm: () => this.runDecision(id, kind),
            cancel: () => {},
        });
    }

    async runDecision(id, kind, note) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            if (kind === "reject") {
                // Note and rejection run in one server transaction, so a failed reject leaves no note behind.
                await this.orm.call(STUDIO, "reject_with_note", [id, note]);
            } else {
                await this.orm.call(GRADE_CHANGE, METHODS[kind], [[id]]);
            }
            this.notification.add(this.successMessage(kind), { type: "success" });
        } catch (error) {
            console.error("Grade studio: decision was rejected by the server", error);
            this.notification.add(errorMessage(error), { type: "danger", sticky: true });
        } finally {
            this.state.busy = false;
            await this.refresh();
        }
    }

    successMessage(kind) {
        const messages = {
            submit: _t("Хүсэлтийг хянуулахаар илгээлээ."),
            approve: _t("Хүсэлтийг баталлаа. Дүн шинэчлэгдлээ."),
            reject: _t("Хүсэлтийг татгалзлаа."),
        };
        return messages[kind];
    }

    // ------------------------------------------------------------ getters
    get counterLabels() {
        return this.filters.map((f) => ({ ...f, count: this.state.counts[f.key] || 0 }));
    }

    get deltaLabel() {
        const detail = this.state.detail;
        if (!detail) {
            return "";
        }
        const delta = detail.delta;
        const sign = delta > 0 ? "+" : "";
        return `${sign}${delta.toFixed(2)}`;
    }

    get staleReasonLabels() {
        const detail = this.state.detail;
        if (!detail) {
            return [];
        }
        const labels = {
            revision: _t("баталгаат дүнгийн хувилбар өөрчлөгдсөн"),
            score: _t("баталгаат дүн өөрчлөгдсөн"),
            unreadable: _t("баталгаат бүртгэлийг таны эрхээр унших боломжгүй"),
        };
        return detail.stale_reasons.map((reason) => labels[reason] || reason);
    }

    formatDate(value) {
        if (!value) {
            return _t("Байхгүй");
        }
        return formatDateTime(deserializeDateTime(value));
    }

    get historyEntries() {
        return (this.state.detail && this.state.detail.history) || [];
    }

    get ismsEntries() {
        return (this.state.detail && this.state.detail.isms && this.state.detail.isms.entries) || [];
    }

    get ismsVisible() {
        return Boolean(this.state.detail && this.state.detail.isms && this.state.detail.isms.visible);
    }

    get noItemsMessage() {
        const messages = {
            pending: _t("Хянуулахаар хүлээж буй хүсэлт алга."),
            mine: _t("Таны гаргасан хүсэлт алга."),
            stale: _t("Хуучирсан хүсэлт алга."),
            all: _t("Харагдах хүсэлт алга."),
        };
        return messages[this.state.filter];
    }
}

registry.category("actions").add("formula_grade_studio", FormulaGradeStudio);
