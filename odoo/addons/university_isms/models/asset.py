"""Мэдээллийн хөрөнгийн бүртгэл (A.5.9 Inventory, A.5.12 Classification).

Ангилал, амьдралын мөчлөг нь Лекц 8–9-ийн слайд 15–16-аас.
"""
from odoo import api, fields, models

from .risk import LEVEL_RANK, LEVELS

CIA = [('1', '1 — Бага'), ('2', '2 — Дунд'), ('3', '3 — Өндөр')]


class IsmsAsset(models.Model):
    _name = 'isms.asset'
    _description = 'Мэдээллийн хөрөнгө'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'isms.audit.mixin']
    _order = 'code'
    _rec_names_search = ['code', 'name']
    _isms_lock_code = True

    code = fields.Char('Код', required=True, copy=False, readonly=True, default='/', index=True)
    name = fields.Char('Хөрөнгийн нэр', required=True, tracking=True)
    asset_type = fields.Selection([
        ('information', 'Мэдээлэл, өгөгдөл'),
        ('system', 'Систем'),
        ('software', 'Программ хангамж'),
        ('hardware', 'Тоног төхөөрөмж'),
        ('document', 'Баримт бичиг'),
        ('service', 'Үйлчилгээ'),
        ('people', 'Хүн'),
        ('facility', 'Байр, талбай'),
    ], 'Төрөл', required=True, default='information', tracking=True)
    description = fields.Text('Тайлбар')
    department_id = fields.Many2one('hr.department', 'Нэгж', tracking=True)
    owner_id = fields.Many2one('res.users', 'Эзэмшигч (Owner)', tracking=True,
                               help='Хөрөнгийн ангилал, хандах эрхийг шийдвэрлэх хариуцлагатай албан тушаалтан')
    custodian_id = fields.Many2one('res.users', 'Хариуцагч (Custodian)', tracking=True,
                                   help='Өдөр тутмын техникийн арчилгаа, хамгаалалтыг хэрэгжүүлэгч')
    location = fields.Char('Байршил', tracking=True)
    classification = fields.Selection([
        ('public', 'Нийтэд нээлттэй'),
        ('internal', 'Дотоод хэрэглээнд'),
        ('restricted', 'Хязгаарлагдмал'),
        ('confidential', 'Нууц'),
    ], 'Ангилал (Classification)', required=True, default='internal', tracking=True)
    confidentiality = fields.Selection(CIA, 'Нууцлал (C)', required=True, default='2', tracking=True)
    integrity = fields.Selection(CIA, 'Бүрэн бүтэн байдал (I)', required=True, default='2', tracking=True)
    availability = fields.Selection(CIA, 'Хүртээмж (A)', required=True, default='2', tracking=True)
    asset_value = fields.Integer('Үнэ цэнэ max(C,I,A)', compute='_compute_asset_value', store=True,
                                 help='decisions.md D04: хөрөнгийн CIA үнэ цэнэ = max(C, I, A), 1–3')
    criticality = fields.Selection(LEVELS, 'Ач холбогдол', compute='_compute_asset_value', store=True)
    personal_data = fields.Boolean('Хувийн мэдээлэл агуулсан', tracking=True,
                                   help='Хүний хувийн мэдээлэл хамгаалах тухай хуульд хамаарах эсэх')
    lifecycle_stage = fields.Selection([
        ('classify', 'Бүртгэх, ангилах'),
        ('protect', 'Аюулгүй байдлыг хангах'),
        ('restore', 'Сэргээх'),
        ('dispose', 'Устгах'),
        ('secure_dispose', 'Хамгаалалттай устгах'),
        ('archive', 'Архивлах'),
    ], 'Амьдралын мөчлөгийн үе шат', default='protect', tracking=True)
    risk_ids = fields.Many2many('isms.risk', 'isms_asset_risk_rel', 'asset_id', 'risk_id', string='Эрсдэл')
    risk_count = fields.Integer('Эрсдэлийн тоо', compute='_compute_risk_level', store=True)
    risk_level = fields.Selection([('none', 'Үнэлээгүй')] + LEVELS, 'Эрсдэл (Low/Med/High)',
                                  compute='_compute_risk_level', store=True,
                                  help='Холбогдох эрсдэлийн одоогийн хамгийн өндөр түвшин')
    control_ids = fields.Many2many('isms.control', 'isms_asset_control_rel', 'asset_id', 'control_id',
                                   string='Хэрэгжүүлсэн хяналт')
    incident_ids = fields.Many2many('isms.incident', 'isms_incident_asset_rel', 'asset_id', 'incident_id',
                                    string='Инцидент')
    active = fields.Boolean(default=True, tracking=True)

    _sql_constraints = [('code_uniq', 'unique(code)', 'Хөрөнгийн код давхардахгүй байх ёстой.')]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') or vals['code'] == '/':
                vals['code'] = self._isms_next_code('isms.asset')
        return super().create(vals_list)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.name) if rec.code and rec.code != '/' else rec.name

    @api.depends('confidentiality', 'integrity', 'availability')
    def _compute_asset_value(self):
        for rec in self:
            value = max(int(rec.confidentiality or 0), int(rec.integrity or 0), int(rec.availability or 0))
            rec.asset_value = value
            rec.criticality = {3: 'high', 2: 'medium'}.get(value, 'low')

    @api.depends('risk_ids.current_level', 'risk_ids.active')
    def _compute_risk_level(self):
        for rec in self:
            risks = rec.risk_ids.filtered('active')
            rec.risk_count = len(risks)
            levels = [r.current_level for r in risks if r.current_level]
            rec.risk_level = max(levels, key=LEVEL_RANK.get) if levels else 'none'
