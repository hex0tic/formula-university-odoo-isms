# Formula ERP: суулгалт, үйл ажиллагаа, нөөц ба rollback (REL-04, REL-05)

Огноо: 2026-11-26. Салбар: `formula-erp`. Суурь commit: `8e74051`.
Хамрах хүрээ: `odoo/` стек (Odoo 18.0 Community, PostgreSQL 16, Docker Compose), `odoo/addons/` дээрх 23 custom addon ба `formula_isms_copilot` (хөгжүүлэлт явагдаж байгаа, энэ баримтад тооцоогүй).

Энэ баримт нь production руу байрлуулах процедурыг **тайлбарлах** боловч **ажиллуулдаггүй**. Production (`orgil_isms`, `isms-odoo`, `isms-https`) энэ ажлын хүрээнд хөндөгдөөгүй. Production руу байрлуулах нь CISO-ийн тодорхой зөвшөөрөл шаардана.

Тэмдэглэгээ: **VERIFIED** (энэ ажлын хүрээнд ажиллуулж хэмжсэн), **NOT VERIFIED** (ажиллуулаагүй эсвэл боломжгүй), **PARTIAL**, **NOT RUN**.

Нууц мэдээлэл (нууц үг, OTP seed, API token, backup encryption key, `odoo.conf`-ийн утгууд) энэ баримтад байхгүй. Хувийн файлуудыг `<private stage config>`, `<private evidence>`, `<private backup key file>` гэж заасан.

---

## 1. Архитектур

| Бүрэлдэхүүн | Хэрэгжүүлэлт | Тайлбар |
| --- | --- | --- |
| Application | `odoo:18.0` image, container `isms-odoo` | Odoo HTTP `127.0.0.1:8069` (анхдагч). LAN горимд `scripts/start-lan.sh` нь private IPv4 дээр холбоно |
| Database | `postgres:16-alpine`, container `isms-db`, `jit=off` | Нэг DB: `orgil_isms` (production). Filestore `/var/lib/odoo/filestore/<db>` |
| TLS (LAN) | `nginx:1.30.5-alpine3.24`, container `isms-https`, `docker-compose.https.yml` | Port 8443. Сертификатын файлууд `evidence/private/tls/` дотор, repo-д байхгүй |
| RTC | `coturn`, container `isms-turn`, host network | Odoo Discuss-ийн WebRTC relay. Тохиргоо `evidence/private/turn/` дотор |
| Network | `isms-net` (bridge) | PostgreSQL хост порт нээхгүй |
| Config | `odoo/config/odoo.conf.template` ба `scripts/setup.sh` үүсгэнэ | `odoo.conf` git-д орохгүй. `max_cron_threads = 1` (production), `workers = 0` |

Production тохиргооны онцлог: `list_db = False`, `dbfilter = ^orgil_isms$`, `without_demo = all`, `proxy_mode = False`.

### 1.1 Модулийн хамаарлын график (текст)

Тэмдэглэл: сумын оронд хамаарлыг "дээр нь суурилна" хэлбэрээр заасан. Доод түвшний модуль нь дээд түвшнээс хамаарахгүй.

```
Суурь (Odoo core ба OCA):  base, web, mail, hr, project, portal, stock, auth_totp, helpdesk_mgmt (OCA)

[Түвшин 1] university_isms                  deps: base, mail, hr, project
   |                                          Хөрөнгө, эрсдэл, хяналт, бодлого, инцидент, аудит лог
   +-- university_isms_capa                 deps: mail, university_isms
   |      +-- university_isms_monitoring_plus   deps: university_isms_capa
   |             +-- university_isms_audit_chain   deps: university_isms, university_isms_monitoring_plus
   +-- university_isms_evidence             deps: university_isms
   +-- university_isms_stock                deps: university_isms, stock
   |      +-- university_isms_inventory_catalog deps: university_isms_stock
   +-- university_isms_helpdesk             deps: university_isms, helpdesk_mgmt (OCA)
   +-- university_access_review             deps: base, mail, hr, project, university_isms
   |      +-- university_access_governance    deps: ..., university_isms, university_access_review
   |      +-- university_mfa_policy           deps: auth_totp, university_isms, campus_university, university_access_review
   +-- university_security_tests            deps: university_isms, campus_university, university_access_review (тест модуль)

[Түвшин 1] campus_university                deps: base, mail  (хөтөлбөр, оюутан, хичээл, дүн, дүнгийн засварын урсгал)
   +-- campus_isms_bridge                   deps: campus_university, university_isms
   +-- campus_academic_plus                 deps: campus_university
   |      +-- campus_portal                 deps: campus_university, campus_academic_plus, portal, web
   +-- formula_grade_studio                 deps: campus_isms_bridge
   +-- formula_integration_hub              deps: base, mail, campus_university, university_isms

[UI] formula_design_system                  deps: web (токен, фонт, dark/light CSS)
[UI] formula_command_center                 deps: web, university_isms, project
[UI] formula_incident_console               deps: web, university_isms
[UI] formula_control_explorer               deps: web, university_isms

[Тусгаарлагдсан] campus_rtc_fix             deps: mail (WebRTC init засвар)
[Хөгжүүлэлт] formula_isms_copilot           (хэрэгжилт явагдаж байна, суулгаагүй)
```

Гол хамаарлын дүрэм:
- `university_isms` нь ISMS-ийн өгөгдлийн эзэн. Бусад ISMS модуль нь түүн дээр нэмэлт хүснэгт, view, cron нэмнэ.
- Campus ба ISMS-ийн хооронд зөвхөн `campus_isms_bridge` ба `formula_integration_hub` холбоно.
- UI модулиуд (`formula_command_center`, `formula_incident_console`, `formula_grade_studio`, `formula_control_explorer`) нь өөрийн бизнес логикгүй. Бүх төлөвийн шилжилт нь суурь модулийн `action_*` методоор явна.
- `formula_integration_hub` нь `university_isms_audit_chain`-аас хамааралгүй (INTEGRATIONS.md).

### 1.2 Модулийн жагсаалт ба хувилбар (staging, 2026-11-26)

| Модуль | Хувилбар | Лиценз | Тайлбар |
| --- | --- | --- | --- |
| university_isms | 18.0.1.1.0 | LGPL-3 | Суурь ISMS, app |
| university_isms_capa | 18.0.1.0.0 | LGPL-3 | Олдвор, CAPA, эрсдэлийн зөвшөөрөл |
| university_isms_monitoring_plus | 18.0.1.0.0 | LGPL-3 | Хяналтын тест |
| university_isms_audit_chain | 18.0.1.0.0 | LGPL-3 | Аудит гинж, trigger, forward |
| university_isms_evidence | 18.0.1.0.0 | LGPL-3 | Нотлох баримт, attestation, export |
| university_isms_stock | 18.0.1.1.0 | LGPL-3 | Inventory холболт |
| university_isms_inventory_catalog | 18.0.1.1.0 | AGPL-3 | Inventory catalog |
| university_isms_helpdesk | 18.0.1.0.0 | AGPL-3 | Incident-Helpdesk холбоо |
| university_access_review | 18.0.1.1.0 | LGPL-3 | Модел бүрийн эрхийн тойм |
| university_access_governance | 18.0.1.0.0 | LGPL-3 | Кампанит ажил, түр/давуу эрх |
| university_mfa_policy | 18.0.1.0.0 | AGPL-3 | Step-up MFA |
| university_security_tests | 18.0.1.0.0 | AGPL-3 | 22 халдлагын регресс тест (тест модуль) |
| campus_university | 18.0.1.0.0 | AGPL-3 | Campus суурь |
| campus_isms_bridge | 18.0.1.1.0 | AGPL-3 | Campus-ISMS аудит холбоо |
| campus_academic_plus | 18.0.1.0.0 | AGPL-3 | Бүртгэл, ирц, GPA, хуваарь |
| campus_portal | 18.0.1.0.0 | AGPL-3 | Оюутан, багшийн портал |
| campus_rtc_fix | 18.0.1.0.0 | AGPL-3 | Discuss WebRTC засвар |
| formula_design_system | 18.0.1.0.0 | LGPL-3 | UI токен, тема |
| formula_command_center | 18.0.1.0.0 | LGPL-3 | Dashboard |
| formula_incident_console | 18.0.1.0.0 | LGPL-3 | Инцидентийн дараалал |
| formula_grade_studio | 18.0.1.0.0 | AGPL-3 | Дүнгийн засварын хяналт |
| formula_control_explorer | 18.0.1.0.0 | LGPL-3 | Annex A хайлт |
| formula_integration_hub | 18.0.1.0.0 | AGPL-3 | Интеграцийн framework (бүгд идэвхгүй анхдагчаар) |
| helpdesk_mgmt | 18.0.1.19.5 | AGPL-3 | OCA, гадны модуль (өөрчлөөгүй) |

---

## 2. Суулгах дараалал

Анхны суулгалт (шинэ хост):

1. `odoo/scripts/setup.sh`: `.env` (санамсаргүй нууц үг), `config/odoo.conf`, data хавтас үүсгэнэ. `.env` ба `odoo.conf` нь git-д орохгүй.
2. `docker compose up -d`: `isms-db` эрүүл болтол хүлээнэ (healthcheck).
3. `odoo/scripts/init-db.sh`: `orgil_isms` DB үүсгэж `base, web, mail, hr, project, auth_totp, auth_password_policy` суулгана, `mn_MN`, demo өгөгдөлгүй.
4. `odoo/scripts/odoo-cli.sh -i university_isms,university_isms_capa,university_isms_monitoring_plus,university_isms_audit_chain,university_isms_evidence,university_access_review,university_access_governance,university_mfa_policy,campus_university,campus_isms_bridge,campus_academic_plus,campus_portal,campus_rtc_fix,university_isms_stock,university_isms_inventory_catalog,university_isms_helpdesk,formula_design_system,formula_command_center,formula_incident_console,formula_control_explorer,formula_grade_studio,formula_integration_hub`
   Dependency-ийг Odoo автоматаар суулгана. `university_security_tests` нь зөвхөн тест орчинд суулгана.
5. `odoo/scripts/odoo-shell.sh scripts/bootstrap.py`: компанийн суурь тохиргоо, admin-ийн нууц үгийг `.env`-ийн санамсаргүй утгаар солино. Нэг удаа ажиллуулна (дахин ажиллуулахад аюулгүй гэж скриптэд бичсэн).
6. Бодит өгөгдөл: `odoo/scripts/odoo-shell.sh scripts/import_case_data.py` нь CSV-ээс upsert хийнэ. Шинэ хэрэглэгчийн нууц үг **stdout-д биш**, `evidence/private/` доорх файлд бичигдэнэ. Тэр файлыг хувийн мэдээллийн адил хадгална.
7. `odoo/scripts/run-tests.sh`: түр DB дээр тест ажиллуулж, дараа нь устгана. Ашиглалтын DB-д хүрэхгүй.

Шинэчлэлт (upgrade): `odoo/scripts/odoo-cli.sh -u <модулийн жагсаалт>`. Скрипт нь `runtime.lock` авч, web контейнерийг түр зогсооно, дуусмагц эхлүүлнэ. Лог `logs/cli-*.log` дотор.

---

## 3. Тохиргооны параметрүүд (`ir.config_parameter`)

Бүх түлхүүрийг кодоос шууд хайж баталсан. Утгыг `Settings > Technical > Parameters > System Parameters` дээр харна. Нууц утгыг UI-д харуулахгүй, лог-д бичихгүй.

| Түлхүүр | Модуль | Анхдагч | Тайлбар |
| --- | --- | --- | --- |
| `university_isms.bruteforce_threshold` | university_isms | 5 | window дотор амжилтгүй нэвтрэлтийн тоо, хүрвэл автомат инцидент (A.8.16) |
| `university_isms.bruteforce_window_minutes` | university_isms | 15 | Тоолох цонх, минут |
| `university_mfa_policy.enforce_date` | university_mfa_policy | хоосон | `YYYY-MM-DD`. Хоосон бол зөвхөн сануулга. Огнооноос хойш step-up хориг идэвхжинэ (5-р хэсэг) |
| `university_access_governance.min_justification_length` | university_access_governance | 20 | Хүсэлтийн үндэслэлийн доод урт (тэмдэгт) |
| `university_access_governance.max_privileged_days` | university_access_governance | 7 | Давуу эрхийн хүсэлтийн дээд хугацаа, хоног |
| `university_access_governance.max_temporary_days` | university_access_governance | 30 | Түр эрхийн дээд хугацаа, хоног |
| `university_isms_monitoring_plus.max_privileged_admins` | university_isms_monitoring_plus | 2 | Settings ба Access Rights-ийн давуу эрхтний босго |
| `university_isms_monitoring_plus.max_inactive_days` | university_isms_monitoring_plus | 90 | Давуу эрхтэн удаан нэвтрээгүй гэж тооцох хоног |
| `university_isms_audit_chain.file_path` | university_isms_audit_chain | хоосон (идэвхгүй) | Гинжийн JSONL файлын абсолют зам (гадаад анкер) |
| `university_isms_audit_chain.http_url` | university_isms_audit_chain | хоосон (идэвхгүй) | Гинжийн https endpoint. `http://` зөвхөн `allow_insecure_http` тохируулсан үед |
| `university_isms_audit_chain.http_token` | university_isms_audit_chain | хоосон | **Нууц.** Bearer token. Хэзээ ч лог, UI-д гаргахгүй |
| `university_isms_audit_chain.allow_insecure_http` | university_isms_audit_chain | хоосон | `1` бол http-г зөвшөөрнө. Production-д тавихгүй |
| `university_isms_audit_chain.http_timeout` | university_isms_audit_chain | 10 | Секунд |
| `university_isms_audit_chain.http_max_retries` | university_isms_audit_chain | 3 | |
| `university_isms_audit_chain.http_backoff_seconds` | university_isms_audit_chain | 2 | |
| `university_isms_audit_chain.batch_size` | university_isms_audit_chain | 500 | Багцын бичлэгийн тоо |
| `university_isms_audit_chain.max_batches_per_run` | university_isms_audit_chain | 10 | Нэг cron run-д дээд багц |
| `university_isms_audit_chain.max_attempts` | university_isms_audit_chain | 50 | Багц бүрийн дээд оролдлого |
| `university_isms_audit_chain.retention_days` | university_isms_audit_chain | 365 | Илгээгдсэн дарааллын мөрийг устгах хугацаа. `0` бол хадгална. **Аудит бичлэгийг устгахгүй** |
| `university_isms_audit_chain.ip_hmac_key` | university_isms_audit_chain | автомат үүснэ | **Нууц.** IP-г HMAC-аар нууцлахад. Анх ашиглахад DB-д үүснэ |
| `formula_integration_hub.api_rate_capacity` | formula_integration_hub | 60 | API token bucket багтаамж, процесс бүрт |
| `formula_integration_hub.api_rate_per_minute` | formula_integration_hub | 60 | Минутад нэмэгдэх хүсэлт |
| `formula_integration_hub.pseudonym_key` | formula_integration_hub | автомат үүснэ | **Нууц.** SIEM payload-ийн pseudonym түлхүүр |

Интеграцийн нууцууд (`formula.integration.endpoint`):
- `secret_key` нь нууцын **нэр** (ir.config_parameter түлхүүр эсвэл орчны хувьсагчийн нэр). Нууцын утгыг бичлэгт хадгалахгүй.
- `secret_source = param` эсвэл `env`. `env` сонгосон бол утгыг container-ийн орчноос уншина.
- `enabled` анхдагчаар унтраалттай. Endpoint бүрийг тусад нь асаана.

---

## 4. Cron ажлууд

Бүгд `active` (анхдагч). Production-д `max_cron_threads = 1`. Staging-д `max_cron_threads = 0` (cron ажиллахгүй).

| Нэр | Модуль | Давтамж | Метод | Тайлбар |
| --- | --- | --- | --- | --- |
| ISMS: өдөр тутмын мониторинг | university_isms | 1 өдөр | `_cron_daily_monitoring` | Бодлогын хяналт, хугацаа хэтэрсэн эрсдэл, SLA |
| ISMS: эрсдлийн зөвшөөрлийн хугацаа дуусалт | university_isms_capa | 1 өдөр | `_cron_expire_waivers` | Хугацаа дууссан waiver |
| ISMS: хяналтын автомат тестүүд | university_isms_monitoring_plus | 1 цаг | `_run_due_plans` | Товлосон тестийн төлөвлөгөө. Давхар ажиллахгүй |
| ISMS: бодлогын баталгаажуулалтын хугацаа дуусгах | university_isms_evidence | 1 өдөр | `_cron_expire_attestations` | Хугацаа дууссан attestation |
| ISMS: аудит гинжийн дамжуулалт | university_isms_audit_chain | 15 минут | `_cron_forward_chain` | Гинжийн багцыг файл/HTTP руу илгээх, `_purge_sent` |
| Эрхийн тойм: дараагийн кампанит ажил | university_access_governance | 1 өдөр | `_cron_create_recurring` | Давтамжтай кампанит ажил үүсгэх |
| Эрхийн тойм: хугацаа хэтэрсөн мөр | university_access_governance | 1 өдөр | `_cron_escalate_overdue` | Хугацаа хэтэрсэн мөрийг escalate |
| Түр эрх: идэвхжүүлэх/хасах | university_access_governance | 1 цаг | `_cron_process_grants` | Батлагдсаныг идэвхжүүлж, хугацаа дууссаныг хасна. Зөвхөн нэмсэн бүлгийг хасна |
| Интеграц: outbox dispatcher | formula_integration_hub | 5 минут | `_cron_dispatch` | Гаралтын дараалал, batch 100, retry |

Cron алдаа нь тусдаа log бичлэг үүсгэнэ. Өдөр тутмын шалгалт: `Мониторинг одоо шалгах` ба `Аудит гинж` цэс.

---

## 5. MFA нэвтрүүлэх төлөвлөгөө (SEC-01)

Зарчим: MFA нь нэвтрэлтийг хаахгүй. Хориг нь зөвхөн **step-up** үйлдлүүдэд хамаарна.

| Үе | Юу хийх | Хариуцагч |
| --- | --- | --- |
| 0. Одоогийн байдал | `enforce_date` хоосон. Зөвхөн сануулга гарна. Staging дээр 4 давуу эрхтэн бүгд TOTP-гүй (FND-2026-0002) | CISO |
| 1. Тооллого | `Давуу эрхийн тайлан` (GOV-04) ба `MFA: давуу эрхтэй хэрэглэгчид TOTP` тестийг ажиллуулах. Жагсаалтыг CISO-д өгөх | Аюулгүйн админ |
| 2. Бүртгэл | Давуу эрхтэн өөрөө TOTP идэвхжүүлнэ. Админ seed-ийг хараахгүй, хуулахгүй | Давуу эрхтэн |
| 3. Мэдэгдэл | Огноог ядаж 14 хоногийн өмнө мэдэгдэнэ (зөвлөмж, системийн шаардлага биш). Хэнд нөлөөлөх, аль үйлдэл хаагдахыг тодорхой бичнэ | CISO |
| 4. Огноо тавих | `enforce_date = YYYY-MM-DD` (ir.config_parameter). Өөрчлөлт аудит лог дээр бүртгэгдэнэ | Системийн админ, CISO-ийн зөвшөөрлөөр |
| 5. Огноо | Өнөөдрөөс хойш TOTP-гүй давуу эрхтэн дараах үйлдэлд хориг авна: бодлого батлах, зөрчил хаах, эрсдэл хүлээн зөвшөөрөх, дүн батлах, эрх өөрчлөх. Нэвтрэлт үргэлж нээлттэй | Автомат |
| 6. Хяналт | `A.8.5` тест болон олдворын тоог өдөр бүр шалгах. FAIL бол CAPA нээх | Аудитор |
| Буцаах | `enforce_date`-ийг хоосон болгоход зөвхөн сануулга руу буцна. Үүнийг бичлэгт тэмдэглэнэ | CISO |

Тэмдэглэл: 2026-11-26-ны байдлаар `enforce_date` тохируулаагүй. Огноог тавих шийдвэр нь хэрэглэгчийн (CISO) шийдвэр, энэ баримтад үүнийг тохируулаагүй.

---

## 6. Аудит гинжийн trigger ба устгах асуудал (SEC-02)

1. `isms_audit_log` дээр trigger нь `UPDATE`, `DELETE`, `TRUNCATE`-ийг татгалзана (`isms_audit_log_chain_guard`). Backfill нь зөвхөн гинжид ороогүй мөрийн `seq`-ийг өөрчлөх зөвшөөрөлтэй, агуулга өөрчлөгдөхгүй.
2. **Хэрэглэгчийг устгахгүй, архивлана.** Аудит бичлэгтэй хэрэглэгчийг устгавал `ondelete` нь UPDATE хийх гэж оролдож trigger татгалзана. Хэрэглэгчийг `active = False` болгож архивлана. Хэрэглэгчийн бүртгэлийг шууд устгахыг хориглоно.
3. Модуль `university_isms_audit_chain`-ийг uninstall хийвэл `uninstall_hook` нь trigger болон функцийг устгана. Аудит мөрүүд үлдэнэ, гэвч хамгаалалт алга болно. Production-д uninstall хийхгүй. Шаардлагатай бол CISO-ийн зөвшөөрөлтэй, өмнө нь бэлэн backup дээр хийнэ.
4. PostgreSQL superuser (`odoo` роль) trigger-ийг `DISABLE TRIGGER`-ээр унтраах боломжтой. Энэ нь **defense-in-depth**, tamper-evidence биш. Tamper-evidence нь hash гинж + гадаад анкер (`file_path` эсвэл `http_url`-ээр илгээсэн толгой хэш) юм. Гадаад анкерыг DB-ээс гадуур хадгална.
5. `ip_hmac_key` нь DB дотор байдаг тул DB админ IP-г тооцоолж чадна (хязгаарлалт).
6. Гинжийн шалгалт: `isms.audit.log._verify_chain()` (`Гинжийн төлөв` цэс). Staging дээр 653 бичлэгийг бүтнээр шалгаж `ok: True` (REL-04).

---

## 7. Pre-deploy backup ба нөөц (SEC-03, REL-04)

### 7.1 Backup

`odoo/scripts/backup/backup.sh` нь PostgreSQL `pg_dump -Fc` + filestore tar + SHA-256 manifest + AES-256-CBC (PBKDF2, 310000 iter) шифрлэлт гүйцэтгэнэ. Гүйцэтгэлийн орчин: container `isms-db`, `isms-odoo`.

Production (**ажиллуулаагүй**, загвар):

```
ISMS_DB_NAME=orgil_isms ISMS_DB_CONTAINER=isms-db ISMS_DB_USER=odoo \
ISMS_ODOO_CONTAINER=isms-odoo \
ISMS_BACKUP_ROOT=<backup root outside repository> \
ISMS_BACKUP_COPY_DIRS=<second local or mounted offsite dir> \
ISMS_BACKUP_KEY_FILE=<key file, mode 0400 or 0600> \
odoo/scripts/backup/backup.sh
```

Exit code: `0` амжилт, `13` хуулбар алдаатай (анхдагч нөөц бүрэн). `13` бол incident нээнэ.

Backup-ийн дүрэм:
- `ISMS_BACKUP_ROOT` нь repository-ийн гадна байх ёстой (скрипт шалгана).
- Key file-ийг repository-д хадгалахгүй. Түлхүүрийг хоёр байршилд (тусдаа) нөөцлөх ёстой. **Энэ нь NOT VERIFIED**: одоогийн хост дээр нэг л хуулбар байгаа.
- Cron ажиллуулах нь **NOT INSTALLED**. RPO-ийн график хүрээ NOT VERIFIED.

### 7.2 Restore verification

`odoo/scripts/backup/restore_verify.sh --latest-from <root> --db orgil_isms --target-db isms_restore_verify_<нэр>` нь:
- Хадгалсан файлын hash, decrypt, plaintext hash-ийг шалгана.
- Тусдаа DB (`isms_restore_verify_*` хэлбэр) болон filestore руу сэргээнэ.
- Модулийн жагсаалт, 21 хүснэгтийн мөрийн тоо, `ir_attachment` файлуудын SHA-1-ийг шалгана.
- Тайлан JSON (`--report`), RTO, RPO-ийг хэмжинэ. Дараа нь DB болон filestore-ийг устгана (`--keep` бол үлдээнэ).

Скрипт нь `orgil_isms`, эх DB-ийн нэр, одоо байгаа DB-ийн нэрийг татгалзана (хамгаалалт).

---

## 8. Байрлуулах процедур (production, ЗӨВХӨН ЗӨВШӨӨРЛИЙН ДАРАА)

Энэ хэсэг нь **процедур**. Энэ баримтын хүрээнд ажиллуулаагүй. Эхлэхийн өмнө: CISO-ийн бичгэн зөвшөөрөл, засвар үйлчилгээний цонх, Бүртгэлтэй хэрэглэгчдэд мэдэгдэл.

Урьдчилсан нөхцөл:
- Staging дээр ижил commit-оор REL-04-ийн бүх алхмыг давсан байх.
- Deploy checkout дээр `git status` цэвэр. Commit hash-ийг бичнэ.
- `odoo/addons/` модулийн агуулгын hash-ийг бичнэ (7.3-т тайлбарласан).

Алхамууд:
1. **Тэмдэглэл.** `git rev-parse HEAD` ба addons хавтасны hash (`find ... | sort | xargs sha256sum | sha256sum`).
2. **Pre-deploy backup.** 7.1-ийн production команд. Exit 0 шаардлагатай. Backup-ийн директорийн нэрийг тэмдэглэнэ.
3. **Backup-ийг шалгах.** `restore_verify.sh` тусдаа DB дээр ажиллуулна. `modules_match`, `counts_match`, `attachments_ok` бүгд `true` байх ёстой.
4. **Web-ийг зогсоох.** `docker compose stop odoo`.
5. **Код шинэчлэх.** `git pull --ff-only` (force push, rebase хориглоно). Шинэ commit-ийн hash-ийг шалгана.
6. **Upgrade.** `odoo/scripts/odoo-cli.sh -u <суулгасан custom модулиудын жагсаалт>`. `helpdesk_mgmt` (OCA)-ийг тусад нь, хувилбар өөрчлөгдсөн үед л. Лог дахь `ERROR`, `CRITICAL`, `Traceback`, `invalid module names` мөрийг шалгана.
7. **Баталгаажуулалт (read-only).** `ir_module_module` дээр `state = 'installed'` ба `latest_version` манифесттэй таарах эсэх. `to upgrade` төлөв үлдсэн бол алдаа.
8. **Web-ийг эхлүүлэх.** `docker compose start odoo`.
9. **Smoke тест** (доорх 8.1).
10. **24 цагийн ажиглалт.** Cron лог, SIEM outbox, аудит гинжийн forward төлөв, Command Center KPI.

### 8.1 Smoke тест (production, хүний шалгалт)

- `/web/login?db=orgil_isms` 200. Admin-аар нэвтрэх, MFA сануулга гарч байгаа эсэх.
- Command Center, Incident Console, Control Explorer (93 хяналт) нээгдэх.
- Оюутны бүртгэлээр `/my/campus` нээгдэх, өөрийн мөр л харагдах (IDOR-ийн эсрэг шалгалт).
- Багшийн портал: өөрийн хичээл л харагдах.
- `Гинжийн төлөв`: `ok` ба сүүлийн `seq` өсч байгаа.
- Cron-ууд `active`, сүүлийн run-ийн алдаагүй.

Staging дээрх security тест (`university_security_tests`, 22 тест) нь ижил commit дээр PASS байх ёстой. Production DB дээр тест ажиллуулахгүй.

### 8.2 Upgrade-ийн дэс дараалал

`-u` жагсаалт нь суулгасан модулийн дараалалд нөлөөлнө. Dependency-ийг Odoo өөрөө эрэмбэлнэ. Хуучин модулийн хувилбарыг `-u` нь өөрчлөхгүй, зөвхөн `latest_version` өөрчлөгдсөн модулийн migration ажиллана.

---

## 9. Rollback

Нөхцөл: upgrade эсвэл smoke тест алдаатай бол.

1. `docker compose stop odoo`.
2. Өмнөх commit руу буцах (`git checkout <өмнөх hash>` биш, `git revert` эсвэл deployment checkout-ийг өмнөх tag руу ff-only-оор буцаах).
3. Pre-deploy backup-аас шинэ DB-д сэргээх: `restore_verify.sh --backup-dir <backup> --target-db isms_restore_verify_<rollback>` (скрипт зөвхөн энэ нэрийг зөвшөөрнө).
4. Сэргээсэн DB-ийг `isms-odoo`-д холбох (`dbfilter` солих) нь **CISO-ийн зөвшөөрөлтэй** (DR_RUNBOOK.md 4-р хэсэг). Энэ алхам **NOT VERIFIED** (production-д хэмжээгүй).
5. Web-ийг эхлүүлж, smoke тест давтах.
6. Data loss цонх (backup-ийн үеэс эхлэн) бичнэ.

REL-04 дээрх хэмжилт (throwaway, 4-р хэсгийн доорх 10-р хэсэг): restore ~52 секунд.

---

## 10. Мониторинг

| Юу | Хаана | Хэн | Алдааны нөхцөл |
| --- | --- | --- | --- |
| Backup exit code, сүүлийн `COMPLETE` директор | host | Operator | Exit 0-ээс бусад, эсвэл 24 цагаас хуучин |
| Odoo алдаа | `logs/odoo.log` (container `/var/log/odoo/odoo.log`) | Operator | `ERROR`, `CRITICAL` |
| Cron алдаа | Odoo лог, `_logger.exception` | Operator | Traceback |
| Аудит гинж | `Гинжийн төлөв`, `audit_chain_integrity` тест | Аудитор | `ok: False` |
| Аудит forward дараалал | `Дамжуулалтын дараалал` | Аудитор | `failed` төлөв |
| SIEM / интеграцийн outbox | `Гаралтын дараалал` | Admin | `failed`, `dead` |
| Давуу эрх | `Давуу эрхийн тайлан` | CISO | Босго, TOTP-гүй |
| Хөрөнгийн зай | host | Operator | `/home` 96%, `/var/lib/postgresql/data` 90% (2026-11-26 хэмжилт) |

Хост дээрх диск: 2026-11-26-ны хэмжилтээр `/home` 96% (16 GB чөлөөтэй), PostgreSQL data 90% (14.5 GB чөлөөтэй). Энэ нь backup, upgrade-ийн эрсдэл. Production байрлуулахаас өмнө диск чөлөөлөх шаардлагатай.

---

## 11. Мэдэгдэж буй хязгаарлалт

| # | Хязгаарлалт | Төлөв |
| --- | --- | --- |
| 1 | Production (`orgil_isms`) шинэ addon-оор шинэчлэгдээгүй. Staging дээр л ажиллуулсан | Байрлуулаагүй |
| 2 | Backup-ийн cron суулгаагүй. RPO-ийн график хүрээ тогтоогдоогүй | NOT VERIFIED |
| 3 | Offsite host, rsync-over-ssh (sshd ажиллахгүй). Remote retention код бичигдсэн, ажиллаагүй | NOT VERIFIED |
| 4 | WORM / object lock / `chattr +i` (root эрх шаардлагатай) | NOT VERIFIED |
| 5 | Backup key-ийн нөөц, эргүүлэлт | NOT VERIFIED (нэг хуулбар) |
| 6 | Restore-ийг Odoo вэб (login, attachment UI) дээр бүтнээр шалгаагүй. ORM түвшний шалгалт хийсэн | PARTIAL |
| 7 | Migration дундуур алдаа гарсан үеийн хагас шинэчлэгдсэн DB (partial upgrade) | NOT VERIFIED |
| 8 | Аудит лог: PostgreSQL superuser trigger-ийг унтрааж чадна. Гадаад анкер тохируулагдаагүй | Defense-in-depth, tamper-evidence биш |
| 9 | Хэрэглэгчийн устгал аудит бичлэгтэй үед татгалзана (архивлах шаардлагатай) | Үйл ажиллагааны дүрэм |
| 10 | `enforce_date` тохируулаагүй. Step-up MFA-ийн хориг идэвхгүй | Шийдвэр хүлээгдэж байна |
| 11 | Интеграц: IdP (OIDC), Moodle, SMTP, SIEM хүлээн авагч бодитоор холбогдоогүй | NOT VERIFIED (INTEGRATIONS.md) |
| 12 | `/api/formula/v1/...` HTTP routing төгсгөл хүртэл (бодит сервер, Bearer header) | NOT VERIFIED |
| 13 | Rate limit нь процесс бүрт; олон worker дээр нийт хязгаар биш | Хязгаарлалт |
| 14 | `-u` дээр буруу модулийн нэр өгөхөд `invalid module names, ignored` анхааруулга гарч exit code `0` байна | Операторын шалгалт шаардлагатай (8-р алхам) |
| 15 | Upgrade-ийн анхааруулга: `university_access_review` (`channel_line_ids`, `channel_summary` "Чат"), `university_isms_stock` (`isms_asset_count`, `isms_asset_ids` "ISMS хөрөнгө") дээр талбарын нэр давхцсан. Функцэд нөлөөгүй, харагдах байдал муу | Засвар хүлээгдэж байна |
| 16 | Staging DB live ашиглагдаж байна. `isms_audit_log` нөөцийн үед 653 байсан, туршилтын дараа 701 болсон (өөр ажлын бичилт). REL-04 туршилт staging дээр бичилт хийгээгүй | Тэмдэглэл |
| 17 | Helpdesk холбоотой incident-ийн нууцлал, `campus_isms_bridge`-ийн тест security suite-д байхгүй | NOT VERIFIED |
| 18 | `formula_isms_copilot` хөгжүүлэлт дутуу, энэ баримтад суулгаагүй | Хэрэгжилт явагдаж байна |
| 19 | Login форм дээрх rate limit тусгайлан шалгагдаагүй. Brute-force инцидент (босго 5, 15 минут) л бүртгэдэг | NOT VERIFIED |
| 20 | Мэдээллийн найдвартай устгал (secure erase) backup болон filestore-д байхгүй | NOT VERIFIED |

---

## 12. REL-04 нотолгоо: throwaway DB дээрх туршилт

Туршилтын орчин: staging. Эх DB `orgil_isms_stage`, container `isms-db` ба `isms-stage-odoo`, volume `isms-stage-data`. Production (`orgil_isms`, `isms-odoo`, `isms-https`) хөндөгдөөгүй. `orgil_isms_stage`-ийг өөрчлөөгүй: зөвхөн `pg_dump` ба filestore унших үйлдэл хийсэн.

Тусгаарлалтын шинж:
- Одоо ажиллаж буй staging web container (`isms-stage-odoo`) дахин эхлээгүй.
- Бүх one-off container `max_cron_threads = 0` тохиргоотой тул cron ажиллаагүй.
- Upgrade нь repo-ийн ажлын хуулбарын **snapshot** дээр ажилласан (хөгжүүлэлт явагдаж байгаа тул). Snapshot-ийн агуулгын hash: `77fb234fc5017917c5df950483b076c6f6ca5378714f02e1207d18e770ef001b` (`*.py`, `*.xml`, `*.csv`, `__manifest__.py` файлуудын sha256 жагсаалтын hash). Commit: `8e74051`.

Нууц мэдээлэл: `<private stage config>` mount хийгдсэн, утгыг хэвлээгүй. Backup encryption key `<private backup key file>` (0600), утгыг хэвлээгүй.

### 12.1 Бүртгэл

| # | Алхам | Үр дүн | Хугацаа (wall) | Тайлбар |
| --- | --- | --- | --- | --- |
| R1 | `backup.sh` (эх: `orgil_isms_stage`), upgrade-ийн **өмнөх** нөөц | exit 0. 75 суулгасан модуль, dump 5 134 052 байт, filestore 15 609 745 байт (460 entry). Шифрлэгдсэн | 7.4 s | Энэ нөөц нь rollback-ийн эх |
| R2 | `restore_verify.sh --backup-dir <R1> --target-db isms_restore_verify_rel04a --keep` | VERIFIED. Модуль таарсан, 21 хүснэгт 0 зөрүү, attachment 216 шалгагдсан, 0 алдаа (1 мөр store файлгүй, DB-д л байгаа) | 57.6 s | `restore_seconds` 55.67, `verify_seconds` 1.11, RTO 56.79 s, RPO observed 60 s |
| R3 | Бүх custom addon-ийн `-u` (23 модуль, `helpdesk_mgmt` оруулаагүй) | exit 0. 75 модуль ачаалагдсан. ERROR-оор бичигдсэн зүйл нь docutils-ийн модулийн тайлбарын RST анхааруулга (ачаалалтад нөлөөгүй). Талбарын давхцсан нэрийн анхааруулга 2 (тайлбар 15) | 27.1 s | Хувилбарууд өөрчлөгдөөгүй (migration шаардаагүй). `formula_isms_copilot` суулгаагүй тул алгассан |
| R4 | 7 UI модулийн `button_immediate_uninstall` | Амжилттай. 6 ISMS/campus хүснэгтийн мөрийн тоо ба md5 өөрчлөгдөөгүй. Аудит гинж `ok: True`, 653 шалгагдсан | 4.9 s | Хамааралтай бусад модуль зөрөөгүй |
| R5 | 7 UI модулийг дахин суулгах (`button_immediate_install`) | Амжилттай. Бүх хүснэгт өмнөхтэй яг ижил md5. Гинж `ok: True`, 653 | 6.7 s | |
| R6 | Алдаатай upgrade: `university_isms_capa/__init__.py`-д синтакс алдаа оруулсан хуулбар дээр бүх жагсаалтын `-u` | exit 255. `Couldn't load module university_isms_capa` (SyntaxError), `Failed to load registry`. Модулийн төлөв өөрчлөгдөөгүй (алдаа ачаалалтын үед, DB бичилтээс өмнө) | ~10 s | Алдааны мөр: 13:05:55 эхэлж, 13:06:06 унасан |
| R7 | R6-ийн дараах DB-ийн хэрэглээний шалгалт (read-only ORM probe) | DB ажиллаж байна: `isms_asset` 16, `isms_audit_log` 653, гинж `ok: True`. `to upgrade` төлөвтэй модуль байхгүй | ~10 s | |
| R8 | `-u no_such_module_rel04` | exit 0, `invalid module names, ignored` WARNING. Ямар ч upgrade хийгдээгүй | ~10 s | Анхааруулах хэрэгтэй (11-р хязгаарлалт 14) |
| R9 | Rollback rehearsal: R1 нөөцөөс `isms_restore_verify_rel04b` руу сэргээх | VERIFIED. Модуль, хүснэгт, attachment бүгд таарсан | 51.9 s RTO | `pg_restore` 49.6 s, filestore 0.7 s, verify 1.15 s |
| R10 | Rollback DB-ийн ORM probe | `isms_asset` 16, `isms_audit_log` 653, гинж `ok: True` | ~10 s | |
| R11 | Цэвэрлэгээ | `isms_restore_verify_rel04a`, `isms_restore_verify_rel04b` DB-г `dropdb`, filestore директорийг `rm -rf`. `pg_database` жагсаалтад зөвхөн `orgil_isms`, `orgil_isms_stage`, `postgres`, `template0/1` үлдсэн | — | Тэмдэглэл: `isms_audit_log` нөөцийн үед 653 мөр, туршилтын дараа дахин уншихад 701 мөр (staging live ашиглагдаж байна). Туршилт staging-д бичилт хийгээгүй |

### 12.2 Командууд (нууц ба хувийн замыг placeholder-оор солисон)

```
# R1 Нөөц (эх: staging, шифрлэгдсэн)
ISMS_DB_NAME=orgil_isms_stage ISMS_DB_CONTAINER=isms-db ISMS_DB_USER=odoo \
ISMS_ODOO_CONTAINER=isms-stage-odoo ISMS_BACKUP_ROOT=<private evidence>/rel04-backups \
ISMS_BACKUP_KEY_FILE=<private backup key file> odoo/scripts/backup/backup.sh

# R2 Сэргээлт, throwaway DB
ISMS_BACKUP_KEY_FILE=<private backup key file> ISMS_RESTORE_WORK_DIR=<scratch dir> \
odoo/scripts/backup/restore_verify.sh --backup-dir <R1 dir> --db orgil_isms_stage \
  --target-db isms_restore_verify_rel04a --keep --report <report.json>

# R3 Бүх custom addon-ийн upgrade (addons хавтас read-only snapshot)
docker run --rm --network isms-net \
  -v <addons snapshot>:/mnt/extra-addons:ro \
  -v <private stage config>:/etc/odoo/odoo.conf:ro \
  -v isms-stage-data:/var/lib/odoo odoo:18.0 \
  odoo -c /etc/odoo/odoo.conf -d isms_restore_verify_rel04a --db-filter='^isms_restore_verify_rel04a$' \
  -u <23 модулийн жагсаалт> --stop-after-init --no-http

# R4 / R5 Uninstall ба reinstall (odoo shell, скриптийг stdin-ээр)
docker run --rm -i --network isms-net -e REL04_MODE=uninstall|install \
  -v <addons snapshot>:/mnt/extra-addons:ro -v <private stage config>:/etc/odoo/odoo.conf:ro \
  -v isms-stage-data:/var/lib/odoo odoo:18.0 \
  odoo shell -c /etc/odoo/odoo.conf -d isms_restore_verify_rel04a --db-filter='^...$' --no-http < <probe script>

# R6 Алдаатай upgrade: snapshot-ийн хуулбар дээр синтакс алдаа оруулаад R3-тай ижил командаар -u
# R8 Буруу модулийн нэр
docker run ... odoo -c /etc/odoo/odoo.conf -d isms_restore_verify_rel04b -u no_such_module_rel04 --stop-after-init --no-http

# R11 Цэвэрлэгээ
docker exec isms-db dropdb -U odoo --if-exists <db>
docker exec isms-stage-odoo rm -rf -- /var/lib/odoo/filestore/<db>
```

Probe скриптийн агуулга: 6 хүснэгтийн `count(*)` ба `md5(string_agg(row::text))`, 7 UI модулийн төлөв, `isms.audit.log._verify_chain()`. Скриптийг repo-д хадгалаагүй (scratch директорид байсан).

### 12.3 Хэмжилтийн тайлбар

- RTO (restore): ~52-57 секунд. Хамгийн их хугацаа нь `pg_restore` (нэг job). DB ~51 MB, dump ~5 MB.
- RPO observed: 60 секунд (R1-ийн нөөцийн нас). Нөөцийн график нь RPO-ийн үнэт хязгаар, одоогоор cron суулгаагүй тул NOT VERIFIED.
- Upgrade (23 модуль, 75 суулгасан модуль ачаалах): 27 секунд. Production-ийн хэмжээ өөр байж болно.

### 12.4 Тэмдэглэх зүйл

- Upgrade-ийн алдааны нөхцөл нь ачаалалтын үед гарсан. **Migration функцын дунд алдаа (хагас шинэчлэгдсэн DB)** энэ туршилтад үзүүлээгүй. Тиймээс rollback нь restore-оор л батлагдсан.
- Restore-ийн дараа Odoo вэбийг бүтнээр эхлүүлж нэвтэрсэн шалгалт хийгээгүй. Үүнийг staging дээр тусад нь хийх ёстой.
- Нөөцийн `--keep` ашигласан тул throwaway DB-ийг бүгдийг ажиллуулаад цэвэрлэсэн (R11).

---

## 13. Нотлох баримтын байршил

| Нотолгоо | Байршил |
| --- | --- |
| Backup manifest ба SHA256SUMS | `<private evidence>/rel04-backups/orgil_isms_stage/20261126T130302Z/` |
| Restore тайлан (JSON) | `<scratch dir>/rel04/restore_a.json`, `rollback_restore_b.json` (түр) |
| Upgrade, uninstall, reinstall, failure log | scratch директорид (хувийн орчны лог, repo-д байхгүй) |

Хувийн файл нь repository-ийн гадна байрлана. Энэ баримтад тэдгээрийн агуулгыг хуулаагүй.
