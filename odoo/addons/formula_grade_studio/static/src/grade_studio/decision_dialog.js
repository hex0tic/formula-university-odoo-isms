/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Reject dialog: the server requires a non-empty review note before action_reject,
 * so the note is collected here and written to review_note by the studio first.
 */
export class GradeDecisionDialog extends Component {
    static template = "formula_grade_studio.DecisionDialog";
    static components = { Dialog };
    static props = {
        title: String,
        body: String,
        confirmLabel: String,
        onConfirm: Function,
        close: Function,
    };

    setup() {
        this.state = useState({ note: "", error: "", submitting: false });
        this.labels = {
            noteLabel: _t("Татгалзсан үндэслэл"),
            notePlaceholder: _t("Татгалзсан шалтгаанаа тодорхой бичнэ үү."),
            cancel: _t("Болих"),
            required: _t("Татгалзсан үндэслэлээ бичнэ үү."),
        };
    }

    confirm() {
        if (this.state.submitting) {
            return;
        }
        const note = (this.state.note || "").trim();
        if (!note) {
            this.state.error = this.labels.required;
            return;
        }
        this.state.submitting = true;
        this.props.onConfirm(note);
        this.props.close();
    }
}
