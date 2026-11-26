# Formula ERP: эцсын чадварын матриц (REL-05)

Огноо: 2026-11-26. Салбар `formula-erp`, суурь commit `8e74051`. Эх сурвалж: `STATUS.md` (төлөв, тоо), `BASELINE.md`, `GAP_ANALYSIS.md`, `DR_RUNBOOK.md`, `INTEGRATIONS.md`, кодын модулийн бүтэц. Энэ матрицын төлөвийг `STATUS.md`-тэй нийцүүлсэн. Нийцэхгүй тохиолдлыг тэмдэглэсэн.

Төлөв:
- **DONE**: хэрэгжсэн, тест/нотолгоо бий (тэмдэглэсэн хязгаарлалтын хүрээнд).
- **PARTIAL**: хэсэгчлэн хэрэгжсэн. Дутуу хэсгийг тэмдэглэсэн.
- **BLOCKED**: шаардлага, эзэн тодорхойгүй.
- **NOT STARTED**: хэрэгжүүлээгүй.

Тестийн тоо нь `STATUS.md`-д бичигдсэн тоо. Staging дээрх "PASS" нь тухайн тестийн ажиллагааг хэлнэ. Энэ REL-05 ажлын хүрээнд regression suite-ийг дахин ажиллуулаагүй.

## 1. Суурь (BASE)

| ID | Даалгавар | Төлөв | Модуль / файл | Тестийн болон нотолгооны эх сурвалж |
| --- | --- | --- | --- | --- |
| BASE-01 | Repo identity, addon бүртгэл | DONE | `docs/roadmap/BASELINE.md` 1-р хэсэг | BASELINE.md |
| BASE-02 | RBAC, record rule, ACL, workflow-ийн зураглал | DONE | `BASELINE.md` 2-4 | BASELINE.md (file:line) |
| BASE-03 | Staging DB ба контейнерийн хуулбар | DONE | `orgil_isms_stage`, `isms-stage-odoo` | STATUS.md Phase 0 |
| BASE-04 | Staging нөөц ба сэргээлтийн баталгаажуулалт (хэш, модуль, мөрийн тоо, attachment) | DONE | `odoo/scripts/backup/` | STATUS.md, DR_RUNBOOK.md 5-р хэсэг. REL-04-ээр дахин батлагдсан (`RUNBOOK.md` 12) |
| BASE-05 | Суурь тестийн баазлах (HEAD) | DONE | 7 хуучин университетийн модуль | 52/52 PASS |
| BASE-06 | Шинэ дэлгэцийн screenshot | PARTIAL | `docs/roadmap/screenshots/` (41 файл) | Хуучин бүх дэлгэцийн цуглуулга хийгдээгүй |
| BASE-07 | Gap analysis | DONE | `docs/roadmap/GAP_ANALYSIS.md` | GAP_ANALYSIS.md |
| BASE-08 | Baseline ба security posture | DONE | `docs/roadmap/BASELINE.md` | BASELINE.md |
| BASE-09 | Roadmap баримтын бүтэц | DONE | `docs/roadmap/` | STATUS.md, DR_RUNBOOK.md, INTEGRATIONS.md, RUNBOOK.md, USER_GUIDE.md, CAPABILITY_MATRIX.md |

## 2. UI (formula_design_system ба дэлгэцийн хэв)

| ID | Даалгавар | Төлөв | Модуль / файл | Тестийн болон нотолгооны эх сурвалж |
| --- | --- | --- | --- | --- |
| UI-01 | `--fds-*` токен, фонт, web asset-ууд | DONE | `formula_design_system` (`web.assets_backend`, `web.assets_web_dark`) | STATUS.md Phase 1 |
| UI-02 | Navbar өнгө, цэсний төлөв (sidebar, breadcrumb орсонгүй) | PARTIAL | `formula_design_system` | STATUS.md |
| UI-03 | Товчнуудын төлөв (primary, secondary, outline, danger, icon) | DONE | `formula_design_system` | STATUS.md |
| UI-04 | Карт, badge, dialog, toast (tooltip, confirmation орсонгүй) | PARTIAL | `formula_design_system` | STATUS.md |
| UI-05 | Reduced motion, transition, skeleton (зөвхөн Command Center) | PARTIAL | `formula_design_system`, `formula_command_center` | STATUS.md |
| UI-06 | Цайвар / бараан горим (`color_scheme` cookie, systray) | PARTIAL | `formula_design_system` | Odoo CE-ийн dark bundle хагас; statusbar болон зарим widget цайвар |
| UI-07 | Responsive (360, 768, 1440 px) | PARTIAL | Command Center шалгагдсан | Бусад дэлгэц шалгагдаагүй |
| UI-08 | UI тест | PARTIAL | `formula_design_system/tests` (3 тест) | HOOT тест NOT RUN |

## 3. Dashboard (formula_command_center, DASH)

| ID | Даалгавар | Төлөв | Модуль / файл | Тестийн болон нотолгооны эх сурвалж |
| --- | --- | --- | --- | --- |
| DASH-01 | Dashboard өгөгдөл (ORM эрхээр, sudo-гүй) | DONE | `formula_command_center/models/command_center.py` (`get_dashboard_data`) | STATUS.md Phase 2 |
| DASH-02 | Owl client action, 14 KPI карт, drill-down | DONE | `formula_command_center` (client action) | `screenshots/cc_*` |
| DASH-03 | 5x5 heatmap, drill-down | DONE | `formula_command_center` | `screenshots/cc_heatmap_drilldown_1440.png`; Enter-ээр шалгасан |
| DASH-04 | Чиг хандлагын график | NOT STARTED | — | — |
| DASH-05 | Хяналтын хамрах хүрээ, SLA, сүүлийн аудитын үйлдэл (аудитын бэлэн байдлын үзүүлэлт байхгүй) | PARTIAL | `formula_command_center` | STATUS.md |
| DASH-06 | Эрхээр шүүх (үүрэг бүрт тусгай агуулга байхгүй) | PARTIAL | `formula_command_center` | STATUS.md |
| DASH-07 | Хугацааны шүүлтүүр (хадгалсан шүүлтүүр, экспорт байхгүй) | PARTIAL | `formula_command_center` | STATUS.md |
| DASH-08 | Эрхийн тест, heatmap ба drill-down тэнцүү байдал | DONE | `formula_command_center/tests` | 10 тест (STATUS.md) |

## 4. Workflow UX (WF)

| ID | Даалгавар | Төлөв | Модуль / файл | Тестийн болон нотолгооны эх сурвалж |
| --- | --- | --- | --- | --- |
| WF-01 | Incident Console: SLA дараалал, шүүлтүүр, SLA тоолуур | DONE | `formula_incident_console/models/incident_console.py` | Staging хөтөч PASS (STATUS.md) |
| WF-02 | Incident drawer: timeline, helpdesk тасалбар, нөлөөлсөн хөрөнгө, шилжилт | DONE | `formula_incident_console`, `university_isms_helpdesk` | STATUS.md |
| WF-03 | Grade Studio: өмнөх/шинэ дүн, зөрүү, хувилбар, dialog | DONE | `formula_grade_studio/models/grade_studio.py` | `screenshots/p3_grade_*` |
| WF-04 | Бүх үйлдэл server-side `action_*`; татгалзах нэг транзакцид | DONE | `formula_grade_studio`, `campus_university` | STATUS.md (RPC нэгтгэсэн) |
| WF-05 | Control Explorer: 93 хяналт, шүүлтүүр, SoA, нотлох баримт | DONE | `formula_control_explorer/models/control_explorer.py` | `screenshots/p3_control_explorer_*` |
| WF-06 | Эрхийн тойм: модел бүрийн унших эрхийн эх сурвалж | DONE | `university_access_review/models/access_review.py` | STATUS.md |
| WF-07 | Ачаалал, хоосон, алдааны төлөв, гарын товч | PARTIAL | Incident Console, Grade Studio | HOOT тест байхгүй |
| WF-08 | Буруу шилжилт, өөрийгөө батлах, хуучирсан хувилбар, давхар дарах | PARTIAL | Grade Studio, Incident Console | Хоёр транзакцийн бодит зэрэгцээ шалгалт NOT VERIFIED |

## 5. ISMS (ISMS-01..10)

| ID | Даалгавар | Төлөв | Модуль / файл | Тестийн болон нотолгооны эх сурвалж |
| --- | --- | --- | --- | --- |
| ISMS-01 | Нотлох баримт: SHA-256 серверт, хувилбарын гинж, digest дахин шалгах | DONE | `university_isms_evidence/models/evidence.py`, `attestation.py` | 16 тест (STATUS.md ISMS-10) |
| ISMS-02 | Хяналтын тестийн төлөвлөгөө (гар, автомат), гүйцэтгэлийн бүртгэл өөрчлөгдөхгүй | DONE | `university_isms_monitoring_plus/models/control_test.py` | 20 тест (ISMS-10) |
| ISMS-03 | Цаг тутмын cron, давхар ажиллахгүй, 7 автомат шалгалт, 2 гар тест | DONE | `university_isms_monitoring_plus/models/check_registry.py` | STATUS.md staging шалгалт |
| ISMS-04 | Олдвор давхардахгүй (`_upsert_from_source`), PASS олдвор хаахгүй | DONE | `university_isms_monitoring_plus`, `university_isms_capa/models/finding.py` | STATUS.md |
| ISMS-05 | Олдвор, CAPA, хэрэгжүүлэлт, бие даасан баталгаажуулалт, CISO хаалт | DONE | `university_isms_capa/models/capa.py`, `finding.py` | 24 тест (ISMS-10) |
| ISMS-06 | Бодлогын баталгаажуулалтын кампанит ажил, хуучирсан хувилбар `stale` | DONE | `university_isms_evidence` | STATUS.md |
| ISMS-07 | Эрсдэлийн waiver (CISO батална), хугацаа дуусах, дахин үнэлгээ. Хөрөнгийн амьдралын мөчлөгийн сануулга байхгүй | PARTIAL | `university_isms_capa/models/waiver.py`, `risk_reeval.py` | STATUS.md |
| ISMS-08 | Аудитор, CISO-д ZIP экспорт (`index.csv`, `missing.csv`, `manifest.txt`) | DONE | `university_isms_evidence/models/export.py` | STATUS.md |
| ISMS-09 | NIST ба CIS зураглал (лицензтэй эх сурвалж шаардлагатай) | NOT STARTED | — | — |
| ISMS-10 | Тестийн тоо: capa 24, monitoring 20, evidence 16 | DONE | — | STATUS.md |

Staging дээрх автомат шалгалтын үр дүн (STATUS.md, 2026-11-26): A.8.15 PASS, A.8.5 FAIL (4/4 давуу эрхтэн TOTP-гүй, FND-2026-0002), A.8.2 PASS, A.5.33 PASS, A.5.26 FAIL (18 SLA хэтэрсэн, 15 шалгагчгүй, FND-2026-0001), A.5.18 PASS, A.5.1 PASS.

## 6. Governance ба аюулгүй байдал (GOV, SEC)

| ID | Даалгавар | Төлөв | Модуль / файл | Тестийн болон нотолгооны эх сурвалж |
| --- | --- | --- | --- | --- |
| GOV-01 | Эрхийн кампанит ажил (30/90/өөрийн хоног), хянагч нь удирдлага эсвэл CISO, escalate | DONE | `university_access_governance/models/recert.py`, `governance_common.py` | `screenshots/p5_recert_campaigns_admin.png` |
| GOV-02 | Separation of duties | PARTIAL | `campus_university`, `university_access_governance`, `university_isms` | 3 SoD дүрэм хүсэлт ба дахин баталгаажуулалтад. Тусдаа SoD хяналтын урсгал байхгүй |
| GOV-03 | Түр болон давуу эрхийн хүсэлт (үндэслэл, хугацаа, cron идэвхжүүлэх, хасах) | DONE | `university_access_governance/models/access_request.py` | `screenshots/p5_access_requests_admin.png` |
| GOV-04 | Давуу эрхтний тайлан (нэвтрэлт, TOTP, түр эрх, нээлттэй мөр; нууц талбар байхгүй) | DONE | `university_access_governance/models/report.py` | `screenshots/p5_privileged_report_admin.png` |
| GOV-05 | Settings ба Access Rights зөвхөн системийн админ олгож хураана | DONE | `university_access_governance`, `university_isms/models/res_users.py` | STATUS.md Phase 3 |
| SEC-01 | Step-up MFA (`enforce_date`), TOTP-гүй давуу эрхтэнд хориг, login хаахгүй | DONE | `university_mfa_policy/models/mfa_policy.py` | `screenshots/p5_mfa_notice_admin.png`. Огноо тохируулаагүй (`RUNBOOK.md` 5) |
| SEC-02 | Аудит гинж (SHA-256), PostgreSQL trigger, 15 мин forward, HMAC IP | DONE | `university_isms_audit_chain/models/audit_chain.py`, `audit_forward.py`, `audit_chain_head.py`, `hooks.py` | Staging (STATUS.md): 642 бичлэг, trigger UPDATE/DELETE хориглосон. Tamper-evidence бүрэн биш (superuser) |
| SEC-03 | Шифрлэсэн нөөц, SHA-256 manifest, хоёр байршил, retention, сэргээлт | PARTIAL | `odoo/scripts/backup/backup.sh`, `restore_verify.sh`, `isms_backup_tool.py` | Staging RTO ~82 s (DR_RUNBOOK). REL-04 дээр дахин: `RUNBOOK.md` 12. Offsite, WORM, cron NOT VERIFIED |
| SEC-04 | Халдлагын регресс тест (эрх дээшлүүлэх, IDOR, side-channel, CSRF, export) | DONE | `university_security_tests` (тест модуль) | 22/22 PASS (DR_RUNBOOK 7-р хэсэг). Helpdesk, campus_isms_bridge орсонгүй |

## 7. Академик ERP (EDU)

| ID | Даалгавар | Төлөв | Модуль / файл | Тестийн болон нотолгооны эх сурвалж |
| --- | --- | --- | --- | --- |
| EDU-01 | Оюутны портал `/my/campus` (хуваарь, дүн, GPA, ирц, бүртгэл, транскрипт). Зөвхөн өөрийн мөр, CSRF | DONE | `campus_portal/models/portal_student.py`, `controllers/student.py` | Staging хөтөч: 200, CSRF-гүй POST 400 (STATUS.md Phase 6) |
| EDU-02 | Багшийн портал (хичээл, roster, ирц, дүнгийн засварын хүсэлт) | DONE | `campus_portal/models/portal_teacher.py` | Staging хөтөч: бүртгэлийн тоо 1/25 болж шинэчлэгдсэн (STATUS.md Phase 6) |
| EDU-03 | Бүртгэлийн хугацаа, багтаамж (мөр түгжээ), урьдчилсан нөхцөл, кредит, хуваарийн давхцал, хасах хугацаа | DONE | `campus_academic_plus/models/enrollment.py`, `policy.py`, `schedule.py`, `term.py` | Багтаамж 0 үед хориглоно (STATUS.md) |
| EDU-04 | Хуваарь, ирц, үсгэн үнэлгээ, кредитээр жигнэсэн GPA, төгсөлтийн шаардлага, PDF транскрипт | DONE | `campus_academic_plus/models/schedule.py`, `catalog.py`; `campus_portal` | Бодлогын анхдагч утга нь тохируулж болох таамаг |
| EDU-05 | Элсэлт, төлбөр, тэтгэлэг | BLOCKED | — | Шаардлага, эзэн тодорхойгүй. Бодлого оруулаагүй |

## 8. Интеграц (INT)

| ID | Даалгавар | Төлөв | Модуль / файл | Тестийн болон нотолгооны эх сурвалж |
| --- | --- | --- | --- | --- |
| INT-01 | SSO (OIDC) адаптер | PARTIAL | `formula_integration_hub/models/sso.py` | OIDC тохиргоо, хэрэглэгч бүртгэх. `auth_oauth` суугаагүй, нэвтрэлтэд холбоогүй. Бодит IdP NOT VERIFIED |
| INT-02 | Moodle LMS адаптер (mock, ERP эх сурвалж) | PARTIAL | `formula_integration_hub/models/moodle.py` | Moodle-ийн дүн зөвхөн `grade.change` ноорог. Бодит Moodle NOT VERIFIED |
| INT-03 | Мэдэгдэл: тохиргоо, загвар, mail queue, үйл явдлын бүртгэл | DONE | `formula_integration_hub/models/notify.py` | SMTP NOT VERIFIED (`outgoing` төлөв л шалгасан) |
| INT-04 | SIEM үйл явдал: HMAC payload, outbox, retry | PARTIAL | `formula_integration_hub/models/siem.py`, `event.py`, `transport.py` | Бодит хүлээн авагч NOT VERIFIED. `mfa_policy_block` төрөл холбогдоогүй (`university_mfa_policy` тусдаа dependency биш) |
| INT-05 | API boundary: API түлхүүр, rate limit (429), анхдагчаар унтраалттай | PARTIAL | `formula_integration_hub/controllers/api.py`, `models/api_service.py` | STATUS.md: DONE. INTEGRATIONS.md: `/api/formula/v1/...` HTTP routing төгсгөл хүртэл NOT VERIFIED; multi-worker rate limit NOT VERIFIED. Тэмдэглэл: төлөв зөрөөтэй |

Интеграцийн тестүүд: `formula_integration_hub` 38 тест, mock transport, сүлжээгүй (INTEGRATIONS.md). Live IdP, Moodle, SIEM, SMTP-ийг бодитоор шалгаагүй.

## 9. AI туслах (AI)

| ID | Даалгавар | Төлөв | Тэмдэглэл |
| --- | --- | --- | --- |
| AI-01 | Зөвхөн унших, эрхээр шүүсэн policy/control/risk/incident хайлт | DONE | `formula_isms_copilot/models/copilot_service.py`: хэрэглэгчийн ORM эрхээр хайна. Staging: шинжээч 12 эх сурвалж, мэдээлэгч зөвхөн хяналт ба бодлого. Тест 31/31 |
| AI-02 | Хариулт нь тодорхой record/нотолгоонд холбогдоно | DONE | Хариултын блок бүр модел, id, холбоос, эх хэсэгтэй. «Аудитын нотолгоо биш» гэж тэмдэглэнэ |
| AI-03 | Эрсдэлийн хяналт, зөрчлийн хураангуй, нотолгооны дутууг санал болгох (эх сурвалж, тодорхойгүй байдлыг заах) | DONE | Санал таб: эрсдэлд хяналт, зөрчлийн хураангуй, хяналтын дутуу нотолгоо. Түлхүүр үгийн давхцлаар тул ойролцоо |
| AI-04 | Зөвшөөрөлтэй үйлдлийг хүн батална (дүн, эрх, инцидент, эрсдэл AI-аар хийгдэхгүй) | DONE | Туслах бичих эрхгүй. Батлах, хаах, хүлээн зөвшөөрөх, эрх олгох, дүн өөрчлөх хүсэлтээс татгалзана (монгол үйл үгийн хувирал орно). Staging дээр «хааж өг» хүсэлтээс татгалзсан |
| AI-05 | Нууцлал, prompt injection хамгаалалт, provider data policy, audit logging | PARTIAL | Injection тэмдэглэгээ, PII нууцлал, гадны provider анхдагчаар унтраалттай (data policy зөвшөөрөл шаардана), асуултын лог (аудитор, CISO). Бодит гадны provider NOT VERIFIED |

## 10. Релиз ба үйл ажиллагаа (REL)

| ID | Даалгавар | Төлөв | Тэмдэглэл |
| --- | --- | --- | --- |
| REL-01 | Backend, frontend, security, upgrade, regression suite бүх addon дээр | DONE | 23 модуль, түр DB: 375/375 PASS (эцсийн код). Upgrade, uninstall, reinstall REL-04-д. HOOT JS тест байхгүй |
| REL-02 | UI visual QA: mobile/tablet/desktop, цайвар/бараан | PARTIAL | `QA_REPORT.md`: 54 үзэлт, хэвтээ гүйлгэх мөргүй, JS алдаа 0, 6 SCSS засвар. Оюутны портал бараан горимгүй, policy form-ын 2 контраст асуудал үлдсэн |
| REL-03 | Dashboard query профайлинг, representative dataset | DONE | `QA_REPORT.md`: N+1 олдоогүй, query тоо өгөгдлөөс үл хамаарна, бүх dashboard дуудлага 1 секундээс бага (cold 241 ms). Production хэмжээний өгөгдөл NOT VERIFIED |
| REL-04 | Backup, restore, upgrade, deployment, rollback, failure mode | PARTIAL | Throwaway DB дээр VERIFIED: нөөц, сэргээлт, custom addon upgrade, uninstall/reinstall, алдаатай upgrade, rollback rehearsal (RTO ~52 с). Production байрлуулалт, production rollback, offsite, cron backup NOT VERIFIED. Дэлгэрэнгүй: `RUNBOOK.md` 12 |
| REL-05 | Runbook, оператор баримт, хэрэглэгчийн гарын авлага, эцсийн матриц, known limitations | DONE | `RUNBOOK.md`, `USER_GUIDE.md`, `CAPABILITY_MATRIX.md`, `QA_REPORT.md`, `DR_RUNBOOK.md`, `INTEGRATIONS.md`, `STATUS.md` |

## 11. Тоон дүн

| Төлөв | Тоо (энэ матриц) |
| --- | --- |
| DONE | 47 |
| PARTIAL | 22 |
| BLOCKED | 1 (EDU-05) |
| NOT STARTED | 2 (DASH-04, ISMS-09) |

Тоо нь энэ баримтын төлөвийн баганаас тоологдсон. Нийт 72 ID. 2026-11-26-нд эцэслэв.

## 12. NOT VERIFIED жагсаалт (нэгтгэл)

1. Production (`orgil_isms`, `isms-odoo`, `isms-https`) байрлуулалт, upgrade, rollback.
2. Backup cron, offsite host, rsync over ssh, WORM, `chattr +i`, key escrow.
3. Migration дундуур алдаа гарсан үеийн хагас шинэчлэгдсэн DB (partial upgrade).
4. Restore хийсний дараа Odoo вэбийг бүтнээр эхлүүлж нэвтрэх шалгалт.
5. IdP (OIDC) login, Moodle Web Services, SMTP, SIEM хүлээн авагч, HTTP API routing төгсгөл хүртэл (INT-01..05).
6. Login форм дээрх rate limit, multi-worker rate limit.
7. Хоёр транзакцийн бодит зэрэгцээ шалгалт (WF-08).
8. Бүх дэлгэцийн responsive, бүх эрхийн хөтчийн QA (UI-07, REL-02).
9. HOOT тест (UI-08, WF-07).
10. `enforce_date` тохируулсан үеийн MFA хориг (SEC-01 production-д).
11. Helpdesk холбоотой ticket-ийн нууцлал, `campus_isms_bridge` security тест.
12. Scheduled backup-ийн RPO график.
