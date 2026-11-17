#!/usr/bin/env bash
# Нэг удаагийн бэлтгэл: .env (санамсаргүй нууц үг), config/odoo.conf, /data дээрх хавтас.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  umask 077
  {
    echo "ISMS_DATA_ROOT=/data/sembee/odoo-isms"
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
    echo "ADMIN_PASSWD=$(openssl rand -hex 16)"
  } > .env
  echo "[setup] .env үүсгэв (git-д орохгүй)."
fi
set -a; source .env; set +a

sed -e "s/__ADMIN_PASSWD__/${ADMIN_PASSWD}/" -e "s/__POSTGRES_PASSWORD__/${POSTGRES_PASSWORD}/" \
  config/odoo.conf.template > config/odoo.conf
chmod 600 config/odoo.conf

mkdir -p "${ISMS_DATA_ROOT}/pgdata" "${ISMS_DATA_ROOT}/filestore" logs
# Odoo контейнерийн хэрэглэгч uid 100 / gid 101; conf-ийг унших, filestore/logs-д бичих эрх
docker run --rm -u 0 --entrypoint sh \
  -v "${ISMS_DATA_ROOT}/filestore:/fs" -v "$PWD/logs:/logs" -v "$PWD/config:/cfg" \
  odoo:18.0 -c 'chown -R 100:101 /fs /logs && chgrp 101 /cfg/odoo.conf && chmod 640 /cfg/odoo.conf'
echo "[setup] бэлэн: docker compose up -d && scripts/init-db.sh"
