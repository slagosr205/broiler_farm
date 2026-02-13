# -*- coding: utf-8 -*-
from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    broiler_daily_log_id = fields.Many2one(
        'broiler.daily.log',
        string='Registro Diario Consumo',
        ondelete='cascade',
        help='Registro diario que generó este movimiento de consumo',
    )
    
   # broiler_feed_consumption_id = fields.Many2one(
    #    'broiler.feed.consumption',
     #   string='Consumo de Alimento',
      
      #  ondelete='cascade',
       # help='Consumo de alimento que generó este movimiento',
    #)