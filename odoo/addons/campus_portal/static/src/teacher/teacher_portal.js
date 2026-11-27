/** @odoo-module **/

import { Component, onPatched, onWillStart, useRef, useState } from "@odoo/owl";
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
        this.portal = useRef("portal");
        this.offeringView = null;
        this.focusAfterPatch = null;
        this.state = useState({
            tab: "offerings",
            loading: true,
            loadError: false,
            wrongAccount: false,
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
        onPatched(() => {
            if (this.focusAfterPatch) {
                this.focusSection(this.focusAfterPatch);
                this.focusAfterPatch = null;
            }
        });
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

    // ------------------------------------------------------------ dashboard and navigation
    async loadDashboard() {
        this.state.loading = true;
        this.state.loadError = false;
        this.state.wrongAccount = false;
        try {
            this.state.dashboard = await this.orm.call(SERVICE, "get_dashboard", []);
        } catch (error) {
            this.state.wrongAccount = error?.data?.name === "odoo.exceptions.AccessError";
            if (!this.state.wrongAccount) {
                console.error("Teacher portal: dashboard could not be loaded", error);
            }
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
            this.offeringView = null;
            this.focusAfterPatch = "ctp-notifications-title";
            this.loadNotifications();
        }
    }

    focusSection(id) {
        const target = this.portal.el?.querySelector(`#${id}`);
        target?.focus();
    }

    // ------------------------------------------------------------ roster and attendance
    async openOffering(offeringId) {
        this.offeringView = Symbol();
        this.state.tab = "offering";
        this.state.offeringId = offeringId;
        this.state.roster = null;
        this.state.sessions = [];
        this.state.attendance = {};
        this.state.drafts = {};
        this.focusAfterPatch = "ctp-offering-title";
        await Promise.all([this.loadRoster(offeringId), this.loadSessions(offeringId)]);
    }

    backToOfferings() {
        if (this.state.tab === "offerings") {
            return;
        }
        const offeringId = this.state.tab === "offering" && this.state.offeringId;
        this.focusAfterPatch = offeringId && !this.state.loading && !this.state.loadError
            ? `ctp-open-${offeringId}` : "ctp-dashboard-title";
        this.offeringView = null;
        this.state.tab = "offerings";
        this.state.offeringId = null;
        this.state.roster = null;
        this.state.sessions = [];
        this.state.attendance = {};
        this.state.drafts = {};
    }

    async loadRoster(offeringId) {
        const view = this.offeringView;
        this.state.rosterLoading = true;
        this.state.rosterError = false;
        try {
            const roster = await this.orm.call(SERVICE, "get_roster", [offeringId]);
            if (view === this.offeringView) {
                this.state.roster = roster;
            }
        } catch (error) {
            console.error("Teacher portal: roster could not be loaded", error);
            if (view === this.offeringView) {
                this.state.roster = null;
                this.state.rosterError = errorMessage(error);
            }
        } finally {
            if (view === this.offeringView) {
                this.state.rosterLoading = false;
            }
        }
    }

    async loadSessions(offeringId, savedSessionId) {
        const view = this.offeringView;
        this.state.sessionsLoading = true;
        this.state.sessionsError = false;
        try {
            const data = await this.orm.call(SERVICE, "get_sessions", [offeringId]);
            if (view !== this.offeringView) {
                return;
            }
            const previousSessions = new Map(this.state.sessions.map((session) => [session.id, session]));
            const attendance = {};
            for (const session of data.sessions) {
                const previousRows = previousSessions.get(session.id)?.rows || [];
                const previousStatuses = new Map(previousRows.map((row) => [row.enrollment_id, row.status]));
                const selections = this.state.attendance[session.id] || {};
                const values = {};
                for (const row of session.rows) {
                    const selection = selections[row.enrollment_id];
                    const edited = selection && selection !== previousStatuses.get(row.enrollment_id);
                    values[row.enrollment_id] = session.id !== savedSessionId && edited ? selection : row.status;
                }
                attendance[session.id] = values;
            }
            this.state.attendance = attendance;
            this.state.sessions = data.sessions;
        } catch (error) {
            console.error("Teacher portal: sessions could not be loaded", error);
            if (view === this.offeringView) {
                this.state.sessions = [];
                this.state.sessionsError = errorMessage(error);
            }
        } finally {
            if (view === this.offeringView) {
                this.state.sessionsLoading = false;
            }
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

    recordedCount(session) {
        return session.rows.filter((row) => row.recorded).length;
    }

    saveAttendance(session) {
        const view = this.offeringView;
        const key = `attendance-${session.id}`;
        const values = this.state.attendance[session.id] || {};
        const rows = session.rows.map((row) => ({
            enrollment_id: row.enrollment_id,
            status: values[row.enrollment_id] || "present",
        }));
        return this.run(key, async () => {
            await this.orm.call(SERVICE, "save_attendance", [session.id, rows]);
            this.notification.add(_t("Ирцийг хадгаллаа."), { type: "success" });
            if (view === this.offeringView) {
                this.focusAfterPatch = `ctp-session-${session.id}`;
                await this.loadSessions(this.state.offeringId, session.id);
            }
        });
    }

    // ------------------------------------------------------------ grade requests
    startRequest(row) {
        this.focusAfterPatch = `ctp-score-${row.enrollment_id}`;
        this.state.drafts[row.enrollment_id] = {
            open: true,
            score: row.score,
            reason: "",
            evidence: "",
            error: "",
        };
    }

    cancelRequest(row) {
        this.focusAfterPatch = `ctp-request-${row.enrollment_id}`;
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
        const view = this.offeringView;
        return this.run(`grade-${row.enrollment_id}`, async () => {
            draft.pending = false;
            await this.orm.call(SERVICE, "request_grade_change", [
                row.enrollment_id, score, draft.reason.trim(), (draft.evidence || "").trim(),
            ]);
            this.notification.add(_t("Хүсэлтийг хянуулахаар илгээлээ."), { type: "success" });
            if (view === this.offeringView) {
                delete this.state.drafts[row.enrollment_id];
                this.focusAfterPatch = "ctp-roster-title";
                await this.loadRoster(this.state.offeringId);
            }
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

    get seatCount() {
        return this.offerings.reduce((total, offering) => total + offering.seats_taken, 0);
    }

    get offeringName() {
        const offering = this.offerings.find((item) => item.id === this.state.offeringId);
        return offering?.name || _t("Хичээл");
    }

    get termName() {
        const term = this.state.dashboard && this.state.dashboard.term;
        return term ? term.name : _t("Нээлттэй улирал алга");
    }
}

registry.category("actions").add("campus_portal_teacher", CampusTeacherPortal);
