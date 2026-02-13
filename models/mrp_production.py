from odoo import api, fields, models

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    broiler_flock_id = fields.Many2one("broiler.flock", string="Lote")

    @api.onchange("broiler_flock_id")
    def _onchange_broiler_flock_id(self):
        for mo in self:
            if mo.broiler_flock_id:
                # Consumo desde la ubicación del lote
                mo.location_src_id = mo.broiler_flock_id.location_id
