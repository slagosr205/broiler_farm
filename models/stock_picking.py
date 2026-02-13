import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    broiler_flock_id = fields.Many2one("broiler.flock", string="Lote")

    @api.onchange("broiler_flock_id")
    def _onchange_broiler_flock_id(self):
        for p in self:
            if p.broiler_flock_id and p.picking_type_id.code == "incoming":
                p.location_dest_id = p.broiler_flock_id.location_id

    def button_validate(self):
        res = super().button_validate()
        for picking in self:
            if picking.state != 'done':
                continue
            if picking.picking_type_id.sequence_code != 'SB':
                continue
            if not picking.broiler_flock_id:
                continue
            picking._update_broiler_flock_costs()
        return res

    def _update_broiler_flock_costs(self):
        self.ensure_one()
        flock = self.broiler_flock_id
        total_cost = 0.0
        for move in self.move_ids.filtered(lambda m: m.state == 'done'):
            total_cost += move.quantity * move.product_id.standard_price
        if total_cost > 0:
            flock.write({
                'cost_feed': flock.cost_feed + total_cost,
                'total_cost': flock.total_cost + total_cost,
            })
            _logger.info(
                "Costo consumo picking %s - Lote %s: $%.2f",
                self.name, flock.name, total_cost,
            )
