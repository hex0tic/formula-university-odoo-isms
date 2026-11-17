# Odoo shell: canonical data/incidents.csv-ийн notification_done/notification_note-ийг зөвхөн хоосон байгаа
# хувийн мэдээллийн зөрчилтэй инцидентэд хуулна (бусад талбар, workflow-ийн түүхийг өөрчлөхгүй).
#   scripts/odoo-shell.sh scripts/sync_incident_notifications.py
import csv
import os

path = '/mnt/case-data/incidents.csv'
rows = {r['code']: r for r in csv.DictReader(open(path, encoding='utf-8-sig', newline=''))}
updated = []
for inc in env['isms.incident'].search([('personal_data_breach', '=', True)]):
    row = rows.get(inc.code)
    if not row or inc.notification_note or not (row.get('notification_note') or '').strip():
        continue
    inc.write({
        'notification_done': (row.get('notification_done') or '').lower() in ('1', 'true', 'yes'),
        'notification_note': row['notification_note'].strip(),
    })
    inc.message_post(body='Canonical өгөгдлийн засвар (2026-11-18): хувийн мэдээллийн зөрчлийн мэдэгдлийн '
                          'шийдвэрийг data/incidents.csv-ээс бүртгэв.')
    updated.append(inc.code)
if os.environ.get('ISMS_IMPORT_DRY_RUN'):
    env.cr.rollback()
else:
    env.cr.commit()
print('NOTIFICATION SYNC', updated or 'өөрчлөлтгүй')
