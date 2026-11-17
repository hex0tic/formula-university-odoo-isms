#!/usr/bin/env bash
# Odoo-г нэг удаа CLI горимоор ажиллуулна (модуль суулгах/шинэчлэх). Жишээ:
#   scripts/odoo-cli.sh -i university_isms
#   scripts/odoo-cli.sh -u university_isms
# Ажиллаж буй вэб процессыг түр зогсоож, дуусмагц дахин эхлүүлнэ.
set -euo pipefail
cd "$(dirname "$0")/.."
# Агентуудын хооронд DB install/update-г дараалуулах (management/runtime.lock)
exec 9>>../management/runtime.lock
echo "[odoo-cli] runtime.lock хүлээж байна..."
flock 9
echo "[odoo-cli] lock авлаа: $*"
was_running=$(docker compose ps --status running --services | grep -qx odoo && echo 1 || echo 0)
[[ $was_running == 1 ]] && docker compose stop odoo >/dev/null
docker compose up -d db >/dev/null
set +e
log="cli-$(date +%Y%m%d-%H%M%S).log"
docker compose run --rm --no-deps odoo odoo -c /etc/odoo/odoo.conf -d orgil_isms \
  --logfile="/var/log/odoo/$log" --stop-after-init "$@"
rc=$?
set -e
echo "[odoo-cli] exit=$rc (лог: logs/$log)"
grep -E "ERROR|CRITICAL|Traceback|tests when loading|post-tests in" "logs/$log" | tail -20 || true
[[ $was_running == 1 ]] && docker compose start odoo >/dev/null
exit $rc
