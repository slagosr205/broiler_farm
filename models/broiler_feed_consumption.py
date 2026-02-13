# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class BroilerFeedConsumption(models.Model):
    _name = 'broiler.feed.consumption'
    _description = 'Consumo de Alimento para Lotes'
    _order = 'date desc, lot_id desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    lot_id = fields.Many2one(
        'broiler.flock',
        string='Lote',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )
    
    date = fields.Date(
        string='Fecha de Consumo',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Producto de Alimento',
        required=True,
        domain=[('type', '=', 'consu')],
        tracking=True
    )
    
    product_tmpl_id = fields.Many2one(
        related='product_id.product_tmpl_id',
        string='Plantilla de Producto',
        readonly=True,
        store=True
    )
    
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unidad de Medida',
        related='product_id.uom_id',
        readonly=True,
        store=True
    )
    
    qty = fields.Float(
        string='Cantidad',
        required=True,
        digits='Product Unit',
        tracking=True,
        help='Cantidad consumida de alimento'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('done', 'Realizado'),
        ('cancel', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    # Referencias para trazabilidad
   # move_ids = fields.One2many(
    #    'stock.move',
        #'broiler_feed_consumption_id',
     #   string='Movimientos de Stock'
    #)
    
    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de Producción',
        readonly=True
    )
    
    picking_id = fields.Many2one(
        'stock.picking',
        string='Transferencia',
        readonly=True
    )
    
    # Campo computado para mostrar nombre descriptivo
    display_name = fields.Char(
        compute='_compute_display_name',
        string='Nombre Descriptivo',
        store=True
    )
    
    @api.depends('lot_id.name', 'date', 'product_id.name')
    def _compute_display_name(self):
        for record in self:
            parts = [
                record.lot_id.name if record.lot_id else 'Sin Lote',
                record.product_id.name if record.product_id else 'Sin Producto'
            ]
            record.display_name = ' - '.join(filter(None, parts))
    
    @api.constrains('qty')
    def _check_qty(self):
        for record in self:
            if record.qty <= 0:
                raise ValidationError('La cantidad debe ser mayor que 0')
    
    def action_confirm(self):
        """Confirmar el consumo y generar movimiento de producción"""
        self.ensure_one()
        if self.state != 'draft':
            return
            
        # Obtener ubicación del lote (ubicación interna donde está el stock)
        lot_location = self.lot_id.location_id
        if not lot_location:
            lot_location = self.env.ref('stock.stock_location_stock')
        
        # Buscar ubicación virtual de producción (consumo productivo)
        production_location = self.env['stock.location'].search([
            ('usage', '=', 'production'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        if not production_location:
            # Crear ubicación virtual de producción si no existe
            production_location = self.env['stock.location'].create({
                'name': 'Consumo Producción Avícola',
                'usage': 'production',
                'company_id': self.company_id.id,
                'location_id': self.env.ref('stock.stock_location_stock').id,
            })
        
        # Crear orden de producción para consumo de materia prima
        production_vals = {
            'name': f'Consumo: {self.display_name}',
            'product_id': self.product_id.id,
            'product_qty': self.qty,
            'product_uom_id': self.product_uom_id.id,
            'location_src_id': lot_location.id,  # Desde donde sale el stock
            'location_dest_id': production_location.id,  # Hacia consumo virtual
            'origin': f'Lote: {self.lot_id.name}',
            'date_planned_start': self.date,
            'date_planned_finished': self.date,
            'user_id': self.env.user.id,
            'company_id': self.company_id.id,
            'state': 'confirmed',
        }
        
        production = self.env['mrp.production'].create(production_vals)
        
        # Confirmar producción para reservar stock
        production.action_confirm()
        
        # Marcar el consumo como confirmado
        self.write({
            'state': 'confirmed',
            'production_id': production.id
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Orden de Producción',
            'view_mode': 'form',
            'res_model': 'mrp.production',
            'res_id': production.id,
            'target': 'current',
        }
    
    def action_mark_done(self):
        """Marcar como realizado y generar consumos finales"""
        self.ensure_one()
        if self.state != 'confirmed':
            return
            
        if not self.production_id:
            raise ValidationError('No hay orden de producción asociada')
        
        # Marcar producción como hecha
        self.production_id.button_mark_done()
        
        # Actualizar estado
        self.write({'state': 'done'})
        
        return True
    
    def action_cancel(self):
        """Cancelar el consumo"""
        self.ensure_one()
        
        if self.production_id and self.production_id.state not in ('done', 'cancel'):
            self.production_id.action_cancel()
        
        self.write({'state': 'cancel'})
        return True
    
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            # Crear automáticamente una entrada en el registro diario del lote
            if record.lot_id and record.state in ('done', 'confirmed'):
                self.env['broiler.daily.log'].create({
                    'flock_id': record.lot_id.id,
                    'date': record.date,
                    'feed_starter_product_tmpl_id': record.product_tmpl_id.id if record.product_tmpl_id else False,
                    'feed_starter_kg': record.qty if 'INICIO' in record.product_id.name.upper() else 0.0,
                    'feed_finisher_product_tmpl_id': record.product_tmpl_id.id if record.product_tmpl_id else False,
                    'feed_finisher_kg': record.qty if 'FINAL' in record.product_id.name.upper() else 0.0,
                    'notes': f'Consumo registrado desde módulo de consumo: {record.qty}kg',
                })
        return records