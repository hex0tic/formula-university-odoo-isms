# Schema contract — `university_isms` (Odoo 18.0 Community)

Эзэмшигч: **Claude Code**. Өөрчлөх санал бол `messages.md`-д бичнэ үү. Хувилбар: v1 (2026-11-16).

- Модулийн зам: `biydaalt/odoo/addons/university_isms/`
- Хамаарал: `base`, `mail`, `hr`, `project`
- Тусдаа суулгах CE модуль: `auth_totp` (MFA, 8.5), `auth_password_policy` (5.17)
- Бүх ISMS модел `mail.thread` + `isms.audit.mixin`-ийг inherit хийнэ → chatter + өөрчлөгдөхгүй аудит лог.

## 1. Моделиуд ба талбарууд

### `isms.asset` — Мэдээллийн хөрөнгө (Даалгавар 3; A.5.9, A.5.12)
| Талбар | Төрөл | Утга / тайлбар |
|---|---|---|
| `code` | char | `AST-001` (хоосон бол sequence) |
| `name` | char* | |
| `asset_type` | selection | `information` Мэдээлэл, `system` Систем, `software` Программ хангамж, `hardware` Тоног төхөөрөмж, `document` Баримт бичиг, `service` Үйлчилгээ, `people` Хүн, `facility` Байр/талбай |
| `department_id` | m2o `hr.department` | |
| `owner_id` | m2o `res.users` | Хөрөнгийн эзэмшигч |
| `custodian_id` | m2o `res.users` | Хариуцагч (техникийн) |
| `location` | char | |
| `classification` | selection | `public` Нийтэд нээлттэй, `internal` Дотоод хэрэглээнд, `restricted` Хязгаарлагдмал, `confidential` Нууц (Лекц 8–9 слайд 15–16) |
| `confidentiality`, `integrity`, `availability` | selection | `1` Бага, `2` Дунд, `3` Өндөр |
| `asset_value` | int (compute) | **max(C,I,A)** (1–3) — decisions.md D04 |
| `personal_data` | bool | Хувийн мэдээлэл агуулсан эсэх (ХХМХ тухай хууль) |
| `lifecycle_stage` | selection | `classify` Бүртгэх/ангилах, `protect` Аюулгүй байдлыг хангах, `restore` Сэргээх, `dispose` Устгах, `secure_dispose` Хамгаалалттай устгах, `archive` Архивлах (слайд 16) |
| `risk_ids` | m2m `isms.risk` | |
| `risk_level` | selection (compute, stored) | `none`/`low`/`medium`/`high` — холбогдох эрсдэлийн хамгийн өндөр түвшин |
| `control_ids` | m2m `isms.control` | |
| `description` | text | |

### `isms.threat` / `isms.vulnerability` — каталог
| Талбар | Утга |
|---|---|
| `code` | `T-01` / `V-01` |
| `name` | |
| `category` (threat) | `deliberate` Санаатай хүний, `accidental` Санамсаргүй хүний, `technical` Техникийн, `environmental` Байгаль/орчны, `supplier` Нийлүүлэгчийн |
| `category` (vulnerability) | `technical`, `process`, `people`, `physical` |

### `isms.risk` — Эрсдэлийн бүртгэл (Даалгавар 4; Clause 6.1.2–6.1.3, 8.2–8.3)
| Талбар | Төрөл | Утга |
|---|---|---|
| `code` | char | `RSK-01` |
| `name` | char* | Эрсдэлийн товч нэр |
| `description` | text | Сценари |
| `asset_ids` | m2m `isms.asset` | |
| `threat_id` / `vulnerability_id` | m2o | |
| `likelihood` | selection `1`–`5` | 1 Маш ховор (жилд 1), 2 Ховор (улиралд 1), 3 Заримдаа (сард 1), 4 Ихэвчлэн (долоо хоногт 1), 5 Тогтмол (өдөр бүр) |
| `impact` | selection `1`–`5` | 1 Маш бага, 2 Бага, 3 Дунд, 4 Өндөр, 5 Маш өндөр |
| `score` | int (compute) | likelihood × impact |
| `level` | selection (compute) | `low`/`medium`/`high` — **слайд 19-ийн 5×5 матрицаар lookup** (доорх §2) |
| `owner_id` | m2o `res.users` | Эрсдэл хариуцагч |
| `treatment` | selection | `mitigate` Бууруулах, `transfer` Шилжүүлэх, `avoid` Зайлсхийх, `accept` Хүлээн зөвшөөрөх |
| `treatment_plan` | html | |
| `control_ids` | m2m `isms.control` | |
| `residual_likelihood` / `residual_impact` | selection `1`–`5` | |
| `residual_score` / `residual_level` | compute | |
| `due_date` | date | |
| `state` | selection | `identify` 1.Тодорхойлсон → `analyze` 2.Шинжилсэн → `evaluate` 3.Үнэлсэн → `respond` 4.Хариу арга хэмжээ → `implement` 5.Хэрэгжүүлж буй → `residual` 6.Үлдэгдэл эрсдэл хянах (слайд 17 цикл) |
| `task_ids` | o2m `project.task` (`isms_risk_id`) | Risk Treatment даалгаврууд |
| `accepted_by_id`, `accepted_date` | | Зөвхөн CISO хүлээн зөвшөөрнө |

### `isms.control` — Annex A 93 хяналт + SoA (Даалгавар 5, 8)
| Талбар | Утга |
|---|---|
| `code` | `5.1` … `8.34` (модуль 93-ыг бүгдийг ачаална) |
| `name` (EN), `name_mn` | |
| `theme` | `organizational` (5), `people` (6), `physical` (7), `technological` (8) |
| `is_new_2022` | 2022 онд шинээр нэмэгдсэн 11 хяналт |
| `selected` | bool — Controls Mapping-д сонгосон (20–25) |
| `applicable` | bool (default True) |
| `implementation` | `yes` Тийм, `no` Үгүй, `partial` Хэсэгчилсэн |
| `justification` | text — Тайлбар/шалтгаан, үндэслэл |
| `odoo_implementation` | text — Odoo дээр хэрхэн хэрэгжсэн |
| `evidence` | text — нотолгоо (дэлгэцийн зургийн нэр гэх мэт) |
| `responsible_id` | m2o `res.users` |
| `risk_ids` | m2m (inverse) |

### `isms.incident` — Инцидент (Даалгавар 6; A.5.24–5.28, 6.8)
| Талбар | Утга |
|---|---|
| `code` | `INC-2026-0001` (sequence) |
| `name`*, `description` | |
| `state` | **`incident` Incident → `report` Report → `investigate` Investigate → `resolve` Resolve → `close` Close** |
| `category` | `phishing`, `malware`, `unauthorized_access`, `account_compromise`, `data_leak`, `integrity` (дүн/бүртгэл өөрчлөлт), `dos`, `physical`, `policy_violation`, `other` |
| `severity` | `low`, `medium`, `high`, `critical` → SLA: 120 / 72 / 24 / 4 цаг |
| `reporter_id`, `reporter_type` | `student`, `faculty`, `staff`, `external`, `system` |
| `assignee_id` | МАБ шинжээч |
| `detected_at`, `reported_at`, `investigation_at`, `resolved_at`, `closed_at` | datetime (үе шат бүрт автоматаар) |
| `asset_ids`, `risk_ids`, `control_ids` | m2m |
| `impact_c`, `impact_i`, `impact_a` | bool |
| `personal_data_breach`, `data_subjects_count` | |
| `containment`, `root_cause`, `resolution`, `lessons_learned` | text (Resolve-д root_cause+resolution, Close-д lessons_learned заавал) |

### `isms.policy` (+ `isms.policy.ack`) — Бодлогын бүртгэл (Даалгавар 7; A.5.1, 5.37)
`code` (POL-01), `name`, `policy_type` (`eisp`, `issp`, `syssp`, `plan`, `procedure`), `version`, `owner_id`, `approver_id`, `approval_date`, `next_review_date`, `state` (`draft`, `review`, `approved`, `retired`), `content` (html), `control_ids`, `ack_ids` (хэрэглэгч, огноо — «Танилцсан» товч).

### `isms.audit.log` — Аудит лог (Даалгавар 8; A.8.15, 8.16, 5.28)
`timestamp`, `user_id`, `login`, `action` (`create`, `write`, `unlink`, `state`, `login`, `login_failed`, `access_change`), `model`, `res_id`, `res_name`, `changes` (хуучин → шинэ), `ip_address`. UI-аас засах/устгах боломжгүй.

## 2. Эрсдэлийн матриц (Лекц 8–9, слайд 19)
| М ↓ / Н → | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| 1 | low | low | low | low | medium |
| 2 | low | low | medium | medium | medium |
| 3 | low | medium | medium | medium | high |
| 4 | low | medium | medium | high | high |
| 5 | medium | medium | high | high | high |

## 3. RBAC бүлгүүд (xml id)
| xml id | Нэр | Implied |
|---|---|---|
| `university_isms.group_isms_reporter` | Мэдээлэгч | base.group_user |
| `university_isms.group_isms_asset_owner` | Хөрөнгө эзэмшигч | reporter |
| `university_isms.group_isms_auditor` | Дотоод аудитор (зөвхөн унших) | reporter |
| `university_isms.group_isms_analyst` | МАБ шинжээч | asset_owner |
| `university_isms.group_isms_manager` | МАБ менежер (CISO) | analyst, auditor |
| `base.group_system` | Odoo админ | — |

## 4. Импортын CSV формат (OpenCode `data/` → Claude XML)
Олон утгыг `;`-ээр тусгаарлана. Хэрэглэгчийг `login`-оор, холбоосыг `code`-оор заана. UTF-8.
- `users.csv`: `login,name,job_title,department,isms_role` (`reporter|asset_owner|auditor|analyst|manager|admin`)
- `departments.csv`: `name,parent,manager_login`
- `assets.csv`: `code,name,asset_type,department,owner_login,custodian_login,location,classification,confidentiality,integrity,availability,personal_data,lifecycle_stage,description`
- `threats.csv` / `vulnerabilities.csv`: `code,name,category,description`
- `risks.csv`: `code,name,asset_codes,threat_code,vulnerability_code,likelihood,impact,treatment,control_codes,owner_login,residual_likelihood,residual_impact,due_date,state,treatment_plan,description`
- `soa.csv`: `control_code,selected,applicable,implementation,justification,odoo_implementation,evidence,responsible_login`
- `incidents.csv`: `code,name,category,severity,reporter_type,reporter_login,assignee_login,detected_at,state,asset_codes,risk_codes,control_codes,impact_c,impact_i,impact_a,personal_data_breach,data_subjects_count,description,containment,root_cause,resolution,lessons_learned`
- `policies.csv`: `code,name,policy_type,version,owner_login,approver_login,approval_date,next_review_date,state,control_codes,content_file`

## 5. Codex `campus_university`-тай холбох цэг
- `_inherit = ['mail.thread', 'isms.audit.mixin']` → аудит лог автоматаар.
- Дүн өөрчлөх хүсэлт ба бусад академик бичлэгийг `isms.asset` (жишээ: AST-002 дүнгийн сан)-тай m2o-оор холбож болно.
- Шинэ эрхийн бүлэг нэмэх бол `group_isms_*`-ийг implied болгож болно.
