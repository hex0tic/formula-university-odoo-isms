# Formula ERP: явцын төлөв

Branch: `formula-erp` (суурь `main` 2f68f12). Шинэчилсэн: 2026-11-26.

## Орчин

| Зүйл | Утга |
| --- | --- |
| Ашиглалт | `orgil_isms`, контейнер `isms-odoo`. Энэ ажлын хүрээнд өөрчлөөгүй |
| Staging DB | `orgil_isms_stage`, 2026-11-26 18:09-ийн `pg_dump -Fc` ба filestore архиваас сэргээсэн |
| Staging Odoo | `isms-stage-odoo`, `127.0.0.1:8070`, энэ branch-ийн `odoo/addons`-ийг ачаална, `max_cron_threads = 0` |
| Staging тест хэрэглэгч | `stage_reporter`, `stage_auditor` (зөвхөн staging DB-д, нууц үг репод ороогүй) |
| Тест | Түр DB дээр `-i <modules> --test-enable`, дараа нь DB ба filestore устгагдана |

## Phase 0 үр дүн

| ID | Төлөв | Нотолгоо |
| --- | --- | --- |
| BASE-01, 02 | DONE | `BASELINE.md` |
| BASE-03 | DONE | Staging DB ба контейнер дээрх хүснэгт |
| BASE-04 | DONE | Dump SHA256 `2a035fc4…`, filestore SHA256 `e6217dbd…`. Сэргээсний дараа хөрөнгө 16, эрсдэл 15, зөрчил 22, аудит лог 595, хэрэглэгч 23 нь ашиглалтын DB-тэй таарсан. 192 хавсралтын SHA1 бүгд зөв |
| BASE-05 | DONE | HEAD дээр 52/52 тест PASS (университетийн 7 модуль) |
| BASE-06 | PARTIAL | Шинэ дэлгэцийн screenshot `screenshots/` дотор. Хуучин бүх дэлгэцийн бүрэн цуглуулга хийгдээгүй |
| BASE-07, 08 | DONE | `BASELINE.md`, `GAP_ANALYSIS.md` |
| BASE-09 | DONE | Энэ хавтас |

## Phase 1: `formula_design_system`

| ID | Төлөв | Тайлбар |
| --- | --- | --- |
| UI-01 | DONE | `--fds-*` токен, фонт, `web.assets_backend` ба `web.assets_web_dark` |
| UI-02 | PARTIAL | Навбарын өнгө ба цэсний төлөв. Sidebar ба breadcrumb өөрчлөөгүй |
| UI-03 | DONE | primary, secondary, outline, danger, icon товчны hover, active, focus, disabled |
| UI-04 | PARTIAL | Карт, badge, dialog, toast-ийн хэв. Tooltip ба confirmation өөрчлөөгүй |
| UI-05 | PARTIAL | `prefers-reduced-motion` ба transition. Skeleton зөвхөн Command Center-д |
| UI-06 | PARTIAL | Systray-ийн цайвар, бараан горимын товч (`color_scheme` cookie). Odoo CE-ийн dark bundle хагас тул үндсэн гадаргууг (control panel, form, list, kanban, tab, гарчиг) тусад нь бараан болгосон. Statusbar болон зарим widget цайвар хэвээр |
| UI-07 | PARTIAL | 360, 768, 1440 px дээр Command Center шалгасан. Бусад дэлгэц шалгаагүй |
| UI-08 | PARTIAL | Python тест 3 (asset бүртгэл). HOOT тест NOT RUN |

## Phase 2: `formula_command_center`

| ID | Төлөв | Тайлбар |
| --- | --- | --- |
| DASH-01 | DONE | `formula.command.center.get_dashboard_data`. Бүх тоо хэрэглэгчийн ORM эрхээр, `sudo` хэрэглээгүй. Унших эрхгүй хэсэг `available: false` |
| DASH-02 | DONE | Owl client action, ISMS цэсэнд Command Center. 14 KPI карт, KPI бүр drill-down-тай |
| DASH-03 | DONE | 5×5 heatmap, анхдагч ба үлдэгдэл, `matrix_level`-ээр түвшин. Нүд дээр дарахад тухайн эрсдэлүүд нээгдэнэ (гарын Enter-ээр шалгасан) |
| DASH-04 | NOT STARTED | Чиг хандлагын график |
| DASH-05 | PARTIAL | Хяналтын хамрах хүрээ, зөрчлийн SLA, сүүлийн аудитын үйлдэл. Аудитын бэлэн байдлын үзүүлэлт байхгүй |
| DASH-06 | PARTIAL | Эрхээр шүүгддэг. Үүрэг бүрт тусгай агуулга байхгүй |
| DASH-07 | PARTIAL | Зөрчлийн хугацааны шүүлтүүр. Хадгалсан шүүлтүүр ба экспорт байхгүй |
| DASH-08 | DONE | 10 тест: analyst, auditor, reporter, manager, asset owner-ийн тоо ORM-той тэнцүү, heatmap ба drill-down тэнцүү, хоосон өгөгдөл |

## Шалгалт

| Шалгалт | Үр дүн |
| --- | --- |
| Бүх модуль (7 хуучин + 2 шинэ), түр DB | PASS, 65/65 |
| Staging-д суулгах ба шинэчлэх (`-i`, `-u`) | PASS |
| SCSS хөрвүүлэлт (цайвар ба бараан bundle) | PASS, засварын дараа |
| Headless Chrome: admin, reporter, auditor, бараан горим | PASS, хөтчийн JS алдаа 0 |
| Эрх: reporter эрсдэл, хөрөнгө, аудит логийг харахгүй | PASS (UI ба тест) |
| Heatmap нүднээс drill-down | PASS: 5×3 нүд 1 эрсдэл, жагсаалт 1 мөр |

Интеграцийн үед засагдсан алдаа:
- `min(100%, 150px)` libsass-д алдаа өгч backend-ийн бүх CSS эвдэрсэн.
- `t-on-click="openDrill(x)"` render үед шууд ажиллаж хуудас Аудит лог руу шилжсэн. Arrow function болгосон.
- Модулийн `__init__` нь `tests`-ийг импортолж байсан.

## Нээлттэй эрсдэл (`BASELINE.md`-ээс)

1. MFA суусан ч нэг ч хэрэглэгч идэвхжүүлээгүй. Админ ба CISO ч мөн адил.
2. Аудит лог зөвхөн ORM түвшинд хамгаалагдсан. DB түвшинд tamper-evident биш.
3. Гадна эсвэл өөрчлөгдөхгүй нөөц байхгүй.
4. `university_access_review` нь Settings ба Access Rights эрхийг бусдад олгох боломжтой (GOV-05).
5. Оюутны бүртгэлүүд Discuss #general-д автоматаар орсон.
6. Академик демо бүртгэлүүд Inventory Administrator эрхтэй.

## Дараагийн ажил

WF-01 Incident Console, WF-03 Grade Approval Studio, WF-05 Control Explorer, GOV-05, SEC-01 MFA төлөвлөгөө.
