# ISMS платформ — Odoo 18.0 Community (deployment)

Formula University-ийн (зохиомол кейс) ISO/IEC 27001:2022 ISMS-ийн Odoo орчин. Эзэмшигч: Deployment агент.
Бүрэн тайлбар, архитектур, RBAC, хатууруулалт, хязгаарлалт: [`../management/odoo-guide.md`](../management/odoo-guide.md).

```bash
./scripts/setup.sh            # анх удаа
docker compose up -d          # http://127.0.0.1:8069
./scripts/init-db.sh          # анх удаа: orgil_isms DB
./scripts/odoo-cli.sh -i university_isms,university_isms_stock
./scripts/odoo-shell.sh scripts/bootstrap.py
./scripts/odoo-shell.sh scripts/import_case_data.py
./scripts/run-tests.sh       # 47 regression тест түр тусдаа DB дээр (ашиглалтын DB-д хүрэхгүй)
```

| Хавтас | Агуулга |
|---|---|
| `addons/university_isms/` | Өөрсдийн ISMS модуль (Deployment агент) |
| `addons/university_isms_stock/` | Inventory холболт (Deployment агент) |
| `addons/university_isms/migrations/` | Хувилбарын шилжилт (18.0.1.1.0: admin SoD, workflow нийцэл, RTP даалгавар) |
| `addons/campus_university/`, `campus_isms_bridge/`, `university_isms_helpdesk/`, `helpdesk_mgmt/` | Codex-ийн эзэмшил |
| `config/odoo.conf.template` | Тохиргооны загвар (`odoo.conf` нь нууц үгтэй, git-д орохгүй) |
| `scripts/` | setup, init-db, odoo-cli (flock), odoo-shell, bootstrap, import, sync_incident_notifications, run-tests (тусдаа DB) |
| `logs/` | Odoo болон CLI лог (git-д орохгүй) |

## Нэг Wi-Fi/LAN-аас нэвтрэх (2026-11-18)

Хэрэглэгчийн хүсэлтээр багийнхан нэг Wi-Fi/LAN-аас нэвтрэх горим нэмэв. `odoo/` дотор:

```bash
./scripts/start-lan.sh
```

Скрипт default route-ийн private IPv4-г сонгон Odoo-ийн HTTP портыг зөвхөн тэр хаягт холбоно. Одоогийн URL: `http://172.16.151.135:8069/web/login?db=orgil_isms`. Компьютер ба багийн төхөөрөмжүүд нэг сүлжээнд байна. IP солигдвол скриптийг дахин ажиллуулж хэвлэсэн URL-ийг ашиглана. Автомат сонголт зөвхөн RFC1918 IPv4 зөвшөөрнө. PostgreSQL хост порт нээхгүй.

`docker compose up -d` дангаараа ажиллавал `ISMS_HTTP_BIND` өгөгдөөгүй үед анхдагч localhost горимд буцна. LAN горимд үргэлж дээрх скриптийг ашиглана. LAN холбоос нээгдэхгүй бол Wi-Fi client isolation эсвэл host firewall-ийг шалгана; энэ скрипт firewall/router-ийн тохиргоог өөрчлөхгүй.
