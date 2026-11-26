/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const SERVICE = "campus.portal.teacher";
const REASON_MIN = 10;
const FALLBACK_ERROR = _t("Сервер хүсэлтийг боловсруулж чадсангүй. Дахин оролдоно уу.");
const ATTENDANCE_LABELS = {
    present: "Ирсэн",
    late: "Хоцорсон",
    absent: "Таслах",
    excused: "Чөлөөтэй",
};

function errorMessage(error) {
    return (error && error.data && error.data.message) || (error && error.message) || FALLBACK_ERROR;
}

export class CampusTeacherPortal extends Component {
    static template = "campus_portal.TeacherPortal";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            tab: "offerings",
            loading: true,
            loadError: false,
            dashboard: null,
            offeringId: null,
            rosterLoading: false,
            rosterError: false,
            roster: null,
            sessionsLoading: false,
            sessionsError: false,
            sessions: [],
            attendance: {},
            drafts: {},
            notificationsLoading: false,
            notificationsError: false,
            notifications: [],
            busy: {},
        });
        useSetupAction({});
        onWillStart(() => this.loadDashboard());
    }

    // ------------------------------------------------------------ busy guard
    // Every write goes through run(): a key that is already in flight is ignored, which stops double clicks.
    async run(key, action) {
        if (this.state.busy[key]) {
            return false;
        }
        this.state.busy[key] = true;
        try {
            await action();
            return true;
        } catch (error) {
            console.error("Teacher portal: server rejected the request", error);
            this.notification.add(errorMessage(error), { type: "danger", sticky: true });
            return false;
        } finally {
            this.state.busy[key] = false;
        }
    }

    isBusy(key) {
        return Boolean(this.state.busy[key]);
    }

    // ------------------------------------------------------------ dashboard and tabs
    async loadDashboard() {
        this.state.loading = true;
        this.state.loadError = false;
        try {
            this.state.dashboard = await this.orm.call(SERVICE, "get_dashboard", []);
        } catch (error) {
            console.error("Teacher portal: dashboard could not be loaded", error);
            this.state.loadError = errorMessage(error);
        } finally {
            this.state.loading = false;
        }
    }

    setTab(tab) {
        if (this.state.tab === tab) {
            return;
        }
        this.state.tab = tab;
        if (tab === "notifications") {
            this.loadNotifications();
        }
    }

    // ------------------------------------------------------------ roster and attendance
    async openOffering(offeringId) {
        this.state.tab = "offering";
        this.state.offeringId = offeringId;
        this.state.drafts = {};
        await Promise.all([this.loadRoster(offeringId), this.loadSessions(offeringId)]);
    }

    backToOfferings() {
        this.state.tab = "offerings";
        this.state.offeringId = null;
        this.state.roster = null;
        this.state.sessions = [];
        this.state.attendance = {};
        this.state.drafts = {};
    }

    async loadRoster(offeringId) {
        this.state.rosterLoading = true;
        this.state.rosterError = false;
        try {
            this.state.roster = await this.orm.call(SERVICE, "get_roster", [offeringId]);
        } catch (error) {
            console.error("Teacher portal: roster could not be loaded", error);
            this.state.roster = null;
            this.state.rosterError = errorMessage(error);
        } finally {
            this.state.rosterLoading = false;
        }
    }

    async loadSessions(offeringId) {
        this.state.sessionsLoading = true;
        this.state.sessionsError = false;
        try {
            const data = await this.orm.call(SERVICE, "get_sessions", [offeringId]);
            this.state.sessions = data.sessions;
            const attendance = {};
            for (const session of data.sessions) {
                attendance[session.id] = {};
                for (const row of session.rows) {
                    attendance[session.id][row.enrollment_id] = row.status;
                }
            }
            this.state.attendance = attendance;
        } catch (error) {
            console.error("Teacher portal: sessions could not be loaded", error);
            this.state.sessions = [];
            this.state.sessionsError = errorMessage(error);
        } finally {
            this.state.sessionsLoading = false;
        }
    }

    setAttendance(sessionId, enrollmentId, status) {
        if (!ATTENDANCE_LABELS[status]) {
            return;
        }
        this.state.attendance[sessionId][enrollmentId] = status;
    }

    attendanceLabel(status) {
        return ATTENDANCE_LABELS[status] || status;
    }

    saveAttendance(session) {
        const key = `attendance-${session.id}`;
        const values = this.state.attendance[session.id] || {};
        const rows = session.rows.map((row) => ({
            enrollment_id: row.enrollment_id,
            status: values[row.enrollment_id] || "present",
        }));
        return this.run(key, async () => {
            await this.orm.call(SERVICE, "save_attendance", [session.id, rows]);
            this.notification.add(_t("Ирцийг хадгаллаа."), { type: "success" });
            await this.loadSessions(this.state.offeringId);
        });
    }

    // ------------------------------------------------------------ grade requests
    startRequest(row) {
        this.state.drafts[row.enrollment_id] = {
            open: true,
            score: row.score,
            reason: "",
            evidence: "",
            error: "",
        };
    }

    cancelRequest(row) {
        delete this.state.drafts[row.enrollment_id];
    }

    isDraftOpen(enrollmentId) {
        return Boolean(this.state.drafts[enrollmentId]);
    }

    submitRequest(row) {
        const draft = this.state.drafts[row.enrollment_id];
        if (!draft || draft.pending || this.isBusy(`grade-${row.enrollment_id}`)) {
            return;
        }
        const score = Number(draft.score);
        if (draft.score === "" || Number.isNaN(score) || score < 0 || score > 100) {
            draft.error = _t("Шинэ дүн 0–100 хооронд байна.");
            return;
        }
        if (score === Number(row.score)) {
            draft.error = _t("Шинэ дүн одоогийн дүнгээс ялгаатай байх ёстой.");
            return;
        }
        if ((draft.reason || "").trim().length < REASON_MIN) {
            draft.error = _t("Үндэслэлийг %s-аас доошгүй тэмдэгтээр бичнэ үү.", REASON_MIN);
            return;
        }
        draft.error = "";
        // Set before the dialog opens so a double click cannot open two confirmations.
        draft.pending = true;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Дүн өөрчлөх хүсэлтийг илгээх үү?"),
            body: _t("%s-ийн дүн %s-аас %s болох хүсэлт сургалтын албанд хянуулахаар илгээгдэнэ. Хүсэлтийг илгээсний дараа засах боломжгүй.",
                row.student_name, String(row.score), String(score)),
            confirmLabel: _t("Илгээх"),
            cancelLabel: _t("Болих"),
            confirm: () => this.sendRequest(row, score, draft),
            cancel: () => {
                draft.pending = false;
            },
        });
    }

    sendRequest(row, score, draft) {
        return this.run(`grade-${row.enrollment_id}`, async () => {
            draft.pending = false;
            await this.orm.call(SERVICE, "request_grade_change", [
                row.enrollment_id, score, draft.reason.trim(), (draft.evidence || "").trim(),
            ]);
            delete this.state.drafts[row.enrollment_id];
            this.notification.add(_t("Хүсэлтийг хянуулахаар илгээлээ."), { type: "success" });
            await this.loadRoster(this.state.offeringId);
            await this.loadDashboard();
        });
    }

    // ------------------------------------------------------------ notifications
    async loadNotifications() {
        this.state.notificationsLoading = true;
        this.state.notificationsError = false;
        try {
            this.state.notifications = await this.orm.call(SERVICE, "get_notifications", []);
        } catch (error) {
            console.error("Teacher portal: notifications could not be loaded", error);
            this.state.notificationsError = errorMessage(error);
        } finally {
            this.state.notificationsLoading = false;
        }
    }

    // ------------------------------------------------------------ getters
    get offerings() {
        return (this.state.dashboard && this.state.dashboard.offerings) || [];
    }

    get pendingCount() {
        return (this.state.dashboard && this.state.dashboard.pending_count) || 0;
    }

    get termName() {
        const term = this.state.dashboard && this.state.dashboard.term;
        return term ? term.name : _t("Нээлттэй улирал алга");
    }
}

registry.category("actions").add("campus_portal_teacher", CampusTeacherPortal);
