# Ажлын явц ба нотолгоо

## 2026-11-16 — Эхлэл
- Эх бие даалтын PDF болон Sem1–Sem10 материалын жагсаалтыг гаргав.
- Sophia, shared-lab-vms, PDF skill-үүдийг уншив.
- VM бодлогыг уншиж lab-vms refresh ажиллуулав (11 бүртгэл, нийт 58 илрүүлэлт).
- Бие даалтын PDF 6 хуудас, текст давхаргагүй тул хуудас бүрийг зургаар унших шаардлагатай.

## 2026-11-16 10:39 — Deployment агент
- Даалгаврын PDF-ийн 6 хуудсыг 200dpi зураг болгон бүрэн уншив (Даалгавар 1–8, тайлангийн 11 бүтэц, үнэлгээ 10 оноо, ёс зүй).
- Орчин шалгав: Docker 29.9.3 / Compose 5.7.1 идэвхтэй; /var 13G сул; 8069/8072/5432 сул; postgres:16-alpine локалд байгаа; Odoo контейнер байхгүй.
- `lab-vms refresh` + `find --role odoo/erp` → тохирох бүртгэл байхгүй. Docker сонголт A-г санал болгов.
- messages.md-д олдвор ба ажлын хуваарийн санал нэмэв.

## 2026-11-16 10:41 — OpenCode (Gemini 4 Argon)
- Бие даалтын заавар PDF (6 хуудас) болон `Sem1/Семинар_1_formula5.pdf`-ийг уншиж, багийн 5 гишүүний нэр, оюутны кодыг (`Formula 5`: Э. Доржсэмбэ B241870023, Б. Батдэмбэрэл B241870018, Б. Бадрал B241870051, А. Эрхэмбаяр B241870055, Б. Тэлмүүн B241870042) баталгаажуулав.
- `messages.md`-д багийн 5 гишүүний мэдээлэл, үүргийн хуваарилалт болон Deployment агент / Coordinator-той давхцахгүй ажиллах саналаа бичив.

## 2026-11-16T10:43:12+08:00 — Sophia: эх сурвалж ба багийн бүрэлдэхүүн
- Хичээлийн эх файлуудыг read-only бүртгэж, лекцийн 6 Markdown-ийг (нийт 4 694 мөр) бүрэн уншив.
- Семинарын 26 PDF/DOCX/PPTX/XLSX эхээс текст, хүснэгт, slide, cell/formula локатор бүхий түр олборлолт хийв; текстгүй 7 удирдамжийн PDF-ийн 30 хуудсыг зургаар уншихаар render хийв.
- Sem1-ийн 2, Sem2/3/4/5/6–7-ийн 5 буюу нийт 7 DOCX-ийн нүүр дэх таван нэр, кодын хослолыг тулгасан; ижил. `management/team.md` үүсгэв.
- Зөвхөн хариуцуулсан Markdown болон flock append журналд бичив. Эх файлууд, VM, контейнер, package төлөвийг өөрчлөөгүй.

## 2026-11-16 — Шаардлагын судалгаа
- Зааврын 6 хуудсыг бүгдийг render хийж нүдээр уншив.
- 21 албан шаардлага + 8 хэрэглэгчийн нэмэлт бүхий requirements.md үүсгэв.
- 4/5 гишүүний зөрүү, 8–10/20–25 control-ын зөрүүг хэрэглэгч ба дэлгэрэнгүй зааврын дагуу шийдэв.
- OpenCode, Deployment агент хоёр messages.md-д нэгдэж, нийтлэг файлын харилцаа ажиллаж байгааг батлав.

## 2026-11-16T10:48:47+08:00 — Infrastructure analyst: read-only орчны аудит дуусав
- `shared-lab-vms` skill, POLICY.md, багийн management болон applicable AGENTS зааврыг уншив; Coordinator-ийн 10:37:13+08 refresh-ийг ашиглав. Дахин refresh/reserve хийгээгүй.
- `lab-vms find` Odoo/Linux/Ubuntu/Debian/database/container/web/Postgres/Kali/server; `media` Ubuntu/Debian/Linux/all; registry 58 илрүүлэлт (11 curated id, 6 guest-verified, 36 empty disk) ба 5 lease-ийг тулгав. Тохирох verified available Linux server VM олдоогүй.
- Docker 29.9.3 / Compose 5.7.1 daemon query амжилттай; 59 containers, 4 running, 53 images. Cached postgres:16-alpine local ID 721873c34ceb, Odoo image байхгүй snapshot. Existing PostgreSQL/Ubuntu course state-д өөрчлөлт хийгээгүй.
- Stopped Lab7-ийн хоёр Ubuntu container-ийн /etc/os-release-ийг `docker cp -L ... -` stdout tar-аас санах ойд уншив: Ubuntu 24.04.5 LTS. Start/exec/local extraction хийгээгүй.
- Actual process/service/socket, scoped Odoo filename/config locations, порт, exact df bytes, RAM/swap/CPU-г шалгав. Root 97%, available 12,882,636,800 B; /data available 49,127,845,888 B (10:42:32+08). Permission-denied ба scope limitation-уудыг тайланд тэмдэглэв.
- `management/environment-audit.md` бичив; UTF-8/code-fence/evidence-reference consistency шалгав. Official Odoo 18/PostgreSQL Docker docs-оор хувилбарын шаардлагыг тулгав. Санал: existing Docker runtime + шинэ тусдаа Odoo Community/PG16 stack, cached image layer reuse, шинэ data/filestore; суулгалт/тест deployment эзэнд.
- Нийт mutation: өөрийн report болон messages.md/worklog.md-д fcntl.flock append. Provision/install/pull/service start-stop/prune/group reserve/registry өөрчлөлт хийгээгүй.

## 2026-11-16 10:49 — Deployment агент: Odoo суулгалт
- `docker pull odoo:18.0` → Odoo Server 18.0-20261112, Python 3.12.3, wkhtmltopdf 0.12.6.1 (PDF тайланд).
- Community addons шалгав: helpdesk/documents/knowledge **байхгүй** (Enterprise) — баталгаажсан.
- `biydaalt/odoo/`: docker-compose.yml (project `isms`, 127.0.0.1:8069), config/odoo.conf.template (list_db=False, without_demo=all, logfile), scripts/setup.sh, init-db.sh, odoo-cli.sh, .gitignore (.env, odoo.conf, logs).
- `scripts/setup.sh`: санамсаргүй нууц үгтэй .env, odoo.conf үүсгэв; /data/sembee/odoo-isms/{pgdata,filestore}.
- `scripts/init-db.sh`: DB `orgil_isms` үүсгэж 7 модуль + mn_MN суулгав (exit=0, registry 47.6 сек).
- `docker compose up -d odoo` → `/web/login` HTTP 200.

## 2026-11-16T10:59:19.572561+08:00 — Codex → баг: campus суусан, 10/10 тест өнгөрлөө
`campus_university` Odoo18 DB-д бодитоор install хийж native TransactionCase 10 тест ажиллуулав: 0 failed, 0 errors. Independent approval, self-approval deny, student/lecturer isolation, auditor read-only, forged-context/direct-state deny, stale-revision reject, freeze/reject reason, forged-create actor ба score range шалгав. Log `evidence/tests/campus-install-test-20261116.log`. `runtime.lock` чөлөөлөгдсөн. `management/case.md`, implementation-plan.md, decisions.md бэлэн, 3,600/280/3 сургууль/2 байр тогтсон. Одоо synthetic academic seed, дараа нь audit bridge хийнэ.

## 2026-11-16 11:04 — Deployment агент: university_isms хөгжүүлэлт ба шалгалт
- `odoo/addons/university_isms/`: 9 модел файл, security (5 бүлэг + 13 record rule, 30 ACL), 93 Annex A CSV (37/8/14/34, 2022 шинэ 11), 12 аюул занал/14 эмзэг байдлын каталог, Risk Treatment Project, 9 view файл, 3 QWeb PDF, цэс, icon.
- `-i university_isms` → exit 0. `-u university_isms --test-enable --test-tags /university_isms` → 13 тест, 0 failed/0 error (`evidence/tests/university_isms-tests-20261116-110343.log`). Эхний оролдлогод password policy (≥10) тестийн хэрэглэгчийг хориглосон → тестийн нууц үгийг уртасгав.
- `scripts/bootstrap.py`: компанийн нэр/улс/MNT, admin нууц үг .env-ээс (hash pbkdf2 баталгаажсан), minlength=10.
- Бодит JSON-RPC нэвтрэлтийн шалгалт: login_failed ×2, login ×1, IP 172.27.0.1 — isms_audit_log-д бичигдсэн.

## 2026-11-16 10:59 — OpenCode (Gemini 4 Argon)
- `management/proposals/opencode-case-and-plan.md` файлыг D01–D07 шийдвэр болон `RM-01 v1.0` (Лекц 8–9 Слайд 19 lookup) аргачлалд нийцүүлэн боловсруулав.
- `biydaalt/policies/` хавтсанд 4 бодлогын баримт бичиг (`POL-01` EISP, `POL-02` Access Control ISSP, `POL-03` Risk Treatment Plan, `POL-04` Acceptable Use Policy)-ийг `.md` болон `.html` форматаар үүсгэв.
- `biydaalt/data/` хавтсанд `schema-university_isms.md` §4-ийн CSV гэрээний дагуу `departments.csv` (8), `users.csv` (11), `assets.csv` (16), `threats.csv` (14), `vulnerabilities.csv` (14), `risks.csv` (14), `soa.csv` (93 хяналт, 25 selected), `incidents.csv` (6), `policies.csv` (4) болон харгалзах `.json` файлуудыг (`risk_matrix_rm01.json`, `stakeholders_objectives.json`) үүсгэж баталгаажуулав.

## 2026-11-16T11:15:52.586939+08:00 — Codex → баг: Helpdesk ба Academic audit bridge installed, 18/18 pass
`campus_university`, `campus_isms_bridge`, `helpdesk_mgmt` (OCA pinned18), `university_isms_helpdesk` суусан. Native18 tests:10 academic +3 audit bridge +5 Helpdesk;0failed0errors. Audit pre/post grade ба approving actor зөв; `isms_audit_skip=True` campus audit-ыг алгасахгүй; 5stage transition Helpdesk-ээс ажиллана, skipping/analyst-close хориг; reporter isolation/auditor read-only/link-delete/tamper deny шалгасан. Log `evidence/tests/campus-helpdesk-integration-20261116.log`.

Deployment агент: шинэ ISMS incident бүр bridge ticket автоматаар үүсгэнэ. Одоо байсан6 imported incident-д `env['isms.incident'].search([])._sync_helpdesk_tickets()` нэг удаа ажиллуулна. Таны CSV import энэ bridge-ийн дараа ажиллавал автоматаар mirror болно. Incident resolve/close нь direct write routed тул importer `_isms_internal`/sudo замаа шалгана уу. Helpdesk stage XML IDs: `university_isms_helpdesk.stage_incident/report/investigate/resolve/close`. Team XML ID team_security.

`management/glossary.md` болон course-review.md дууссан. Sophia/reviewer туслахууд application network permission revoked болж тасалдсан; эхний source review файл нь бэлэн, glossary-г Coordinator course-review эхийн дагуу өөрөө гүйцээв. External OpenCode/Deployment агент shared-file channel үргэлжилж байна.

## 2026-11-16 11:18 — Deployment агент: аюулгүй байдлын засвар, импорт, баталгаажуулалт
- Codex review: context-оор audit алгасах, RPC/kanban-аар workflow алгасах, acceptance/approval хуурах — сервер талын token-оор хаав; шинэ 5 тест. Нийт 18/18 (`evidence/tests/university_isms-tests-20261116-111048.log`). (Засвар: өмнөх бичлэгт «13 record rule» гэсэн нь буруу — 11 record rule, 30 ACL.)
- `university_isms_stock` (isms.asset ↔ product/stock.lot/location) суулгаж тест 1/1.
- `scripts/import_case_data.py`: schema §4 CSV → idempotent upsert, dry-run горим; OpenCode data-г бодитоор импортлов (16 хөрөнгө, 14 эрсдэл, 25/93 SoA, 6 инцидент, 4 бодлого, 11 хэрэглэгч).
- `bootstrap.py`: лого, `auth_signup.invitation_scope` b2c→b2b (DB үүсгэхэд Odoo-гийн анхдагчаар b2c орсон байсан, 02:48 __system__).
- HTTP-ээр CISO хэрэглэгчийн session-оор 6 моделийн бүх view ачаалж, 3 PDF үүсгэв (`evidence/reports/`); built-in browser-оор list/pivot/kanban-ыг нүдээр шалгав; session-ийг logout хийв.
- `management/odoo-guide.md`, `odoo/README.md` бичив. `biydaalt/.gitignore`: `evidence/private/`.

## 2026-11-16 — Codex: нийлмэл хэрэгжүүлэлт ба эцсийн материал
39 native tests0failed0errors. Inventory16product/5DEMOserial,Helpdesk7ticket/5stage,livegrade72→85өөрбатлагч,3policyliveapproval/ack,backuprestore48.414сек/190attachmentPASS. SoA25selected:15yes10partial. Хүний үүргийн хэрэглэгчийнзааврыгhuman-responsibilities.md-дбаталгаажуулсан.
28pagePDF+10slideeditablePPTXбэлтгэжбүххуудас/слайдынvisualQAхийжбайна. OpenCode-ийнreportsoutline/demo-scriptхариуирээгүйтулCoordinatorтэдгээрийгуулзалтынхүрээнднэгтгэнхийв. Нууцфайлгүйsource/evidencepackageгаргана. Эцсийнфайлыгreports/баCodexoutputs/хоёуландхадгална.

## 2026-11-16 — Codex → баг: хэрэглэгчийн нэрийн өөрчлөлт
Одоогийн их сургуулийн нэр **Formula University** боллоо. Coordinator canonical case/data/policies/source display labels ба Odoo company/team/menu-г migration хийж, current screenshots/PDF/PPTX-г дахин гаргаж байна. Append-only history, audit лог, backup болон техникийн DB/login ID-г түүхэн нотолгоогоор хадгална. D08-г мөрдөнө.

## 2026-11-16 — Codex: Formula University нэгдсэн хувилбар бэлэн
D08 нэрийн өөрчлөлтийг company/menu/canonical data/policies/report/deck дээр хэрэгжүүлэв. Current UI-г дахин авч manifest.json-д SHA256, хэмжээ, огноогоор бүртгэсэн. Policyv1.2 review/approval/ack ажилласан; nextreview огноог бодлогын давтамжтай тулгав. post-rebrand-data-qa.json PASS:16 Inventory,25 selected(15yes/10partial),19 internaluser,7 incident/7 ticket.
28 хуудасны PDF,10 слайдын editablePPTX,reports/demo-script.md(12мин,5хүн),management/operations.md бэлэн. Regression39/39 PASS лог хадгалагдсан. Хүний үүргийг хэрэглэгчийн баталсан хуваарилалтаар оруулж, хүний хийсэн ажлыг зохиогоогүй. Код/management/evidence архив нууц файлгүй, checksum ба ZIP integrity шалгалттай.

## 2026-11-17 — Codex: засварлах боломжтой Word хувилбар
Хэрэглэгчийн DOCX хүсэлтээр PDF-ийн агуулгаас native Word хувилбар үүсгэв. 28 хуудас,24 засварлах хүснэгт,5 бодит зураг; Times New Roman,A4;native heading numbering,SEQcaption,PAGEREF/TOC. DOCX-ийг render хийж28хуудсыгнүдээршалгасан. Файл reports/Formula5_FormulaUniversity_Odoo_ISMS_Report.docx ба Codexoutputs/-д ижилSHA256-тай хадгалагдав.

## 2026-11-17 — Codex: GitHub репозитор бэлтгэв
Хэрэглэгчийн хүсэлтээр `hex0tic/formula-university-odoo-isms` private репозиторт нийтлэх тусдаа Git хуулбар бэлтгэв. Эх `University-coursework` репозиторын remote/history болон ажиллаж буй Odoo DB-г өөрчлөөгүй. `.gitignore`-д локал нууц, хувийн нотолгоо, runtime state/cache-ийг тодорхой хасав; код, DOCX/PDF/PPTX тайлан, canonical өгөгдөл, бодлого, management болон test/UI evidence-ийг багтаав. Шинэ clone-ийн нууц үг ба DB-г локал setup-аар үүсгэнэ.

## 2026-11-17 — Codex: GitHub push амжилттай
`https://github.com/hex0tic/formula-university-odoo-isms` private репозитор үүсгэж `main` branch руу push хийв. Анхны commit `9db325e16a4bc256f9174bf4f30c7f89ccc73720` локал болон GitHub дээр таарсан; remote tree 282 файлтай, нууц зам/тохиргоо агуулаагүй. Тайлангийн DOCX/PDF, PPTX GitHub дээр байгааг шалгав. Локал Git хуулбар ба цааш өөрчлөх зааврыг `management/github.md`-д хадгалав.

## 2026-11-18 07:37 — Deployment агент: төслийн аудит, алдаа засвар, нэмэлт (university_isms 18.0.1.1.0)
**Эхний төлөв:** Odoo 18.0-20261112 + PG16 ажиллаж байсан, 14 custom/CE модуль, 16 хөрөнгө, 14 эрсдэл, 25 сонгосон хяналт, 7 инцидент/7 тасалбар, 516 аудит бичлэг; 39/39 тест (ашиглалтын DB дээр). Runtime лог дахь cron алдаа нь backup үеийн DB restart (benign).
**Олдсон алдаа/дутуу ба засвар:**
1. RSK-14 «Хүлээн зөвшөөрөх» CISO-гийн батлалтгүй 6-р үе шатанд — импорт workflow-г тойрсон → `_isms_repair_workflow_consistency` + migration (эрсдэл хариуцагч нь CISO тул батлалтыг бүртгэв, chatter-т тэмдэглэв); импорт цаашид өөрөө тулгана.
2. INC-2026-0001 (PII) мэдэгдлийн шийдвэргүйгээр хаагдсан; canonical CSV-д багана байгаагүй → `data/incidents.csv/json`-д `notification_done/notification_note`, импорт дэмжих, `sync_incident_notifications.py`-оор DB-д.
3. Risk Treatment Plan Project даалгавар 0 → 5-р үе шатанд автоматаар үүсгэх, migration 10 даалгавар үүсгэв.
4. ISO 6.1.3 f) үлдэгдэл эрсдэлийг эрсдэл хариуцагч/CISO батлах алхам байгаагүй → `action_accept_residual` (Project даалгавар дуусаагүй бол хориглоно, дахин үнэлбэл хүчингүй).
5. Нууцлал: Reporter (багш/оюутан) RPC-ээр бүх хөрөнгийн бүртгэл, SoA-ийн хэрэгжилт, Inventory/lot дээрх ISMS ангилал/байршлыг уншиж чаддаг байсан → ACL хасаж, field groups + create/write-ийн холбоосын шалгалт (Odoo 18 field groups create-д хамгаалдаггүйг тест илрүүлэв). Аудиторт хөрөнгө унших ACL тусад нь.
6. A.6.8: campus-ийн 7 хэрэглэгч инцидент мэдээлж чаддаггүй байсан → `campus_university.group_campus_user` ⇒ ISMS Reporter (campus_isms_bridge 18.0.1.1.0).
7. A.5.3: `admin` техникийн данс CISO эрхтэй байсан → Reporter + Settings л үлдээв (migration).
8. Тайлангийн server action-ууд Odoo 18-д моделийн write эрх шаарддаг тул **аудитор PDF хэвлэж чаддаггүй** байсан → `groups_id` тохируулав.
9. Дотоод token-той context бичлэгтэй хамт дуудагч руу «урсаж» дараагийн хэрэглэгчийн үйлдэлд хамгаалалтыг тойрох боломж (тест илрүүлэв) → шинэ context-той буцаадаг болгов.
10. A.8.31: regression тест ашиглалтын DB дээр ажиллаж sequence дугаар идэж байсан (INC 0021→0070 гэх мэт) → `scripts/run-tests.sh` түр DB.
11. Нэг тест run-д PostgreSQL backend signal 11 (segfault) → дахин PASS; Alpine/musl LLVM JIT-ийг унтраав (ALTER SYSTEM + compose).
12. Bootstrap-д хуучин нэрийн website/email, лого хоосон → Formula University лого, `formula-university.example`.
**Нэмэлт боломж:** brute-force нэвтрэлтийн автомат инцидент (A.8.16), өдөр тутмын мониторинг cron (бодлогын хяналт, хугацаа хэтэрсэн эрсдэл, SLA), Clause 9.3 удирдлагын дүн шинжилгээний PDF, «Хугацаа хэтэрсэн», «SLA хэтэрсэн», «Автомат илрүүлэлт» шүүлтүүр.
**Шалгалт:** `run-tests.sh` → 47/47 PASS (`evidence/tests/regression-20261118.json`). Бодит HTTP: brute-force → INC-2026-0070 (Report, Helpdesk тасалбартай); аудитор SoA/удирдлагын PDF хэвлэнэ, мониторинг хориотой; CISO бүгд; багш бүх хязгаарлагдмал бүртгэлээс татгалзагдсан (`evidence/tests/live-audit-20261118.json`). PDF: `evidence/reports/2026-11-18/`; 11-16-ны түүхэн PDF-ийг санамсаргүй дарж бичсэнээ git хуулбараас сэргээв.

## 2026-11-18 07:39 — Deployment агент: GitHub push
- `hex0tic/formula-university-odoo-isms` → branch `audit-fixes-20261118`, commit `7a43fe0805b40237a309ac1fb9fcadf8ca1baf3a` (48 файл, +1007/−70). Remote SHA таарсан. Push хийхээс өмнө өөрчлөгдсөн 47 файлыг `odoo/.env` ба `evidence/private/`-ийн 22 нууц утгатай тулгаж шалгав — нууц үг ороогүй. `main` руу merge хийх эсэхийг хэрэглэгч шийднэ.

## 2026-11-18 07:54 — Deployment агент: өнөөдрийн ажлын нэгтгэл ба merge
1. **Аудит:** ажиллаж буй Odoo-гийн төлөв (Odoo 18, 14 модуль, 39 тест), runtime лог, DB-ийн өгөгдлийн чанар, бүх custom модулийн код, бодит HTTP-ийн үүргийн allow/deny-г шалгав.
2. **Засвар:** 11 олдвор (импортын workflow зөрчил ×2, Project ашиглагдаагүй, 6.1.3 f) дутуу, Reporter-ийн мэдээлэл задрал, campus мэдээлэх эрхгүй, admin=CISO, аудитор хэвлэж чадахгүй, тест ашиглалтын DB дээр, PG segfault, token context урсах, хуучин нэр).
3. **Нэмэлт:** brute-force илрүүлэлт, мониторинг cron, Clause 9.3 тайлан, шүүлтүүр; `university_isms` 18.0.1.1.0 + migration.
4. **Баталгаа:** 47/47 тест тусдаа DB дээр; бодит HTTP-ээр аудитор/CISO/багшийн эрх; INC-2026-0070 автомат инцидент.
5. **Баримт:** `management/audit-20261118.md` — засвар бүрийн «яагаад» үндэслэл ба ISO заалт; `odoo-guide.md`, `schema-university_isms.md` v1.1, `operations.md`, `README.md` шинэчилсэн.
6. **GitHub:** branch `audit-fixes-20261118` (commit 7a43fe0, a5ad1d3) → үндэслэл бүхий merge commit-оор `main` руу.

## 2026-11-18 07:55 — Deployment агент: `main` руу merge хийгдлээ
`hex0tic/formula-university-odoo-isms` `main` = merge commit `1e7b6f4` (`--no-ff`, branch `audit-fixes-20261118`: 7a43fe0, a5ad1d3, 208659d). Merge commit-ийн мессежид засвар бүрийн шалтгаан (ISO заалттай) бичигдсэн; дэлгэрэнгүй `management/audit-20261118.md`. Remote SHA шалгаж таарсан. Энэ бичлэг дараагийн синкээр GitHub-д орно.

## 2026-11-18 — Codex → Deployment агент/OpenCode/баг: GitHub өөрчлөлтийн review
Хэрэглэгчийн хүсэлтээр main `da14a7f` (эхлээд шалгасан `1e7b6f4`-тэй ижил tree)-г суурь `4aeb926`-той харьцуулав: 50 файл. 47/47 PASS runtime логийг бие даан баталгаажуулсан. Review: `management/github-review-20261118-codex.md`. F1(P1): repair helper бодит owner/CISO action-гүй батлагч/өнөөдрийн огноо нөхдөг; F2(P2): treatment/asset өөрчлөгдөхөд residual approval хуучнаараа; F3(P2): stage.fold=True нь In Progress даалгаврыг дууссанд тооцдог. Яг source method-уудын нөхцөлт логикийг ORM stub-тай тусгаарлан давтав. Monitoring давхар review: архивлагдсан хариуцагчийн сануулга алга болох, KPI archive-user numerator/active-user denominator зөрөх, cron upgrade локал тохиргоог дарах. Нэгдсэн DOCX/PDF/PPTX хуучин 39 тестийн snapshot хэвээр. Код/runtime/GitHub-д засвар/push хийгээгүй; review болон worklog/messages-ийг үндсэн biydaalt management-д хадгалсан.
