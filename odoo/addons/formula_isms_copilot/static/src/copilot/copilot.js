/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { Layout } from "@web/search/layout";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const MODEL = "formula.isms.copilot";
const KINDS = [
    { value: "risk", label: "Эрсдэл → Annex A хяналтын санал" },
    { value: "incident", label: "Инцидент → хураангуй ба дутуу зүйл" },
    { value: "control", label: "Хяналт → дутуу нотолгоо" },
];
const ERROR_TEXT = "Хүсэлт амжилтгүй боллоо. Дахин оролдоно уу.";

export class FormulaIsmsCopilot extends Component {
    static template = "formula_isms_copilot.Copilot";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.kinds = KINDS;
        this.state = useState({
            tab: "ask",
            question: "",
            scopeOptions: [],
            scopesLoaded: false,
            selectedScopes: [],
            loading: false,
            error: "",
            result: null,
            kind: "risk",
            targets: [],
            targetId: "",
            targetsLoading: false,
            suggestLoading: false,
            suggestError: "",
            suggestion: null,
        });
        useSetupAction({});
        onWillStart(() => this.loadScopes());
    }

    // ------------------------------------------------------------ данс
    async loadScopes() {
        try {
            const options = await this.orm.call(MODEL, "get_scope_options", []);
            this.state.scopeOptions = options;
        } catch (error) {
            console.error("ISMS туслах: хайлтын хүрээ уншигдсангүй", error);
        } finally {
            this.state.scopesLoaded = true;
        }
    }

    // ------------------------------------------------------------ асуулт
    get canAsk() {
        return !this.state.loading && this.state.question.trim().length > 0;
    }

    get answerConfidenceClass() {
        const conf = this.state.result ? this.state.result.confidence : "none";
        return `fcp-conf fcp-conf--${conf}`;
    }

    isScopeSelected(key) {
        return this.state.selectedScopes.includes(key);
    }

    toggleScope(key) {
        const option = this.state.scopeOptions.find((opt) => opt.key === key);
        if (!option || !option.available) {
            return;
        }
        if (this.isScopeSelected(key)) {
            this.state.selectedScopes = this.state.selectedScopes.filter((item) => item !== key);
        } else {
            this.state.selectedScopes = [...this.state.selectedScopes, key];
        }
    }

    onQuestionKeydown(ev) {
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault();
            this.ask();
        }
    }

    async ask() {
        const question = this.state.question.trim();
        if (!question) {
            this.state.error = "Асуултаа бичнэ үү.";
            return;
        }
        this.state.loading = true;
        this.state.error = "";
        this.state.result = null;
        try {
            const result = await this.orm.call(MODEL, "ask", [question, [...this.state.selectedScopes]]);
            if (!result.ok) {
                this.state.error = result.message || ERROR_TEXT;
            } else {
                this.state.result = result;
            }
        } catch (error) {
            console.error("ISMS туслах: асуулт амжилтгүй боллоо", error);
            this.state.error = ERROR_TEXT;
        } finally {
            this.state.loading = false;
        }
    }

    openRecord(block) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: block.model,
            res_id: block.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ------------------------------------------------------------ санал
    setTab(tab) {
        this.state.tab = tab;
    }

    async onKindChange(ev) {
        this.state.kind = ev.target.value;
        this.state.targetId = "";
        this.state.suggestion = null;
        await this.loadTargets();
    }

    onTargetChange(ev) {
        this.state.targetId = ev.target.value;
    }

    async loadTargets() {
        this.state.targetsLoading = true;
        this.state.suggestError = "";
        try {
            this.state.targets = await this.orm.call(MODEL, "list_suggestion_targets", [this.state.kind]);
        } catch (error) {
            console.error("ISMS туслах: бичлэгийн жагсаалт уншигдсангүй", error);
            this.state.targets = [];
            this.state.suggestError = ERROR_TEXT;
        } finally {
            this.state.targetsLoading = false;
        }
    }

    async requestSuggestion() {
        if (!this.state.targetId) {
            this.state.suggestError = "Бичлэгээ сонгоно уу.";
            return;
        }
        this.state.suggestLoading = true;
        this.state.suggestError = "";
        this.state.suggestion = null;
        try {
            const result = await this.orm.call(MODEL, "suggest", [this.state.kind, Number(this.state.targetId)]);
            if (!result.ok) {
                this.state.suggestError = result.message || ERROR_TEXT;
            } else {
                this.state.suggestion = result;
            }
        } catch (error) {
            console.error("ISMS туслах: санал амжилтгүй боллоо", error);
            this.state.suggestError = ERROR_TEXT;
        } finally {
            this.state.suggestLoading = false;
        }
    }

    openSuggestionItem(item) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: item.model,
            res_id: item.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onRootKeydown(ev) {
        if (ev.key === "Escape" && this.state.question) {
            ev.preventDefault();
            this.state.question = "";
        }
    }
}

registry.category("actions").add("formula_isms_copilot", FormulaIsmsCopilot);
