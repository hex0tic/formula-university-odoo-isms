# GitHub өөрчлөлтийн шалгалт — 2026-11-18

Шалгасан: Codex; monitoring, cron, KPI болон тестийн скриптийг тусдаа reviewer давхар шалгав.

## Хамрах хүрээ ба дүгнэлт

Репозитор: https://github.com/hex0tic/formula-university-odoo-isms

- Суурь commit: `4aeb926de73feec5d4d3f2856c3c0107883f08ff`.
- GitHub `main`: `da14a7f9f599fc250cd09de214b516e2b5574ff5`; tree `f84b1c2404d8d83becdb8103c0ab48740fffd84f`.
- Эхлээд шалгасан `1e7b6f42ffb3f93fdd68e6190738c23a0ee5589a`-ийн tree нь одоогийн commit-той яг ижил. Шалгалтын үеэр commit түүх шинэчлэгдсэн ч файлын агуулга өөрчлөгдөөгүй.
- Өөрчлөлт: 50 файл, 1174 нэмсэн / 70 хассан мөр; нийт tracked файл 298.
- Одоогийн хандалт **PUBLIC**. Өмнө үүсгэх үеийн PRIVATE төлөв өөрчлөгдсөн байна; энэ шалгалтаар хандалтын тохиргоог өөрчлөөгүй.

**Дүгнэлт: засах шаардлагатай 6 кодын асуудал, эцсийн материалын 1 нийцлийн асуудал байна.** Хамгийн түрүүнд F1–F3-ыг засаж, дараа нь regression ба баримтжуулалтыг шинэчилнэ.

## F1 — P1: Migration/import бодит зөвшөөрөлгүй батлалт үүсгэнэ

Эх: [odoo/addons/university_isms/models/risk.py:296](https://github.com/hex0tic/formula-university-odoo-isms/blob/da14a7f9f599fc250cd09de214b516e2b5574ff5/odoo/addons/university_isms/models/risk.py#L296). Migration дуудлага: [odoo/addons/university_isms/migrations/18.0.1.1.0/post-migrate.py:22](https://github.com/hex0tic/formula-university-odoo-isms/blob/da14a7f9f599fc250cd09de214b516e2b5574ff5/odoo/addons/university_isms/migrations/18.0.1.1.0/post-migrate.py#L22).

`_isms_repair_workflow_consistency` нь батлалтгүй эрсдэлийн `accepted_by_id`, `accepted_date`, `residual_accepted_by_id`, `residual_accepted_date`-ийг owner-ийн ID болон өнөөдрийн огноогоор бөглөдөг. Owner/CISO өөрөө батлах үйлдэл хийхгүй; даалгавар дууссан эсэхийг ч энэ зам шалгахгүй. Энэ helper бүх эрсдэлийг хайж, migration болон canonical import бүрийн төгсгөлд ажиллана. Chatter-т засвар гэж тэмдэглэсэн ч батлалтын үндсэн талбарууд бодит шийдвэр гаргаагүй хүнийг батлагч болгож байна.

Дахин үзүүлэлт: батлагчгүй, owner=42, `treatment=accept`, `state=residual` бичлэг дээр helper дуудахад хоёр батлагч хоёул 42 болов.

Засвар: батлалтгүй бичлэгийг дахин хянуулах төлөвт оруулж, шаардлагатай owner/CISO approval action-ийг гүйцэтгүүлнэ. Кейсийн зохиомол импортын metadata-г бодит батлалтаас тусдаа хадгална.

## F2 — P2: Арга хэмжээ эсвэл хөрөнгө солигдоход үлдэгдэл батлалт хүчингүй болохгүй

Эх: [odoo/addons/university_isms/models/risk.py:142](https://github.com/hex0tic/formula-university-odoo-isms/blob/da14a7f9f599fc250cd09de214b516e2b5574ff5/odoo/addons/university_isms/models/risk.py#L142).

`_ASSESSMENT_FIELDS` өөрчлөгдөхөд анхны `accepted_by_id`-г цэвэрлэдэг боловч үлдэгдэл батлалтыг зөвхөн `residual_likelihood/residual_impact` өөрчлөгдөхөд цэвэрлэнэ. Батлагдсан эрсдэлийн treatment эсвэл asset-ийг солиход өмнөх шийдвэр өөр нөхцөлд хүчинтэй мэт үлдэнэ.

Дахин үзүүлэлт: `state=residual`, `residual_accepted_by_id=42` эрсдэлийн treatment-ийг `mitigate → avoid` болгоход state болон residual approval хэвээр үлдэв.

Засвар: батлагдсан төлөвлөгөө, хөрөнгө, үндсэн үнэлгээ зэрэг шийдвэрийн үндэслэл өөрчлөгдөхөд үлдэгдэл батлалтыг цэвэрлэж дахин батлуулах төлөвт оруулна.

## F3 — P2: Kanban баганыг эвхсэнийг даалгавар дууссантай адилтгана

Эх: [odoo/addons/university_isms/models/risk.py:252](https://github.com/hex0tic/formula-university-odoo-isms/blob/da14a7f9f599fc250cd09de214b516e2b5574ff5/odoo/addons/university_isms/models/risk.py#L252); ижил тооцоо KPI-д [odoo/addons/university_isms/models/monitoring.py:135](https://github.com/hex0tic/formula-university-odoo-isms/blob/da14a7f9f599fc250cd09de214b516e2b5574ff5/odoo/addons/university_isms/models/monitoring.py#L135).

`not t.stage_id.fold and t.state not in ('1_done', '1_canceled')` нөхцөл нь `fold=True` баганад байгаа `01_in_progress` даалгаврыг нээлттэйд тооцохгүй. Үүний улмаас дутуу ажлыг үлдэгдэл батлалтад саад болохгүй гэж үзэж, management review-д дууссан ажлын тоог өсгөж болно. Odoo 18-ийн эх кодод `fold` нь “Folded in Kanban”, дууссан эсэхийг `state/is_closed` тусад нь тодорхойлдог.

Дахин үзүүлэлт: `stage.fold=True`, `state=01_in_progress` нэг даалгавар дээр `_treatment_tasks_open()` хоосон буцав.

Засвар: даалгаврын бодит `state/is_closed`-оор шалгаж, цуцалсан ажлыг дууссанаас бизнесийн дүрмээр ялгана. Тестэд зөвхөн stage солихын оронд бодит completion state-ийг шалгана.

## F4 — P2: Хариуцагч архивлагдвал monitoring сануулга алга болно

Эх: [odoo/addons/university_isms/models/monitoring.py:27](https://github.com/hex0tic/formula-university-odoo-isms/blob/da14a7f9f599fc250cd09de214b516e2b5574ff5/odoo/addons/university_isms/models/monitoring.py#L27), хариуцагч сонгох хэсэг [odoo/addons/university_isms/models/monitoring.py:61](https://github.com/hex0tic/formula-university-odoo-isms/blob/da14a7f9f599fc250cd09de214b516e2b5574ff5/odoo/addons/university_isms/models/monitoring.py#L61).

Policy/risk/incident дээр owner эсвэл assignee бөглөгдсөн бол CISO fallback сонгогдохгүй. Тэр хүн архивлагдсан үед `_schedule_once` False буцааж, идэвхтэй CISO байхад ч сануулга үүсэхгүй. Тусдаа reviewer үүнийг гурван төрлийн бичлэг дээр санах ойн replay-аар давтав.

Засвар: хариуцагчийг сонгохдоо active хэрэглэгчээр шүүж, тохирох хүнгүй бол CISO руу шилжүүлнэ.

## F5 — P2: Бодлогын танилцалтын KPI-ийн хүртвэр, хуваарь өөр хэрэглэгчид тоолно

Эх: [odoo/addons/university_isms/models/monitoring.py:104](https://github.com/hex0tic/formula-university-odoo-isms/blob/da14a7f9f599fc250cd09de214b516e2b5574ff5/odoo/addons/university_isms/models/monitoring.py#L104); харуулах хэсэг [odoo/addons/university_isms/report/management_review.xml:78](https://github.com/hex0tic/formula-university-odoo-isms/blob/da14a7f9f599fc250cd09de214b516e2b5574ff5/odoo/addons/university_isms/report/management_review.xml#L78).

`users_internal` нь идэвхтэй дотоод хэрэглэгчдийг тоолно. `ack_users` нь архивлагдсан эсвэл энэ хүрээнд ороогүй хүний танилцалтыг хасахгүй. Хоёр танилцсан хэрэглэгчийн нэгийг архивлахад `2 / 1` гарч болно. Reviewer-ийн expression replay үүнийг батлав.

Засвар: current-version acknowledger-уудыг `internal_users`-тай огтлолцуулж ижил хамрах хүрээгээр тоолно.

## F6 — P2: Module upgrade monitoring cron-ийн локал тохиргоог дарна

Эх: [odoo/addons/university_isms/data/ir_cron_data.xml:2](https://github.com/hex0tic/formula-university-odoo-isms/blob/da14a7f9f599fc250cd09de214b516e2b5574ff5/odoo/addons/university_isms/data/ir_cron_data.xml#L2).

XML нь `noupdate` хамгаалалтгүйгээр `active=True`, interval=1 day гэж заана. Админ сануулгыг түр унтраасан эсвэл давтамжийг өөрчилсөн дараа модуль шинэчлэхэд уг тохиргоо дахин бичигдэнэ.

Засвар: эхний default cron-ийг `noupdate`-аар хадгалж, зориудын дараагийн тохиргооны өөрчлөлтийг тусдаа migration-аар удирдана.

## F7 — P2: Үндсэн DOCX/PDF/PPTX шинэ хэрэгжүүлэлттэй нийцээгүй

`reports/`-ийн эцсийн файлууд суурь commit-оос өөрчлөгдөөгүй. PDF-ийн 2, 20, 23, 27, 28-р хуудсанд 39 тестийн хуучин snapshot байна; DOCX-д 39 гэсэн тестийн дүн байгаа бөгөөд 47 байхгүй. Шинэ residual approval, monitoring, management review болон RBAC-ийн өөрчлөлт эцсийн материалд ороогүйг Deployment агент өөрөө `management/audit-20261118.md` §8, messages.md-д тэмдэглэсэн. Шинээр нэмсэн QWeb PDF-ууд эцсийн нэгдсэн тайланг орлохгүй.

Засвар: түүхэн 2026-11-16 snapshot-ийг хадгалж, 2026-11-18-ны шинэ тайлан/слайд дээр бодит өөрчлөлт, 47 тестийн нотолгоо, одоогийн инцидент/RTP төлөвийг ялгаж шинэчилнэ.

## Баталгаажуулалт ба хязгаар

- Эх runtime лог `odoo/logs/tests-isms_ci_20261118073432.log`-т `0 failed, 0 error(s) of 47 tests` байгааг бие даан уншиж баталгаажуулав. Энэ нь 2026-11-18 07:35:19 (Улаанбаатар)-ны өмнөх run; энэ review-ээр бүтэн багцыг дахин ажиллуулаагүй.
- 18 өөрчлөгдсөн Python файл AST parse, 9 XML файл parse, 1 shell файл `bash -n` шалгалт PASS. Reviewer мөн Compose YAML болон scoped diff/server-action syntax-ийг шалгасан.
- F1–F3: яг шалгасан эхээс AST-аар авсан өөрчлөгдөөгүй method-уудыг хөнгөн ORM stub-тай гүйцэтгэж давтав. Энэ нь нөхцөлт логикийн баталгаа; бүрэн Odoo integration тест биш. Үр дүн: `work/review-20261118/risk-method-checks.json`.
- F4–F5: reviewer-ийн тусдаа in-memory replay; F6: XML ба Odoo loader-ийн эх кодын шалгалт.
- Odoo 18-ийн upstream `addons/project/models/project_task_type.py` ба `project_task.py`-г GitHub API-аар уншиж fold/state ялгааг баталсан.
- 298 tracked файлыг локал 21 credential утга, түгээмэл GitHub token/private-key тэмдэглэгээтэй тулгахад тааралт олдоогүй. Энэ нь бүх боломжит нууцыг илрүүлэх иж бүрэн аудит биш.
- GitHub Actions run: 0. Хадгалсан локал тестийн нотолгоог CI-д ажилласан гэж үзээгүй.
- Репозиторын код, runtime DB, GitHub branch/visibility-г энэ review өөрчлөөгүй. Шалгалтын баримтыг үндсэн `biydaalt/management/` ба Codex `outputs/`-д хадгалав.
