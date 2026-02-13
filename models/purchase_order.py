from odoo import fields, models

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    broiler_flock_id = fields.Many2one("broiler.flock", string="Lote", index=True)
