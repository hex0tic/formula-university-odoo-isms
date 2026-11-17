# Шаардлага ба эцсийн нотолгооны индекс

2026-11-16. Одоогийн байгууллага: **Formula University**, сургалтын апп: **Formula Campus**. D08 шийдвэрээр нэр өөрчилсөн. Түүхэн raw draft/submitted зураг, өмнөх backup болон audit нь анхны утгаараа хадгалагдана; одоогийн тайлан, слайд шинэ нэртэй UI ашиглана.

| Шаардлага | Үр дүн ба нотолгоо |
|---|---|
| R01 — Community | Odoo18.0-20261112, PostgreSQL16; compose, environment-audit, odoo-guide |
| R02 — Кейс / Clause4 | case.md; тайлан 3–4;3600 оюутан/280 ажилтан нь simulation |
| R03 — Модуль / ISO | architecture.md; тайлан 5–6; модуль/хяналтын хүснэгт |
| R04 — ≥10asset | 16asset,16Inventoryproduct; inventory-catalog.json,14-inventory-catalog.png |
| R05 — ≥10risk | 14risk; RM-01v1.0 lookup; decisionsD04; тайлан 9–12 |
| R06 — 20–25control | 25selected; data/soa.csv ба controls_soa.json; тайлан 13–14 |
| R07 — 5stageHelpdesk | OCA18+bridge;6nativeHelpdesktest;7incident/7ticket;10,13 зураг |
| R08 — 3policy | EISP/Access/RTP тус бүр 2 хуудас;policyv1.2;нэмэлтAUP |
| R09 — ≥5role | Academic+ISMS ACL/rules;39test allow/deny;тайлан 23 |
| R10 — Users | 19activeinternalaccount snapshot;15-internal-users.png |
| R11 — Audit | grade pre/post actor;16-grade-audit-detail.png; audit write/unlink deny |
| R12 — SoA | 25applicable;15yes/10partial;үндэслэл/эзэн/хүрээ;тайлан 25–26 |
| R13–R16 — Тайлан | 28pagePDF;11 үндсэнхэсэг;5embeddedactualfigures;TOC/bookmarks |
| R17 — Presentation | 10slideeditablePPTX,3nativeeditabletables;render/layout/packageQA |
| R18 — Demo | reports/demo-script.md;12 мин,5 хүн |
| R19 — Хүний хувь нэмэр | Хэрэглэгчийн баталсан үүрэг human-responsibilities.md-д. Хүн өөрөө хийсэн ажил/шалгалтаа worklog-д нотолгоотой нэмнэ;агентын ажлыг хүний оролцоо гэж зохиогоогүй. |
| R20 — Эх сурвалж / AI | Тайлан 27–28,messages/worklog,course-review,THIRD_PARTY.md |
| R21 — Монгол хэл | Монгол тайлан/бодлого/гарын авлага;модуль/техникийн нэр English |
| U01–U08 | management бүрэн бүтэц,3 агентынхарилцаа,өмнөхлекц/семинарынсудалгаа,суусанOdoo,өөрийнacademicмодуль,5 гишүүн,VMreuseaudit |

39 regression тест нь 2026-11-16 11:45(UTC+8)-д 0failed0errors. Дараах нэршлийн өөрчлөлт нь label/company/policy content-д хамаарсан;currentUI ба өгөгдлийн холбоосыг post-rebrand-data-qa.json-аар тусад нь шалгасан. Backuprestore48.414 сек,190attachmentchecksumPASS нь 11:22–11:23snapshot-ийннотолгоо;одоогийнбүхкампусынRTOгэсэндүгнэлтбиш.

Хэсэгчилсэн 10 хяналтынүлдэхажил: MFA enrollment/rollout,offsiteimmutablebackup,external audit sink,physicalcontrols,supplier/JMLүйл ажиллагаа,PIIretention/legalreview,бодит SETA сургалт. Энэ ялгааг SoA-д хадгалсан.
