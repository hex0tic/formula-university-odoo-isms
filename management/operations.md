# Formula University — ажиллуулах ба дахин шалгах заавар

## Одоогийн системийг эхлүүлэх

Үндсэн `biydaalt/odoo/` хавтас дотор:

```bash
docker compose up -d
docker compose ps
```

Хөтөч: `http://127.0.0.1:8069`. Өгөгдлийн сан: `orgil_isms`. Odoo 18 Community ба PostgreSQL 16 ашиглана. DB ба filestore нь `/data/sembee/odoo-isms` дотор хадгалагдана. Одоо байгаа мэдээллийг хадгалж ажиллуулахад дахин импорт хийх шаардлагагүй.

Нэвтрэх мэдээлэл: `odoo/.env` (администратор), `evidence/private/odoo/isms-user-credentials.csv` (кейсийн хэрэглэгчид), `evidence/private/campus-demo-credentials.json` (академик demo). Эдгээр нууц файлыг тайлан, Git, тараах архивт оруулаагүй.

## Бүх regression тест

`odoo/` дотор ажиллуулна. Веб процесс түр зогсож, тест дуусмагц буцаж асна.

```bash
./scripts/odoo-cli.sh -u campus_university,campus_isms_bridge,university_isms,university_isms_stock,university_isms_helpdesk --without-demo=all --test-enable --test-tags /campus_university,/campus_isms_bridge,/university_isms,/university_isms_stock,/university_isms_helpdesk
```

Скрипт `management/runtime.lock`-ийг өөрөө авдаг. Гаднаас ижил түгжээ давхар авахгүй. Эцсийн run: 39 тест, 0 failed, 0 errors (11+3+18+1+6). Лог: `evidence/tests/final-regression-20261116.log`.

## Шинэ тусдаа орчинд босгох дараалал

Доорх нь шинэ орчны дараалал. Одоо ажиллаж буй DB-г дахин үүсгэх шаардлагагүй. VM/server шинээр хэрэгтэй бол shared-lab-vms POLICY-г уншиж, refresh/search болон reservation хийсний дараа шийдвэрлэнэ.

1. Docker Compose, `odoo:18.0`, `postgres:16-alpine` image болон дискний багтаамжийг шалгана. Өөр хичээлийн service, дискийг өөрчлөхгүй.
2. `odoo/` дотор `scripts/setup.sh` ажиллуулна. Admin login-д ашиглах санамсаргүй `ODOO_ADMIN_PASSWORD` утгыг `.env` файлд хамгаалж нэмнэ. `ADMIN_PASSWD` нь database manager-ийн тусдаа нууц үг юм.
3. `scripts/init-db.sh` нь суурь модулиуд ба Монгол хэлийг бэлтгэнэ.
4. `scripts/odoo-cli.sh -i university_isms,university_isms_stock,campus_university,campus_isms_bridge,helpdesk_mgmt,university_isms_helpdesk,university_isms_inventory_catalog --without-demo=all` ажиллуулна.
5. `scripts/odoo-shell.sh scripts/bootstrap.py`, дараа `scripts/odoo-shell.sh scripts/import_case_data.py` ажиллуулна. Эх data-ийн policy огноо нь кейсийн simulation metadata; бодит workflow approval-ийн actor/time нь тусдаа evidence юм.
6. Вебийг асааж, үндсэн хавтаснаас `python3 odoo/addons/campus_university/scripts/run_demo_seed.py` ажиллуулна. Энэ helper гаднаас `management/runtime.lock`-оор зохицуулалт шаарддаг. Нууц үг stdout-д гарахгүй.
7. `scripts/odoo-shell.sh ../evidence/tools/seed_inventory_catalog.py` ажиллуулж 16 product ба 5 DEMO serial үүсгэнэ. Өмнөх incident-ийг `env['isms.incident'].search([])._sync_helpdesk_tickets()`-ээр нэг удаа sync хийнэ; шинэ incident автоматаар холбогдоно.
8. Regression болон UI allow/deny-г дахин шалгана. Шинэ орчны evidence-г тусад нь үүсгэж, хуучин логийг шинэ run гэж нэрлэхгүй.

## Нөөцөөс сэргээх

`evidence/tools/backup_restore_verify.py` нь локал DB+filestore нөөц авч тусдаа temporary DB-д сэргээнэ. Үндсэн DB-г overwrite хийхгүй. Вебийг түр зогсоож буцааж асаан, 10 хүснэгтийн count болон filestore checksum шалгана.

2026-11-16-ны snapshot: сэргээх 48.414 секунд, 190 attachment таарсан. Хаалттай backup файлууд `evidence/private/backups/` дотор. Энэ нь local rehearsal; offsite, WORM, NAS хадгалалтыг тусад нь төлөвлөсөн.

## Хамгаалалтад ашиглах snapshot

- `GCR/2026/00039`: 72→85, revision 1; хүсэлт гаргагч `campus.lecturer`, батлагч `campus.reviewer`.
- `INC-2026-0021`: Close; нийт 7 incident, 7 Helpdesk ticket.
- 16 asset, 16 Inventory product; 14 эрсдэл; 25 сонгосон хяналт (15 yes, 10 partial).
- Үндсэн 3 бодлогын live approval болон demo acknowledgment.

Шинэ demo нь энэ snapshot-оос хойших өөрчлөлт болно. Үүнийг огноо, actor, үр дүнтэй нь worklog-д нэмнэ. Дэлгэрэнгүй: `reports/demo-script.md`.
