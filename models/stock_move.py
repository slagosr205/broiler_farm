from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    broiler_daily_log_id = fields.Many2one(
        "broiler.daily.log",
        string="Registro Diario Consumo",
        index=True,
        ondelete="set null",
    )
