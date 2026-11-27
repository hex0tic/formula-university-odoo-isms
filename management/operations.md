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

`odoo/` дотор ажиллуулна. 2026-11-18-аас тестийг **ашиглалтын `orgil_isms` DB дээр биш**, шинээр үүсгэсэн түр `isms_ci_<огноо>` DB дээр ажиллуулж, дуусмагц устгана (A.8.31). Вэб процесс зогсохгүй.

```bash
./scripts/run-tests.sh
```

Скрипт `management/runtime.lock`-ийг өөрөө авдаг. Эцсийн run (2026-11-18): **47 тест, 0 failed, 0 errors** (campus 11 + bridge 4 + ISMS 25 + stock 1 + Helpdesk 6), `evidence/tests/regression-20261118.json`. Өмнөх 39 тестийн run (2026-11-16, ашиглалтын DB дээр): `evidence/tests/final-regression.json`.

Ашиглалтын DB-д кодын өөрчлөлтийг тестгүйгээр шилжүүлэх: `./scripts/odoo-cli.sh -u university_isms,...`.

## Шинэ тусдаа орчинд босгох дараалал

Доорх нь шинэ орчны дараалал. Одоо ажиллаж буй DB-г дахин үүсгэх шаардлагагүй. VM/server шинээр хэрэгтэй бол shared-lab-vms POLICY-г уншиж, refresh/search болон reservation хийсний дараа шийдвэрлэнэ.

1. Docker Compose, `odoo:18.0`, `postgres:16-alpine` image болон дискний багтаамжийг шалгана. Өөр хичээлийн service, дискийг өөрчлөхгүй.
2. `odoo/` дотор `scripts/setup.sh` ажиллуулна. Admin login-д ашиглах санамсаргүй `ODOO_ADMIN_PASSWORD` утгыг `.env` файлд хамгаалж нэмнэ. `ADMIN_PASSWD` нь database manager-ийн тусдаа нууц үг юм.
3. `scripts/init-db.sh` нь суурь модулиуд ба Монгол хэлийг бэлтгэнэ. Дараа нь `scripts/odoo-shell.sh scripts/set_discuss_translation.py` ажиллуулж Discuss цэсийг «Хэлэлцэх» гэж нэрлэнэ. Суурь орчуулгыг дарж шинэчилсэн бол энэ командыг давтаж болно.
4. `scripts/odoo-cli.sh -i university_isms,university_isms_stock,campus_university,campus_isms_bridge,helpdesk_mgmt,university_isms_helpdesk,university_isms_inventory_catalog,campus_rtc_fix --without-demo=all` ажиллуулна.
5. `scripts/odoo-shell.sh scripts/bootstrap.py`, дараа `scripts/odoo-shell.sh scripts/import_case_data.py` ажиллуулна. Импорт төгсгөлдөө workflow-ийн нийцлийг (CISO-гийн хүлээн зөвшөөрөлт, үлдэгдэл батлалт, Risk Treatment даалгавар) шалгаж засна. Эх data-ийн policy огноо нь кейсийн simulation metadata; бодит workflow approval-ийн actor/time нь тусдаа evidence юм.
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

## Бүртгэл тус бүрийн жишээ өгөгдөл

Кейс, академик демо бүртгэлүүдийг суулгасны дараа `odoo/` хавтсаас доорх командыг ажиллуулна. Давтаж ажиллуулахад жишээ бүртгэлүүд давхардахгүй.

```bash
flock ../management/runtime.lock docker exec -e ISMS_DEMO_APPLY=1 -i isms-odoo \
  odoo shell -c /etc/odoo/odoo.conf -d orgil_isms --no-http \
  --logfile=/var/log/odoo/shell.log < scripts/seed_account_examples.py
```

`ISMS_DEMO_APPLY=1`-ийг өгөөгүй үед скрипт шалгаад өөрчлөлт хадгалалгүй гарна. Жишээ нь тайлангийн өмнөх snapshot-аас хойш нэмэгдсэн сургалтын өгөгдөл тул `[ДЭМО]` тэмдэгтэй шинэ инцидент, эрсдэлийг өмнөх тайлангийн тоонд оруулахгүй.

## Нэг Wi-Fi/LAN-аас нэвтрэх (2026-11-18)

Хэрэглэгчийн хүсэлтээр багийнхан нэг Wi-Fi/LAN-аас нэвтрэх горим нэмэв. `odoo/` дотор:

```bash
./scripts/start-lan.sh
```

Скрипт default route-ийн private IPv4-г сонгон Odoo-ийн HTTP портыг зөвхөн тэр хаягт холбоно. Одоогийн URL: `http://172.16.151.135:8069/web/login?db=orgil_isms`. Компьютер ба багийн төхөөрөмжүүд нэг сүлжээнд байна. IP солигдвол скриптийг дахин ажиллуулж хэвлэсэн URL-ийг ашиглана. Автомат сонголт зөвхөн RFC1918 IPv4 зөвшөөрнө. PostgreSQL хост порт нээхгүй.

`docker compose up -d` дангаараа ажиллавал `ISMS_HTTP_BIND` өгөгдөөгүй үед анхдагч localhost горимд буцна. LAN горимд үргэлж дээрх скриптийг ашиглана. LAN холбоос нээгдэхгүй бол Wi-Fi client isolation эсвэл host firewall-ийг шалгана; энэ скрипт firewall/router-ийн тохиргоог өөрчлөхгүй.

## LAN camera/mic-д HTTPS ашиглах

Өмнөх HTTP LAN хаягийг HTTPS горим орлов: `./scripts/start-lan.sh`, дараа `https://<LAN-IP>:8443`. Төхөөрөмж бүрд CA trust import шаардлагатай. Дэлгэрэнгүй: [lan-https.md](lan-https.md).

## Автомат нөөцлөлт (2026-11-27)

Үндсэн Odoo өгөгдлийн сан болон файлын санг Улаанбаатарын цагаар өдөр бүр 04:30-д шифрлэж нөөцөлнө. Сар бүрийн эхний нямд 05:30-д хамгийн сүүлийн нөөцийг тусгаарласан өгөгдлийн санд сэргээн шалгана. Шалгалт дуусахад түр өгөгдлийн сан, файлын санг цэвэрлэнэ. Компьютер унтарсан бол дараа асахад хоцорсон ажлыг нөхөн ажиллуулна.

```bash
systemctl --user list-timers 'formula-isms-*'
systemctl --user start formula-isms-backup.service
systemctl --user start formula-isms-restore-verify.service
journalctl --user -u formula-isms-backup.service -u formula-isms-restore-verify.service
```

Нөөц болон сэргээх шалгалтын JSON нь `~/.local/state/formula-isms-backups/` дотор байна. Шифр тайлах түлхүүрийг `~/.config/formula-isms/backup.key`-д тусад нь, зөвхөн эзэмшигчид унших эрхтэй хадгална. Нөөц болон түлхүүрийг Git-д оруулахгүй. Тусдаа төхөөрөмжид нөөцийн хуулбар хадгалах тохиргоо хийгдээгүй. Өдөр тутмын 7, долоо хоног тутмын 4 нөөц хадгалах дүрэм үйлчилнэ.
