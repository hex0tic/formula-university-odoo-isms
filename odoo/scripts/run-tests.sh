#!/usr/bin/env bash
# Regression тестийг ашиглалтын `orgil_isms` DB дээр БИШ, шинээр үүсгэсэн түр DB дээр ажиллуулна
# (ISO/IEC 27001:2022 A.8.31 орчныг тусгаарлах, A.8.33 тестийн мэдээлэл). Дууссаны дараа DB, filestore-ийг устгана.
# Ашиглалтын DB-ийн sequence дугаар, бүртгэлд нөлөөлөхгүй; вэб процесс зогсохгүй.
#   scripts/run-tests.sh
#   MODULES=university_isms TAGS=/university_isms scripts/run-tests.sh
set -euo pipefail
cd "$(dirname "$0")/.."
exec 9>>../management/runtime.lock
echo "[run-tests] runtime.lock хүлээж байна..."
flock 9
MODULES=${MODULES:-university_isms,university_isms_stock,university_isms_inventory_catalog,university_isms_helpdesk,campus_university,campus_isms_bridge}
TAGS=${TAGS:-/university_isms,/university_isms_stock,/university_isms_inventory_catalog,/university_isms_helpdesk,/campus_university,/campus_isms_bridge}
db="isms_ci_$(date +%Y%m%d%H%M%S)"
log="tests-$db.log"
docker compose up -d db >/dev/null
cleanup() {
  docker compose exec -T db dropdb -U odoo --if-exists "$db" >/dev/null 2>&1 || true
  docker compose run --rm --no-deps --entrypoint rm odoo -rf "/var/lib/odoo/filestore/$db" >/dev/null 2>&1 || true
  echo "[run-tests] түр DB $db устгагдлаа"
}
trap cleanup EXIT
echo "[run-tests] түр DB: $db, модуль: $MODULES"
set +e
docker compose run --rm --no-deps odoo odoo -c /etc/odoo/odoo.conf -d "$db" -i "$MODULES" \
  --without-demo=all --test-enable --test-tags "$TAGS" --logfile="/var/log/odoo/$log" --stop-after-init
rc=$?
set -e
echo "[run-tests] exit=$rc (лог: logs/$log)"
grep -E "tests when loading|post-tests in|FAIL:|ERROR:" "logs/$log" | tail -20 || true
exit $rc
