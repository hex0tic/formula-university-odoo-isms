/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

export class FormAssistant extends Component {
    static template = "formula_assistant.Widget";
    static props = {};

    setup() {
        this.state = useState({
            ready: false, hidden: false, size: "normal", panel: "", name: "",
            greeting: null, draft: "", busy: false, saving: false, error: "", messages: [],
        });
        this.thread = useRef("thread");
        this.input = useRef("input");
        this.pet = useRef("pet");
        this.restore = useRef("restore");
        this.nextId = 0;
        this.active = true;
        onMounted(() => this.load());
        onWillUnmount(() => { this.active = false; });
    }

    async load() {
        try {
            const result = await rpc("/formula/form/brief", {}, { silent: true });
            if (!this.active) {
                return;
            }
            Object.assign(this.state, { ready: true, hidden: result.hidden, size: result.size, name: result.name });
            if (result.brief && !result.hidden) {
                this.state.greeting = result.brief;
                this.state.panel = "greeting";
                void rpc("/formula/form/settings", { seen: true }, { silent: true }).catch(() => {});
            }
        } catch {
            // Render no empty widget for logged-out sessions or during an ERP restart.
        }
    }

    async save(values) {
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        const previous = { hidden: this.state.hidden, size: this.state.size, panel: this.state.panel };
        Object.assign(this.state, values, { error: "" });
        if (values.hidden !== undefined) {
            this.state.panel = "";
        }
        try {
            const result = await rpc("/formula/form/settings", values, { silent: true });
            if (!this.active) {
                return;
            }
            Object.assign(this.state, { hidden: result.hidden, size: result.size });
            if (values.hidden !== undefined) {
                requestAnimationFrame(() => (values.hidden ? this.restore.el : this.pet.el)?.focus());
            }
        } catch {
            if (this.active) {
                Object.assign(this.state, previous, { error: "Тохиргоо хадгалагдсангүй. Дахин оролдоно уу." });
            }
        } finally {
            if (this.active) {
                this.state.saving = false;
            }
        }
    }

    open(panel) {
        this.state.panel = this.state.panel === panel ? "" : panel;
        if (this.state.panel === "chat") {
            requestAnimationFrame(() => this.input.el?.focus());
        }
    }

    close() {
        this.state.panel = "";
        requestAnimationFrame(() => this.pet.el?.focus());
    }

    onKeydown(event) {
        if (event.key === "Escape" && this.state.panel) {
            event.stopPropagation();
            this.close();
        }
    }

    async ask(question = this.state.draft) {
        const text = question.trim();
        if (!text || this.state.busy) {
            return;
        }
        this.state.draft = "";
        this.state.error = "";
        this.state.busy = true;
        this.state.messages.push({ id: ++this.nextId, role: "user", text, items: [] });
        this.scrollToEnd();
        try {
            const answer = await rpc("/formula/form/chat", { question: text }, { silent: true });
            if (this.active) {
                this.state.messages.push({ id: ++this.nextId, role: "form", ...answer });
                // Keep an intentionally short, in-memory conversation.
                if (this.state.messages.length > 30) {
                    this.state.messages.splice(0, this.state.messages.length - 30);
                }
            }
        } catch {
            if (this.active) {
                this.state.error = "Хариулт ачаалагдсангүй. Дахин оролдоно уу.";
                this.state.draft = text;
            }
        } finally {
            if (this.active) {
                this.state.busy = false;
                this.scrollToEnd();
            }
        }
    }

    scrollToEnd() {
        requestAnimationFrame(() => {
            if (this.thread.el) {
                this.thread.el.scrollTop = this.thread.el.scrollHeight;
            }
        });
    }
}
