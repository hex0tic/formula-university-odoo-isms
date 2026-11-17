"""Execute in Odoo shell. Uses actual role permissions and preserves case records."""
import json
from odoo.exceptions import AccessError, UserError


def account(login):
    record = env["res.users"].search([("login", "=", login)], limit=1)
    assert record, login
    return record


manager = account("dorjsembe")
analyst = account("erkhembayar")
reporter = account("student_demo")
auditor = account("telmuun")
env["isms.incident"].search([])._sync_helpdesk_tickets()
exercise = env.ref("campus_isms_bridge.live_demo_incident", raise_if_not_found=False)
if not exercise:
    exercise = env["isms.incident"].with_user(reporter).create({
        "name": "Сургалтын демо: дүнгийн хуурамч хүсэлтийг шалгах",
        "description": "Зохиомол сургалтын үйл явдал. Бодит халдлага хийгээгүй. Дүнгийн хүсэлтийн үндэслэл ба батлах үүргийг шалгана.",
        "category": "integrity", "severity": "high", "reporter_type": "student",
    })
    env["ir.model.data"].create({
        "module": "campus_isms_bridge", "name": "live_demo_incident", "model": "isms.incident",
        "res_id": exercise.id, "noupdate": True,
    })
ticket = exercise.sudo().helpdesk_ticket_ids
assert len(ticket) == 1
trace = []
def stage(state, user):
    if exercise.state == state:
        return
    ticket.with_user(user).write({"stage_id": env.ref("university_isms_helpdesk.stage_" + state).id})
    exercise.invalidate_recordset()
    assert exercise.state == state
    trace.append({"state": state, "actor": user.login, "helpdesk_stage": ticket.stage_id.name})

if exercise.state == "incident":
    exercise.with_user(reporter).action_report()
    trace.append({"state": "report", "actor": reporter.login, "helpdesk_stage": ticket.stage_id.name})
if exercise.state == "report":
    stage("investigate", analyst)
if exercise.state == "investigate":
    exercise.with_user(analyst).write({
        "root_cause": "Баталгаагүй сувгаар ирсэн хүсэлтийн зөвшөөрөл, протоколын эхийг тусад нь шалгах шаардлага.",
        "containment": "Хүсэлтийг тусгаарлаж, эх баримт батлагдахаас өмнө дүнг өөрчлөөгүй.",
        "resolution": "Хүсэлт гаргагч ба тусдаа батлагчийн эрхийг шалгаж, зөвшөөрсөн өөрчлөлтийг audit логтой тулгав.",
        "lessons_learned": "Дүнгийн шийдвэрийг системийн хүсэлт, тусдаа батлагч, revision шалгалтаар удирдана.",
        "asset_ids": [(6, 0, env["isms.asset"].search([("code", "in", ["AST-002", "AST-003"])]).ids)],
    })
    stage("resolve", analyst)
if exercise.state == "resolve":
    try:
        ticket.with_user(analyst).write({"stage_id": env.ref("university_isms_helpdesk.stage_close").id})
    except AccessError:
        analyst_close_denied = True
    else:
        raise AssertionError("Analyst must not close CISO incident")
    stage("close", manager)

for policy in env["isms.policy"].search([("code", "in", ["POL-01", "POL-02", "POL-03"])]):
    # Do not backdate live approval. Case document metadata remains source data.
    policy.with_user(manager).action_reset_draft()
    policy.with_user(analyst).action_submit()
    policy.with_user(manager).action_approve()
    policy.with_user(reporter).action_acknowledge()

grade = env["campus.grade.change"].search([("state", "=", "approved")], order="id desc", limit=1)
grade.sudo().write({
    "isms_asset_id": env["isms.asset"].search([("code", "=", "AST-002")], limit=1).id,
    "isms_incident_id": exercise.id,
})
audit = env["isms.audit.log"].search([("model", "=", "campus.enrollment"),
                                     ("res_id", "=", grade.enrollment_id.id), ("action", "=", "write")], limit=1)
assert audit and audit.user_id == grade.approver_id
result = {
    "result": "PASS", "exercise_incident_code": exercise.code,
    "exercise_incident_id": exercise.id, "helpdesk_ticket_id": ticket.id,
    "incident_state": exercise.state, "helpdesk_state": ticket.stage_id.name,
    "live_transition_trace": trace,
    "detected_at": str(exercise.detected_at), "reported_at": str(exercise.reported_at),
    "investigation_at": str(exercise.investigation_at), "resolved_at": str(exercise.resolved_at),
    "closed_at": str(exercise.closed_at),
    "grade_request_id": grade.id, "grade_request_name": grade.name,
    "grade_requester": grade.requester_id.login, "grade_approver": grade.approver_id.login,
    "grade_before": grade.old_score, "grade_after": grade.enrollment_id.score,
    "grade_revision": grade.enrollment_id.grade_revision, "grade_audit_actor": audit.login,
    "grade_audit_changes": audit.changes,
    "counts": {model: env[model].search_count([]) for model in [
        "isms.asset", "isms.risk", "isms.control", "isms.incident", "isms.policy", "isms.audit.log", "helpdesk.ticket",
        "campus.student", "campus.enrollment", "campus.grade.change",
    ]},
    "selected_controls": env["isms.control"].search_count([("selected", "=", True)]),
    "scope": "AI-assisted software exercise with fictional data and actual role checks; not human participation evidence",
}
env.cr.commit()
print("LIVE_RESULT_JSON=" + json.dumps(result, ensure_ascii=False))
