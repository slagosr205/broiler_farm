# -*- coding: utf-8 -*-
from odoo import api, fields, models


class BroilerFlockCostWizard(models.TransientModel):
    _name = 'broiler.flock.cost.wizard'
    _description = 'Wizard para Actualizar Costos del Lote'

    flock_id = fields.Many2one('broiler.flock', string='Lote', required=True)
    cost_description = fields.Char(string='Descripción del Costo', required=True)
    cost_amount = fields.Float(string='Monto del Costo', required=True, digits=(16, 2))
    cost_type = fields.Selection([
        ('medicine', 'Medicina'),
        ('vaccine', 'Vacuna'),
        ('labor', 'Mano de Obra'),
        ('electricity', 'Electricidad'),
        ('water', 'Agua'),
        ('other', 'Otro'),
    ], string='Tipo de Costo', required=True, default='other')
    
    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if 'flock_id' in self._context and self._context.get('default_flock_id'):
            res['flock_id'] = self._context.get('default_flock_id')
        return res

    def action_update_cost(self):
        """Actualizar costos manuales en el lote"""
        self.ensure_one()
        
        if not self.flock_id:
            return {'type': 'ir.actions.act_window_close'}
        
        # Actualizar costos acumulados
        self.flock_id.write({
            'cost_other': self.flock_id.cost_other + self.cost_amount,
            'total_cost': self.flock_id.total_cost + self.cost_amount,
        })
        
        # Crear nota en el registro diario actual si existe
        today = fields.Date.context_today(self)
        daily_log = self.env['broiler.daily.log'].search([
            ('flock_id', '=', self.flock_id.id),
            ('date', '=', today)
        ], limit=1)
        
        if daily_log:
            note = f"Costo manual: {self.cost_description} (${self.cost_amount:.2f})"
            existing_notes = daily_log.notes or ''
            daily_log.notes = f"{existing_notes}\n{note}" if existing_notes else note
        
        return {'type': 'ir.actions.act_window_close'}