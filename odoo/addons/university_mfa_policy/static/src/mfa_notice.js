// Shows a sticky reminder to privileged users without TOTP. The server enforces the policy;
// this notice only explains it and offers the standard Odoo TOTP enrolment wizard.
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

const mfaNoticeService = {
    dependencies: ["orm", "notification", "action"],
    start(env, { orm, notification, action }) {
        orm.call("res.users", "get_mfa_status", []).then((status) => {
            if (!status.privileged || status.totp_enabled) {
                return;
            }
            const when = status.enforced
                ? _t("Хоёр шатлалт баталгаажуулалт идэвхжүүлэх хүртэл бодлого батлах, зөрчил хаах, эрх өөрчлөх зэрэг үйлдэл хориглогдсон.")
                : status.enforce_date
                ? _t("%s-ээс эхлэн чухал үйлдэлд TOTP шаардлагатай болно.", status.enforce_date)
                : _t("Давуу эрхтэй бүртгэлд TOTP идэвхжүүлэхийг шаардаж байна (A.8.5).");
            notification.add(when, {
                title: _t("Хоёр шатлалт баталгаажуулалт"),
                type: "warning",
                sticky: true,
                buttons: [{
                    name: _t("TOTP идэвхжүүлэх"),
                    primary: true,
                    onClick: async () => {
                        const act = await orm.call("res.users", "action_totp_enable_wizard", [[user.userId]]);
                        if (act) {
                            await action.doAction(act);
                        }
                    },
                }],
            });
        }).catch(() => {
            // The notice is advisory; the server-side checks do not depend on it.
        });
    },
};

registry.category("services").add("university_mfa_policy_notice", mfaNoticeService);
