# Odoo ERP — зорилго, бүтэц, ажиллуулах заавар (Даалгавар 3)

Эзэмшигч: Claude Code (deployment owner). Сүүлд шинэчилсэн: 2026-11-16. Бүх тоо, хувилбар нь энэ орчинд бодитоор шалгагдсан.

## 1. Odoo гэж юу вэ, яагаад ISMS-д?

**Odoo** нь нээлттэй эхийн **ERP (Enterprise Resource Planning)** платформ: санхүү, хүний нөөц, төсөл, агуулах, худалдан авалт зэрэг байгууллагын үйл ажиллагааг нэг өгөгдлийн сан, нэг хэрэглэгчийн эрхийн системээр удирддаг **модуль (app)**-иудаас бүрдэнэ. Community Edition (LGPL-3) үнэгүй; Enterprise нь нэмэлт модультай (Helpdesk, Documents, Knowledge, Sign г.м.) төлбөртэй.

ISMS-д ашиглах үндэслэл:
- **Нэг эх сурвалж:** хөрөнгө, эрсдэл, хяналт, инцидент, бодлогыг нэг DB-д холбож хадгална (asset → risk → control → task → incident → evidence).
- **Эрхийн загвар бэлэн:** хэрэглэгч, бүлэг (group), ACL, record rule → RBAC (A.5.15, A.5.18, A.8.2).
- **Өөрчлөлтийн түүх:** chatter + `tracking` (A.5.28), workflow (статус бар).
- **Өргөтгөх боломж:** Python модуль бичиж өөрийн байгууллагын процессыг (их сургуулийн ISMS) нэмнэ.
- **Төсөв:** кейсийн сургуульд commercial GRC платформ авах нөөц бага (case.md §3).

## 2. Архитектур

```
Хэрэглэгч (browser) ──HTTP 127.0.0.1:8069──► isms-odoo (odoo:18.0, Python 3.12)
                                               │  ORM, view, security, workflow, QWeb PDF (wkhtmltopdf 0.12.6.1)
                                               │  addons_path: /mnt/extra-addons (манай модуль) + стандарт 689 addon
                                               ├──► isms-db (postgres:16-alpine) — бүх бичлэг, эрх, лог
                                               └──► filestore (/var/lib/odoo) — хавсралт, asset bundle
```

| Давхарга | Odoo дахь ойлголт | Манай жишээ |
|---|---|---|
| Model (өгөгдөл) | `models.Model`, талбар (`fields.*`), ORM | `isms.risk`, `isms.asset` |
| View (харагдац) | XML: list, form, kanban, pivot, graph, search | Эрсдэлийн матриц = pivot (магадлал × нөлөөлөл) |
| Controller/логик | Python method, `@api.depends` compute, action товч | `action_close()`, `_compute_scores()` |
| Security | `res.groups`, `ir.model.access.csv` (ACL), `ir.rule` (record rule) | 5 ISMS бүлэг, 11 record rule, 30 ACL мөр |
| Data | XML/CSV data файл, sequence | 93 Annex A хяналт, AST-/RSK-/INC- дугаарлалт |
| Report | QWeb template → PDF | SoA, Risk Register, Asset Register |

Модулийн бүтэц (`odoo/addons/university_isms/`): `__manifest__.py` (нэр, хамаарал, data дараалал) → `models/` → `security/` → `data/` → `views/` → `report/` → `tests/` → `static/`.

## 3. Манай орчин

| Зүйл | Утга |
|---|---|
| Odoo | **18.0 Community**, build `18.0-20261112` (`odoo:18.0` image) |
| PostgreSQL | 16 (`postgres:16-alpine`, локал cache-ээс дахин ашигласан) |
| Compose project | `isms`; контейнер `isms-odoo`, `isms-db`; сүлжээ `isms-net` |
| URL | `http://127.0.0.1:8069` (зөвхөн localhost) |
| DB | `orgil_isms` (demo өгөгдөлгүй), хэл mn_MN |
| Өгөгдөл | `/data/sembee/odoo-isms/{pgdata,filestore}` (/var 97% дүүрсэн тул) |
| Лог | `biydaalt/odoo/logs/odoo.log`, CLI ажиллагаа бүр `logs/cli-<огноо>.log` |
| Нууц үг | `biydaalt/odoo/.env` (600, git-д орохгүй); хэрэглэгчдийнх `evidence/private/odoo/isms-user-credentials.csv` |

### Суусан модулиуд
| Модуль | Эх | Үүрэг |
|---|---|---|
| `university_isms` | **Өөрсдийн** (Claude) | Хөрөнгө, эрсдэл 5×5, Annex A + SoA, инцидент 5 үе шат, бодлого, аудит лог, RBAC |
| `university_isms_stock` | **Өөрсдийн** (Claude) | Хөрөнгийг Inventory-ийн бараа/серийн дугаар/байршилтай холбоно |
| `campus_university`, `campus_isms_bridge` | **Өөрсдийн** (Codex) | Оюутан, хичээл, дүн өөрчлөх хүсэлтийн тусдаа батлалт; ISMS аудитад холбох |
| `helpdesk_mgmt` (OCA) + `university_isms_helpdesk` | OCA + Codex | Community Helpdesk ба ISMS инцидентийн холбоос |
| `hr`, `project`, `stock` | Odoo CE | Нэгж/ажилтан, эрсдэлийн хариу арга хэмжээний даалгавар, агуулах |
| `auth_totp`, `auth_password_policy` | Odoo CE | MFA (A.8.5), нууц үгийн урт ≥10 (A.5.17) |

## 4. Ажиллуулах

```bash
cd biydaalt/odoo
./scripts/setup.sh                 # анх удаа: .env, odoo.conf, /data хавтас
docker compose up -d               # асаах
docker compose ps                  # төлөв
docker compose logs -f odoo        # лог (эсвэл logs/odoo.log)
docker compose stop                # зогсоох (өгөгдөл хадгалагдана)
./scripts/init-db.sh               # анх удаа: DB + CE модулиуд
./scripts/odoo-cli.sh -i university_isms                       # модуль суулгах
./scripts/odoo-cli.sh -u university_isms --test-enable --test-tags /university_isms   # шинэчлэх + тест
./scripts/odoo-shell.sh scripts/bootstrap.py                   # компани, admin нууц үг, хатууруулалт
./scripts/odoo-shell.sh scripts/import_case_data.py            # biydaalt/data/*.csv импорт (дахин ажиллуулж болно)
ISMS_IMPORT_DRY_RUN=1 ./scripts/odoo-shell.sh scripts/import_case_data.py   # шалгах, rollback
```
`odoo-cli.sh`, `odoo-shell.sh` нь `management/runtime.lock`-ийг flock хийж, олон агент зэрэг DB өөрчлөхөөс сэргийлнэ.

## 5. ISMS цэс ба ажлын урсгал
- **Инцидент** — мэдээлэх, миний мэдээлсэн, бүх инцидент (kanban: Incident → Report → Investigate → Resolve → Close).
- **Хөрөнгө** — Asset Register (ангилал: Нийтэд нээлттэй / Дотоод / Хязгаарлагдмал / Нууц; C/I/A 1–3; үнэ цэнэ = max(C,I,A)).
- **Эрсдэл** — бүртгэл, **5×5 матриц** (pivot), хариу арга хэмжээний даалгавар (Project), аюул занал, эмзэг байдал.
- **Хяналт ба SoA** — Controls Mapping (25 сонгосон), SoA (93), Annex A.
- **Бодлого** — EISP/ISSP/SysSP, батлах, «Танилцсан».
- **Тайлан** — SoA / Эрсдэл / Хөрөнгийн бүртгэл PDF.
- **Аудит лог** — зөвхөн аудитор, CISO, системийн админ.

## 6. RBAC (Даалгавар 8)
| Түвшин | Бүлэг | Гол эрх |
|---|---|---|
| 1 | Мэдээлэгч | Инцидент мэдээлэх, өөрийнхөө инцидент, батлагдсан бодлого |
| 2 | Хөрөнгө эзэмшигч | Хөрөнгө унших, **өөрийн** хөрөнгийг засах, өөрийн хөрөнгийн эрсдэл |
| 3 | Дотоод аудитор | Бүгдийг **зөвхөн унших** + аудит лог (тусдаа ангилал, SoD) |
| 4 | МАБ шинжээч | Хөрөнгө, эрсдэл, инцидент, SoA засах; Project даалгавар |
| 5 | МАБ менежер (CISO) | Эрсдэл хүлээн зөвшөөрөх, бодлого батлах, инцидент хаах/дахин нээх |
| 6 | Odoo Settings (`base.group_system`) | Техникийн тохиргоо |

Хамгаалалт сервер талд: workflow-ийн төлөв, батлагч, хугацааны тэмдэг, бүртгэлийн дугаарыг зөвхөн дотоод token-той method өөрчилнө — RPC/kanban drag ч ижил шалгалтаар дамжина. 18 автомат тест allow/deny-г баталсан (`evidence/tests/university_isms-tests-20261116-111048.log`).

## 7. Хийсэн хатууруулалт
- Порт зөвхөн `127.0.0.1` (A.8.20); `list_db = False` — вэб DB manager хаалттай (A.8.9).
- CLI-ээр үүсэх `admin/admin` нууц үгийг санамсаргүй утгаар солив (A.5.17).
- `auth_password_policy.minlength = 10`; MFA (`auth_totp`) суусан — хэрэглэгч бүр Preferences → Account Security-д идэвхжүүлнэ.
- Odoo-гийн анхдагч **чөлөөт бүртгэл (b2c)**-ийг **урилгаар (b2b)** болгож хаав (A.5.16, A.5.18).
- Нууц үг, credential файл `.gitignore`-д (`odoo/.env`, `odoo/config/odoo.conf`, `evidence/private/`).

## 8. Хязгаарлалт (тайланд шударга бичих)
- Аудит лог нь **Odoo app түвшинд** өөрчлөх/устгах боломжгүй; DB админ SQL-ээр өөрчлөх боломжтой тул tamper-proof гадаад лог гэж нэрлэхгүй. Бодит байгууллагад SIEM/WORM хадгалалт шаардлагатай.
- CLI/cron-оор хийсэн өөрчлөлтийн IP хоосон байна.
- Seed өгөгдөл (`biydaalt/data/`) зохиомол кейс; дэлгэцийн зураг, тестийн үр дүн, лог нь бодит ажиллагааны нотолгоо (decisions.md D07).
- Аудит логийн хэрэглэгчийн мөр бүр бодит: гишүүд **өөрсдийн хэрэглэгчээр** нэвтэрч ажилласнаар хувь нэмэр нь логт харагдана.
