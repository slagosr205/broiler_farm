from odoo import api, fields, models
from odoo.exceptions import ValidationError

class BroilerProcessFlockWizard(models.TransientModel):
    _name = "broiler.process.flock.wizard"
    _description = "Procesar lote (MRP)"

    flock_id = fields.Many2one("broiler.flock", required=True)
    processed_weight_kg = fields.Float(string="Kg procesados", digits=(16,3), required=True)
    processed_qty = fields.Integer(string="Pollos procesados", required=True)

    def action_process(self):
        self.ensure_one()
        flock = self.flock_id

        if not flock.processed_product_id:
            raise ValidationError("Configura el producto 'Pollo Procesado' en el lote.")
        if not flock.live_bird_product_id:
            raise ValidationError("Configura el producto 'Pollo Vivo' en el lote.")
        if self.processed_weight_kg <= 0:
            raise ValidationError("Kg procesados debe ser > 0")
        if self.processed_qty <= 0:
            raise ValidationError("Pollos procesados debe ser > 0")

        # Crea una orden de fabricación (sin BOM: genera consumo manual)
        mo = self.env["mrp.production"].create({
            "product_id": flock.processed_product_id.id,
            "product_qty": self.processed_weight_kg,
            "product_uom_id": flock.processed_product_id.uom_id.id,
            "location_src_id": flock.location_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_stock").id,
            "broiler_flock_id": flock.id,
        })

        # Agrega movimiento de consumo de pollo vivo (unidades)
        self.env["stock.move"].create({
            "name": "Consumo Pollo Vivo",
            "product_id": flock.live_bird_product_id.id,
            "product_uom_qty": self.processed_qty,
            "product_uom": flock.live_bird_product_id.uom_id.id,
            "location_id": flock.location_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_scrapped").id,  # o una ubicación Consumo
            "raw_material_production_id": mo.id,
        })

        flock.write({
            "processed_weight_kg": self.processed_weight_kg,
            "processed_qty": self.processed_qty,
            "state": "processing",
        })

        # (Opcional) confirmar MO
        mo.action_confirm()

        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.production",
            "view_mode": "form",
            "res_id": mo.id,
        }
