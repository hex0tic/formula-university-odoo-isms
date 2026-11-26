"""Аудит логийн гинжин хэш (hash chain), ISO/IEC 27001:2022 A.8.15.

Гэрээ:
* Бичлэг бүр `seq` (1-ээс эхэлсэн тасралтгүй дугаар), `prev_hash` (өмнөх бичлэгийн `entry_hash`,
  эхнийх нь GENESIS) ба `entry_hash` = SHA-256 (canonical JSON дээр)-ээр холбогдоно.
* Гинжийн дугаар ба хэш серверт (create дээр) олгогдоно. Клиентээс ирсэн seq/hash үл тоомсорлоно.
* Шинэ бичлэг нэмэх бүрт `isms.audit.chain.head` мөрийг `SELECT ... FOR UPDATE`-ээр түгжинэ.
  Ингэснээр зэрэгцээ гүйлгээнүүд ижил seq авахгүй, мөн rollback хийвэл толгой буцаж гарцгүй үлдэнэ.
* ХЯЗГААРЛАЛТ: энэ нь ганцаараа tamper-evidence биш. Superuser нь гинжийг бүрэн дахин тооцоолж
  толгойг ч шинэчлэх боломжтой. Бодит tamper-evidence нь гадаад (дамжуулсан) хэш анкерлэлтээс бүрдэнэ.
"""
import hashlib
import json

from odoo import _, api, fields, models

GENESIS_HASH = '0' * 64
CHAIN_VERSION = 'isms-audit-chain-v1'
VERIFY_CHUNK = 1000

_VERIFY_SQL = """
    SELECT id, seq, timestamp, user_id, action, model, res_id, res_name, changes,
           ip_address, prev_hash, entry_hash
      FROM isms_audit_log
     WHERE seq > %s
     ORDER BY seq
     LIMIT %s
"""


def canonical_text(value):
    """Text талбар: Odoo огт trim хийхгүй; NULL/False -> ''."""
    if value is None or value is False:
        return ''
    return str(value)


def canonical_char(value):
    """Char талбар: Odoo талбарын хоёр талын хоосон зайг тайрдаг тул эндээс мөн тайрна."""
    return canonical_text(value).strip()


def canonical_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def canonical_ts(value):
    """Datetime -> 'YYYY-MM-DD HH:MM:SS' (секундэд хүртэл; create болон DB уншилтад ижил)."""
    if not value:
        return ''
    if isinstance(value, str):
        value = fields.Datetime.to_datetime(value)
    return fields.Datetime.to_string(value)


def canonical_payload(seq, timestamp, user_id, action, model, res_id, res_name, changes, ip, prev_hash):
    return {
        'v': CHAIN_VERSION,
        'seq': canonical_int(seq),
        'ts': canonical_ts(timestamp),
        'uid': canonical_int(user_id),
        'action': canonical_char(action),
        'model': canonical_char(model),
        'res_id': canonical_int(res_id),
        'res_name': canonical_char(res_name),
        'changes': canonical_text(changes),
        'ip': canonical_char(ip),
        'prev_hash': canonical_char(prev_hash),
    }


def entry_hash_of(payload):
    blob = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def _row_payload(row):
    return canonical_payload(
        seq=row['seq'], timestamp=row['timestamp'], user_id=row['user_id'], action=row['action'],
        model=row['model'], res_id=row['res_id'], res_name=row['res_name'], changes=row['changes'],
        ip=row['ip_address'], prev_hash=row['prev_hash'])


class IsmsAuditLogChain(models.Model):
    _inherit = 'isms.audit.log'

    seq = fields.Integer('Гинжийн дугаар', readonly=True, copy=False, index=False)
    prev_hash = fields.Char('Өмнөх бичлэгийн хэш', readonly=True, copy=False)
    entry_hash = fields.Char('Бичлэгийн хэш (SHA-256)', readonly=True, copy=False)

    _sql_constraints = [
        ('isms_audit_chain_seq_uniq', 'UNIQUE(seq)', 'Гинжийн дугаар давтагдахгүй байх ёстой.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if not vals_list:
            return self.browse()
        head = self.env['isms.audit.chain.head'].sudo()._lock_head()
        last_seq, prev_hash = head.last_seq, head.last_hash
        now = fields.Datetime.now()
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            vals['timestamp'] = vals.get('timestamp') or now
            last_seq += 1
            digest = entry_hash_of(canonical_payload(
                seq=last_seq, timestamp=vals['timestamp'], user_id=vals.get('user_id'),
                action=vals.get('action'), model=vals.get('model'), res_id=vals.get('res_id'),
                res_name=vals.get('res_name'), changes=vals.get('changes'),
                ip=vals.get('ip_address'), prev_hash=prev_hash))
            vals.update(seq=last_seq, prev_hash=prev_hash, entry_hash=digest)
            prev_hash = digest
            prepared.append(vals)
        records = super().create(prepared)
        head.write({'last_seq': last_seq, 'last_hash': prev_hash})
        return records

    @api.model
    def _verify_chain(self, limit=None):
        """Гинжийг уншин шалгана (зөвхөн унших, өөрчлөлт хийхгүй).

        Буцаах dict: ok, checked, broken_seq (эвдрэлийн эхний seq эсвэл False), reason, last_seq,
        last_hash. `limit` өгвөл зөвхөн эхний `limit` бичлэгийг (GENESIS-ээс) шалгана; толгойн
        харьцуулалт зөвхөн бүрэн шалгалтад хийгдэнэ.
        """
        cr = self.env.cr
        result = {'ok': True, 'checked': 0, 'broken_seq': False, 'reason': '',
                  'last_seq': 0, 'last_hash': GENESIS_HASH}
        cr.execute("SELECT COUNT(*) FROM isms_audit_log WHERE seq IS NULL")
        unchained = cr.fetchone()[0]
        if unchained:
            return self._chain_broken(result, False, _('Гинжинд ороогүй бичлэг: %s') % unchained)

        expected, prev_hash, after, checked = 1, GENESIS_HASH, 0, 0
        while limit is None or checked < limit:
            size = VERIFY_CHUNK if limit is None else min(VERIFY_CHUNK, limit - checked)
            cr.execute(_VERIFY_SQL, (after, size))
            columns = [col[0] for col in cr.description]
            rows = cr.fetchall()
            if not rows:
                break
            for values in rows:
                row = dict(zip(columns, values))
                if row['seq'] != expected:
                    return self._chain_broken(
                        dict(result, checked=checked),
                        expected, _('Дараалал тасарсан: seq %s алга') % expected)
                if row['prev_hash'] != prev_hash:
                    return self._chain_broken(
                        dict(result, checked=checked), row['seq'],
                        _('Өмнөх хэшийн холбоос таарахгүй'))
                if entry_hash_of(_row_payload(row)) != row['entry_hash']:
                    return self._chain_broken(
                        dict(result, checked=checked), row['seq'],
                        _('Бичлэгийн хэш таарахгүй (агуулга өөрчлөгдсөн байж магадгүй)'))
                prev_hash = row['entry_hash']
                expected += 1
                checked += 1
                after = row['seq']
        result.update(checked=checked, last_seq=checked, last_hash=prev_hash)
        if limit is None:
            head = self.env['isms.audit.chain.head'].sudo().search([], order='id', limit=1)
            if head:
                if head.last_seq > checked:
                    return self._chain_broken(
                        result, checked + 1,
                        _('Сүүлийн бичлэг устсан (толгойн seq %s, сүүлийн бичлэг %s)') % (head.last_seq, checked))
                if head.last_seq < checked:
                    return self._chain_broken(
                        result, head.last_seq + 1,
                        _('Толгой гинжээс хоцорсон (толгой %s, бичлэг %s)') % (head.last_seq, checked))
                if head.last_hash != prev_hash:
                    return self._chain_broken(
                        result, checked, _('Сүүлийн хэш толгойтой таарахгүй'))
        return result

    def _chain_broken(self, result, broken_seq, reason):
        return dict(result, ok=False, broken_seq=broken_seq, reason=reason)
