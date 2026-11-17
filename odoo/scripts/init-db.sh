#!/usr/bin/env bash
# orgil_isms DB-г demo өгөгдөлгүй үүсгэж, Community модулиудыг суулгана.
set -euo pipefail
cd "$(dirname "$0")"
./odoo-cli.sh -i base,web,mail,hr,project,auth_totp,auth_password_policy \
  --without-demo=all --load-language=mn_MN "$@"
