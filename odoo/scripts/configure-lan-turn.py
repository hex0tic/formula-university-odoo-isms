#!/usr/bin/env python3
"""Configure a private-LAN authenticated TURN relay; caller owns runtime.lock."""
from pathlib import Path
import base64, ipaddress, json, os, secrets, subprocess, sys
root = Path(__file__).resolve().parents[2]
ip = str(ipaddress.IPv4Address(sys.argv[1]))
private = root / "evidence/private/turn"
private.mkdir(parents=True, exist_ok=True)
private.chmod(0o700)
creds = private / "credentials.json"
if creds.exists():
    account = json.loads(creds.read_text())
else:
    account = {"username": "formula-lan", "password": secrets.token_hex(24)}
    fd = os.open(creds, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(account, stream)
config = private / "turnserver.conf"
config.write_text("\n".join([
    "listening-port=3478", "listening-ip=" + ip, "relay-ip=" + ip,
    "min-port=49160", "max-port=49200", "realm=formula-university.lan",
    "fingerprint", "lt-cred-mech", "user=" + account["username"] + ":" + account["password"],
    "no-cli", "no-tls", "no-multicast-peers", "relay-threads=2", "pidfile=/tmp/turnserver.pid",
    "denied-peer-ip=127.0.0.0-127.255.255.255", "denied-peer-ip=0.0.0.0-0.255.255.255",
    "user-quota=30", "total-quota=100", "no-software-attribute", "simple-log", "log-file=stdout",
]) + "\n")
# The enclosing directory remains 0700; only this file is mounted into coturn running as nobody.
config.chmod(0o644)
payload = base64.b64encode(json.dumps({"ip": ip, **account}).encode()).decode()
code = """import base64, json
p = json.loads(base64.b64decode(PAYLOAD))
Ice = env['mail.ice.server'].sudo()
for kind, suffix in [('stun', ':3478'), ('turn', ':3478?transport=udp'), ('turn', ':3478?transport=tcp')]:
    uri = p['ip'] + suffix
    # Update only records previously owned by this helper; retain unrelated ICE configuration.
    rows = Ice.search([('server_type', '=', kind), ('username', '=', p['username'])])
    row = rows.filtered(lambda r: r.uri.endswith(suffix))[:1]
    vals = {'server_type': kind, 'uri': uri, 'username': p['username'], 'credential': p['password'] if kind == 'turn' else False}
    if row:
        row.write(vals)
    else:
        Ice.create(vals)
env.cr.commit()
print('LAN ICE CONFIGURED: STUN + authenticated TURN UDP/TCP')
""".replace('PAYLOAD', repr(payload))
result = subprocess.run(['docker', 'exec', '-i', 'isms-odoo', 'odoo', 'shell', '-c',
    '/etc/odoo/odoo.conf', '-d', 'orgil_isms', '--no-http', '--logfile=/dev/null'],
    input=code, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if result.returncode:
    raise SystemExit('Odoo ICE setup failed; inspect local runtime logs.')
print(result.stdout.strip())
