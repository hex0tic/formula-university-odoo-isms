"""18.0.1.1.0: 2026-11-18 аудитын засвар.

1. A.5.3: техникийн `admin` данс CISO/шинжээч/эзэмшигч/аудиторын бизнес эрхгүй — зөвхөн Reporter + Settings.
2. Импортоор workflow-г тойрсон эрсдэлийн хүлээн зөвшөөрөлт, үлдэгдэл батлалтыг нийцүүлэх.
3. Risk Treatment Plan (Project) даалгаврыг үүсгэх.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if admin:
        remove = [env.ref('university_isms.group_isms_%s' % name).id
                  for name in ('manager', 'analyst', 'asset_owner', 'auditor')]
        admin.write({'groups_id': [(3, gid) for gid in remove]
                     + [(4, env.ref('university_isms.group_isms_reporter').id)]})
    result = env['isms.risk']._isms_repair_workflow_consistency('18.0.1.1.0 migration')
    _logger.info('university_isms 18.0.1.1.0 migration: %s', result)
