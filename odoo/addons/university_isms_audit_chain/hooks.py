"""Суулгах / устгах hook-ууд.

1. backfill_chain: гинжинд ороогүй хуучин бичлэгүүдийг id эрэмбээр нэг удаа гинжилнэ (idempotent).
2. install_trigger: isms_audit_log дээр UPDATE/DELETE/TRUNCATE-ийг татгалзах trigger.
   ХЯЗГААРЛАЛТ: PostgreSQL superuser (`odoo` роль) trigger-ийг DISABLE TRIGGER-ээр унтраах боломжтой.
   Тиймээс энэ нь defense-in-depth бөгөөд tamper-evidence биш; tamper-evidence нь hash гинж +
   гадаад анкерлэлт юм.
3. remove_trigger: uninstall үед trigger ба функцийг устгана. Аудит бичлэг, гинжийн багануудыг хэвээр үлдээнэ.
"""
import logging

from .models.audit_chain import canonical_payload, entry_hash_of

_logger = logging.getLogger(__name__)

BACKFILL_GUC = 'university_isms_audit_chain.backfill'
GUARD_FUNCTION = 'isms_audit_log_chain_guard'
ROW_TRIGGER = 'isms_audit_log_guard_row'
STATEMENT_TRIGGER = 'isms_audit_log_guard_stmt'
BACKFILL_BATCH = 500

GUARD_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION isms_audit_log_chain_guard() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Зөвхөн backfill горим (сессийн GUC, зөвхөн гинжинд ороогүй мөр) дээр, агуулга хэвээр байвал зөвшөөрнө.
        IF OLD.seq IS NULL
           AND current_setting('university_isms_audit_chain.backfill', true) = 'on'
           AND (NEW.id, NEW.timestamp, NEW.user_id, NEW.login, NEW.action, NEW.model, NEW.model_name,
                NEW.res_id, NEW.res_name, NEW.changes, NEW.ip_address)
               IS NOT DISTINCT FROM
               (OLD.id, OLD.timestamp, OLD.user_id, OLD.login, OLD.action, OLD.model, OLD.model_name,
                OLD.res_id, OLD.res_name, OLD.changes, OLD.ip_address) THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION USING
        MESSAGE = 'ISMS аудит лог: ' || TG_OP || ' зөвшөөрөгдөхгүй (ISO/IEC 27001:2022 A.8.15)',
        ERRCODE = 'insufficient_privilege';
END
$fn$;
"""


def backfill_chain(env):
    """Гинжинд ороогүй (seq IS NULL) бичлэгүүдийг id өсөхөөр гинжилнэ. Аль хэдийн гинжтэй бол юу ч хийхгүй."""
    cr = env.cr
    head = env['isms.audit.chain.head'].sudo()._lock_head()
    cr.execute("SELECT COUNT(*) FROM isms_audit_log WHERE seq IS NULL")
    if not cr.fetchone()[0]:
        return 0
    cr.execute("SELECT set_config(%s, 'on', true)", (BACKFILL_GUC,))
    last_seq, prev_hash, done = head.last_seq, head.last_hash, 0
    while True:
        cr.execute("""
            SELECT id, timestamp, user_id, action, model, res_id, res_name, changes, ip_address
              FROM isms_audit_log
             WHERE seq IS NULL
             ORDER BY id
             LIMIT %s
        """, (BACKFILL_BATCH,))
        columns = [col[0] for col in cr.description]
        rows = cr.fetchall()
        if not rows:
            break
        for values in rows:
            row = dict(zip(columns, values))
            last_seq += 1
            digest = entry_hash_of(canonical_payload(
                seq=last_seq, timestamp=row['timestamp'], user_id=row['user_id'], action=row['action'],
                model=row['model'], res_id=row['res_id'], res_name=row['res_name'],
                changes=row['changes'], ip=row['ip_address'], prev_hash=prev_hash))
            cr.execute("UPDATE isms_audit_log SET seq = %s, prev_hash = %s, entry_hash = %s WHERE id = %s",
                       (last_seq, prev_hash, digest, row['id']))
            prev_hash = digest
            done += 1
    cr.execute("SELECT set_config(%s, 'off', true)", (BACKFILL_GUC,))
    head.write({'last_seq': last_seq, 'last_hash': prev_hash})
    _logger.info('Audit chain backfill: %s existing rows chained', done)
    return done


def install_trigger(cr):
    cr.execute(GUARD_FUNCTION_SQL)
    cr.execute('DROP TRIGGER IF EXISTS %s ON isms_audit_log' % ROW_TRIGGER)
    cr.execute('CREATE TRIGGER %s BEFORE UPDATE OR DELETE ON isms_audit_log FOR EACH ROW '
               'EXECUTE FUNCTION %s()' % (ROW_TRIGGER, GUARD_FUNCTION))
    cr.execute('DROP TRIGGER IF EXISTS %s ON isms_audit_log' % STATEMENT_TRIGGER)
    cr.execute('CREATE TRIGGER %s BEFORE TRUNCATE ON isms_audit_log FOR EACH STATEMENT '
               'EXECUTE FUNCTION %s()' % (STATEMENT_TRIGGER, GUARD_FUNCTION))


def remove_trigger(cr):
    cr.execute('DROP TRIGGER IF EXISTS %s ON isms_audit_log' % ROW_TRIGGER)
    cr.execute('DROP TRIGGER IF EXISTS %s ON isms_audit_log' % STATEMENT_TRIGGER)
    cr.execute('DROP FUNCTION IF EXISTS %s()' % GUARD_FUNCTION)


def post_init_hook(env):
    backfill_chain(env)
    install_trigger(env.cr)
    _logger.info('Audit chain guard trigger installed')


def uninstall_hook(env):
    remove_trigger(env.cr)
    _logger.info('Audit chain guard trigger removed')
