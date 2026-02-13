# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class BroilerDailyLog(models.Model):
    _name = "broiler.daily.log"
    _description = "Registro Diario - Pollos de Engorde"
    _order = "date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    flock_id = fields.Many2one(
        "broiler.flock", string="Lote",
        required=True, ondelete="cascade", index=True, tracking=True
    )
    date = fields.Date(
        string="Fecha", required=True,
        default=fields.Date.context_today, tracking=True
    )

    # ✅ ahora usamos product.template para que siempre liste
    feed_starter_product_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto Alimento Inicio",
        domain=[("type", "=", "consu")],
    )

    feed_finisher_product_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto Alimento Final",
        domain=[("type", "=", "consu")],
    )

    feed_starter_kg = fields.Float(string="Alimento Inicio (kg)", digits=(16, 3), default=0.0)
    feed_finisher_kg = fields.Float(string="Alimento Final (kg)", digits=(16, 3), default=0.0)
    
    # Stock disponible al momento del registro (para referencia)
    starter_stock_available = fields.Float(
        string='Stock Disponible - Inicio',
        compute='_compute_stock_available_daily',
        digits='Product Unit',
        store=True,
        help='Stock disponible del producto de alimento inicio al crear este registro'
    )
    
    finisher_stock_available = fields.Float(
        string='Stock Disponible - Final',
        compute='_compute_stock_available_daily',
        digits='Product Unit',
        store=True,
        help='Stock disponible del producto de alimento final al crear este registro'
    )

    feed_kg = fields.Float(
        string="Alimento Total (kg)",
        compute="_compute_feed_total",
        store=True,
        digits=(16, 3),
    )

    water_l = fields.Float(string="Agua (L)", digits=(16, 2), default=0.0)
    dead_qty = fields.Integer(string="Mortalidad (unid)", default=0)
    culled_qty = fields.Integer(string="Descartes (unid)", default=0)

    avg_weight_g = fields.Float(string="Peso prom. muestreo (g)", digits=(16, 2), default=0.0)
    sample_size = fields.Integer(string="Muestra (aves)", default=0)

    notes = fields.Text(string="Observaciones")
    medication = fields.Text(string="Medicación")
    vaccine = fields.Text(string="Vacuna")

    stock_move_ids = fields.One2many(
        "stock.move",
        "broiler_daily_log_id",
        string="Movimientos de Consumo",
        readonly=True,
        copy=False,  # No copiar movimientos al duplicar
    )

    _sql_constraints = [
        ("uniq_flock_date", "unique(flock_id, date)", "Ya existe un registro para este lote en esa fecha.")
    ]

    # -----------------------
    # DEBUG / LOG
    # -----------------------
    @api.onchange("flock_id")
    def _onchange_flock_id_set_products(self):
        goods = self.env["product.template"].search([("type", "=", "consu")], limit=20)
        _logger.warning("ONCHANGE flock_id=%s -> goods templates visibles=%s, muestra=%s",
                        self.flock_id.id if self.flock_id else None,
                        len(goods),
                        goods.mapped("name"))

        for r in self:
            if r.flock_id:
                if not r.feed_starter_product_tmpl_id:
                    r.feed_starter_product_tmpl_id = r.flock_id.feed_starter_product_tmpl_id
                if not r.feed_finisher_product_tmpl_id:
                    r.feed_finisher_product_tmpl_id = r.flock_id.feed_finisher_product_tmpl_id

    # -----------------------
    # COMPUTE / VALIDATE
    # -----------------------
    @api.depends("feed_starter_kg", "feed_finisher_kg")
    def _compute_feed_total(self):
        for r in self:
            r.feed_kg = (r.feed_starter_kg or 0.0) + (r.feed_finisher_kg or 0.0)

    @api.constrains(
        "dead_qty", "culled_qty",
        "feed_starter_kg", "feed_finisher_kg",
        "water_l", "avg_weight_g", "sample_size"
    )
    def _check_values(self):
        for r in self:
            for f in [
                "dead_qty", "culled_qty",
                "feed_starter_kg", "feed_finisher_kg",
                "water_l", "avg_weight_g", "sample_size"
            ]:
                val = r[f]
                if val is not None and val < 0:
                    raise ValidationError("No se permiten valores negativos en el registro diario.")

            if r.avg_weight_g and r.avg_weight_g > 0 and (not r.sample_size or r.sample_size <= 0):
                raise ValidationError("Si registra peso promedio, debe indicar una muestra (aves) mayor que 0.")

            if r.flock_id and r.flock_id.state == "closed":
                raise ValidationError("No puede registrar datos porque el lote está CERRADO.")

            if (r.feed_starter_kg > 0 and not r.feed_starter_product_tmpl_id) or \
               (r.feed_finisher_kg > 0 and not r.feed_finisher_product_tmpl_id):
                raise ValidationError("Selecciona el producto de alimento (inicio/final) para poder rebajar inventario.")

    # -----------------------
    # STOCK
    # -----------------------
    def _get_salida_broiler_picking_type(self):
        picking_type = self.env.ref(
            'broiler_farm.picking_type_salida_broiler', raise_if_not_found=False
        )
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('sequence_code', '=', 'SB'),
                ('code', '=', 'outgoing'),
            ], limit=1)
        return picking_type

    def _sync_stock_consumption_moves(self):
        self.ensure_one()
        flock = self.flock_id
        if not flock:
            return

        starter = (
            self.env["product.product"].search(
                [("product_tmpl_id", "=", self.feed_starter_product_tmpl_id.id)], limit=1
            )
            if self.feed_starter_product_tmpl_id
            else False
        )
        finisher = (
            self.env["product.product"].search(
                [("product_tmpl_id", "=", self.feed_finisher_product_tmpl_id.id)], limit=1
            )
            if self.feed_finisher_product_tmpl_id
            else False
        )

        want_starter = float(self.feed_starter_kg or 0.0)
        want_finisher = float(self.feed_finisher_kg or 0.0)

        if self.stock_move_ids:
            pickings_to_remove = self.stock_move_ids.mapped('picking_id')
            moves_to_remove = self.stock_move_ids
            for move in moves_to_remove:
                if move.state == 'done':
                    move.state = 'assigned'
                elif move.state not in ('draft', 'waiting', 'confirmed', 'assigned', 'cancel'):
                    move.state = 'cancel'
            for picking in pickings_to_remove:
                if picking.state == 'done':
                    for m in picking.move_ids:
                        m.state = 'assigned'
                    picking.state = 'assigned'
                if picking.state != 'cancel':
                    picking.action_cancel()
            moves_to_remove.filtered(lambda m: m.state == 'cancel').unlink()
            pickings_to_remove.filtered(lambda p: p.state == 'cancel').unlink()

        if want_starter <= 0 and want_finisher <= 0:
            return

        picking_type = self._get_salida_broiler_picking_type()
        if not picking_type:
            raise ValidationError(
                "No se encontró el tipo de operación 'Salida Broiler'. "
                "Reinstala el módulo broiler_farm."
            )

        src = picking_type.default_location_src_id or self.env.ref("stock.stock_location_stock")
        dest = picking_type.default_location_dest_id
        if not dest:
            dest = flock._get_consumption_location()

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src.id,
            'location_dest_id': dest.id,
            'origin': 'Consumo %s - %s' % (flock.name, self.date),
            'scheduled_date': self.date,
            'broiler_flock_id': flock.id,
        })

        move_vals_list = []
        if want_starter > 0 and starter:
            move_vals_list.append({
                'reference': 'Consumo Inicio %s' % starter.display_name,
                'product_id': starter.id,
                'product_uom_qty': want_starter,
                'product_uom': starter.uom_id.id,
                'location_id': src.id,
                'location_dest_id': dest.id,
                'picking_id': picking.id,
                'broiler_daily_log_id': self.id,
                'origin': picking.origin,
            })

        if want_finisher > 0 and finisher:
            move_vals_list.append({
                'reference': 'Consumo Final %s' % finisher.display_name,
                'product_id': finisher.id,
                'product_uom_qty': want_finisher,
                'product_uom': finisher.uom_id.id,
                'location_id': src.id,
                'location_dest_id': dest.id,
                'picking_id': picking.id,
                'broiler_daily_log_id': self.id,
                'origin': picking.origin,
            })

        if not move_vals_list:
            picking.unlink()
            return

        self.env['stock.move'].create(move_vals_list)

        picking.action_confirm()
        picking.action_assign()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            _logger.info(f"DEBUG: BroilerDailyLog.create llamado - ID: {rec.id}, Flock: {rec.flock_id.name if rec.flock_id else 'None'}")
            rec._sync_stock_consumption_moves()
        return records

    @api.depends('flock_id.feed_starter_product_tmpl_id', 'flock_id.feed_finisher_product_tmpl_id', 'flock_id')
    def _compute_stock_available_daily(self):
        """Calcular stock disponible de los productos del lote al momento del registro"""
        for record in self:
            starter_stock = 0.0
            finisher_stock = 0.0
            
            # Stock disponible del alimento inicio (del lote)
            if record.flock_id and record.flock_id.feed_starter_product_tmpl_id:
                starter_stock = record.flock_id.starter_stock_available or 0.0
            
            # Stock disponible del alimento final (del lote)
            if record.flock_id and record.flock_id.feed_finisher_product_tmpl_id:
                finisher_stock = record.flock_id.finisher_stock_available or 0.0
            
            record.starter_stock_available = starter_stock
            record.finisher_stock_available = finisher_stock

    def write(self, vals):
        res = super().write(vals)
        feed_fields = {'feed_starter_kg', 'feed_finisher_kg',
                       'feed_starter_product_tmpl_id', 'feed_finisher_product_tmpl_id'}
        if feed_fields & set(vals):
            for rec in self:
                rec._sync_stock_consumption_moves()
        return res

    def action_reprocess_stock_moves(self):
        if not self:
            self = self.search([])
        for rec in self:
            _logger.info(f"REPROCESS: Re-procesando registro diario ID {rec.id} - Lote {rec.flock_id.name}")
            rec._sync_stock_consumption_moves()
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
