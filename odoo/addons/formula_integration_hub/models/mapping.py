"""Дотоод модель ↔ гадаад ID холбоос (идемпотент). Холбоосыг хэзээ ч дарж бичихгүй."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FormulaIntegrationMapping(models.Model):
    _name = 'formula.integration.mapping'
    _description = 'Дотоод ↔ гадаад ID холбоос'
    _order = 'endpoint_id, local_model, local_id'

    endpoint_id = fields.Many2one('formula.integration.endpoint', 'Endpoint', required=True,
                                  ondelete='cascade', index=True)
    local_model = fields.Char('Дотоод модел', required=True, index=True)
    local_id = fields.Integer('Дотоод ID', required=True, index=True)
    remote_id = fields.Char('Гадаад ID', required=True, index=True)
    remote_kind = fields.Char('Гадаад төрөл')
    last_seen = fields.Datetime('Сүүлд харсан', default=fields.Datetime.now)

    _sql_constraints = [
        ('local_uniq', 'unique(endpoint_id, local_model, local_id)',
         'Дотоод объект аль хэдийн өөр гадаад ID-тай холбогдсон байна.'),
        ('remote_uniq', 'unique(endpoint_id, local_model, remote_id)',
         'Гадаад ID аль хэдийн өөр дотоод объектод холбогдсон байна.'),
    ]

    @api.model
    def lookup(self, endpoint, local_model, remote_id):
        """Гадаад ID-аар холбоосыг олно (хоосон бол хоосон recordset)."""
        return self.sudo().search([('endpoint_id', '=', endpoint.id),
                                   ('local_model', '=', local_model),
                                   ('remote_id', '=', str(remote_id))], limit=1)

    @api.model
    def remote_for(self, endpoint, local_model, local_id):
        rec = self.sudo().search([('endpoint_id', '=', endpoint.id),
                                  ('local_model', '=', local_model),
                                  ('local_id', '=', local_id)], limit=1)
        return rec.remote_id if rec else False

    @api.model
    def link(self, endpoint, local_model, local_id, remote_id, remote_kind=False):
        """Идемпотент холбоос. Ижил холбоос байвал буцаана; зөрчилтэй бол ValidationError (дарж бичихгүй)."""
        remote_id = str(remote_id)
        by_local = self.sudo().search([('endpoint_id', '=', endpoint.id),
                                       ('local_model', '=', local_model),
                                       ('local_id', '=', local_id)], limit=1)
        if by_local:
            if by_local.remote_id == remote_id:
                return by_local
            raise ValidationError(_('Холбоос зөрчилтэй: дотоод объект өөр гадаад ID-тай байна.'))
        by_remote = self.lookup(endpoint, local_model, remote_id)
        if by_remote:
            raise ValidationError(_('Холбоос зөрчилтэй: гадаад ID өөр дотоод объектод холбогдсон байна.'))
        return self.sudo().create({
            'endpoint_id': endpoint.id,
            'local_model': local_model,
            'local_id': local_id,
            'remote_id': remote_id,
            'remote_kind': remote_kind or False,
        })
