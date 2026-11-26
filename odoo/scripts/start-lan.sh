#!/usr/bin/env bash
# Start the existing Odoo database on this computer's current private LAN IPv4.
set -euo pipefail
cd "$(dirname "$0")/.."
exec 200>../management/runtime.lock
flock -n 200 || { echo "Odoo runtime is busy; retry after the current operation finishes." >&2; exit 1; }
lan_ip="$(python3 - <<'PYIP'
import ipaddress, json, subprocess
routes = json.loads(subprocess.check_output(['ip', '-j', 'route', 'get', '1.1.1.1']))
address = routes[0].get('prefsrc') or routes[0].get('src')
if not address:
    raise SystemExit('No LAN IPv4 address found. Connect to Wi-Fi/LAN first.')
ip = ipaddress.ip_address(address)
networks = [ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
if not any(ip in n for n in networks):
    raise SystemExit('The current address is not a private LAN IPv4; refusing automatic exposure.')
print(address)
PYIP
)"
tls_dir="$(cd .. && pwd)/evidence/private/tls/lan"
mkdir -p "$tls_dir"
chmod 700 "$tls_dir"
umask 077
if [[ ! -f "$tls_dir/ca.crt" ]]; then
    openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
      -keyout "$tls_dir/ca.key" -out "$tls_dir/ca.crt" \
      -subj "/CN=Formula University Coursework LAN CA" \
      -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
      -addext "keyUsage=critical,keyCertSign,cRLSign" 2>/dev/null
fi
if [[ ! -f "$tls_dir/server.crt" ]] || ! openssl x509 -in "$tls_dir/server.crt" -noout -checkend 86400 >/dev/null 2>&1 || ! openssl x509 -in "$tls_dir/server.crt" -noout -checkip "$lan_ip" >/dev/null 2>&1; then
    openssl req -newkey rsa:2048 -nodes -keyout "$tls_dir/server.key" \
      -out "$tls_dir/server.csr" -subj "/CN=$lan_ip" 2>/dev/null
    printf 'subjectAltName=IP:%s\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n' "$lan_ip" > "$tls_dir/server.ext"
    openssl x509 -req -in "$tls_dir/server.csr" -CA "$tls_dir/ca.crt" -CAkey "$tls_dir/ca.key" \
      -CAcreateserial -out "$tls_dir/server.crt" -days 90 -sha256 \
      -extfile "$tls_dir/server.ext" 2>/dev/null
fi
# Only public CA certificate may be shared; never share ca.key or server.key.
chmod 644 "$tls_dir/ca.crt" "$tls_dir/server.crt"
proxy_changed="$(python3 - <<'PYCONF'
from pathlib import Path
import re
p=Path('config/odoo.conf')
s=p.read_text()
t=re.sub(r'(?m)^proxy_mode\s*=\s*False\s*$', 'proxy_mode = True', s)
if t != s:
    p.write_text(t)
    print('yes')
else:
    print('no')
PYCONF
)"
if [[ -z "$(docker compose ps --status running -q db)" ]]; then
    docker compose up -d db
fi
# Keep direct HTTP on loopback; only the HTTPS proxy is available to LAN clients.
ISMS_HTTP_BIND=127.0.0.1 docker compose up -d --no-deps odoo
if [[ "$proxy_changed" == yes ]]; then
    docker compose restart odoo
fi
python3 scripts/configure-lan-turn.py "$lan_ip"
ISMS_LAN_IP="$lan_ip" docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --no-deps https turn
# TURN reads listener IP and credentials at startup.
ISMS_LAN_IP="$lan_ip" docker compose -f docker-compose.yml -f docker-compose.https.yml restart turn
printf '\nOdoo HTTPS LAN URL: https://%s:8443/web/login?db=orgil_isms\n' "$lan_ip"
printf 'Trust this public CA certificate on each client device first: %s/ca.crt\n' "$tls_dir"
