# Ажлын хуваарилалт

## AI агентуудын одоогийн write scope

| Агент | Ажил | Эзэмших зам |
|---|---|---|
| Codex / Coordinator | Шаардлага, кейс, архитектур, academic module, интеграц ба шалгалт | management/requirements.md, case.md, implementation-plan.md, architecture.md, decisions.md; odoo/addons/campus_university/; evidence/ |
| Claude Code | Deployment, Odoo Community, ISMS module, RBAC/audit/helpdesk | odoo/ (campus_university-гаас бусад), management/proposals/claude-case-and-plan.md |
| OpenCode | Dataset, 3 ISMS бодлого, кейсийн санал | data/, policies/, management/proposals/opencode-case-and-plan.md |
| Sophia / course analyst (Codex туслах) | Өмнөх хичээл, нэр томьёо, багийн бүрэлдэхүүн | management/course-review.md, glossary.md, team.md |
| Infrastructure analyst (Codex туслах) | Орчны зөвхөн унших аудит | management/environment-audit.md |

`messages.md`, `worklog.md`-д бүгд түгжээтэй append хийнэ. Эзэмшлийн өөрчлөлтийг эхлээд messages.md-д тохиролцоно.

## Хүний баг

Formula 5 нь 5 гишүүнтэй. Хэрэглэгчийн баталсан5 хүний хуваарилалтыг human-responsibilities.md-д хэрэгжүүлсэн. Нэрийг өмнөх тайлангаас баталгаажуулсан team.md-д хадгална. AI агентын хийсэн ажил нь хүний бодит хувь нэмрийн нотолгоо болохгүй.


Хүний багийн баталгаатай хуваарилалт: `human-responsibilities.md` (хэрэглэгчийн2026-11-16 заавар).

## Эцсийн интеграцийн эзэмшил

Codex:campus_isms_bridge,university_isms_helpdesk,OCApinnedsource,university_isms_inventory_catalog,evidence/reports. CanonicalSoAдээрх16factualQAмөрийгmessages.md-дзарласныдагууCoordinatorнэгтгэсэн. OpenCodedata/policyэх,ClaudeISMS/deploymentэххадгалагдсан. OpenCode-ийнoutline/demo-scriptхариуирээгүйучирCoordinatorreports/доторнэгтгэнбэлтгэв.
