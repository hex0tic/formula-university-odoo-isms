#!/usr/bin/env bash
# Python скриптийг `odoo shell`-ээр orgil_isms DB дээр ажиллуулна (вэб процесс зогсохгүй).
#   scripts/odoo-shell.sh scripts/bootstrap.py
#   scripts/odoo-shell.sh scripts/import_case_data.py   (biydaalt/data/*.csv-г /mnt/case-data-д mount хийнэ)
set -euo pipefail
cd "$(dirname "$0")/.."
script=${1:?usage: odoo-shell.sh <script.py>}
exec 9>>../management/runtime.lock
flock 9
set -a; source .env; set +a
root="$(cd .. && pwd)"
data_dir="${ISMS_CASE_DATA:-$root/data}"
priv="$root/evidence/private/odoo"
if [[ ! -d "$priv" ]]; then  # odoo uid 100 бичнэ, хэрэглэгчийн бүлэг уншина
  mkdir -p "$priv"
  docker run --rm -u 0 --entrypoint sh -v "$priv:/p" odoo:18.0 -c "chown 100:$(id -g) /p && chmod 2770 /p"
fi
mounts=(-v "$priv:/mnt/case-private")
[[ -d "$data_dir" ]] && mounts+=(-v "$data_dir:/mnt/case-data:ro")
[[ -d "$root/policies" ]] && mounts+=(-v "$root/policies:/mnt/case-policies:ro")
docker compose run --rm --no-deps -T "${mounts[@]}" -e ODOO_ADMIN_PASSWORD -e ISMS_IMPORT_DRY_RUN \
  odoo odoo shell -c /etc/odoo/odoo.conf -d orgil_isms --no-http \
  --logfile=/var/log/odoo/shell.log < "$script"
