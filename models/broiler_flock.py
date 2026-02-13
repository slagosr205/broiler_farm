# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError
import re


class BroilerFlock(models.Model):
    _name = "broiler.flock"
    _description = "Lote de Pollos de Engorde"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)

    # Nombre automático: LOTE_DDMMAAAA(-NNN)
    name = fields.Char(string="Lote", required=True, tracking=True, readonly=True, default="/")

    date_in = fields.Datetime(string="Fecha y Hora de Ingreso", required=True, tracking=True)
    initial_qty = fields.Integer(string="Cantidad Inicial", required=True, tracking=True)

    farm_name = fields.Char(string="Granja")
    house = fields.Char(string="Galpón")
    supplier = fields.Char(string="Proveedor")
    strain = fields.Char(string="Línea/Genética")

    state = fields.Selection(
        [("draft", "Borrador"), ("active", "Activo"), ("closed", "Cerrado")],
        default="draft",
        tracking=True,
    )

    daily_log_ids = fields.One2many("broiler.daily.log", "flock_id", string="Registros diarios")

    # Productos configurables (para sugerir en el daily log)
    feed_starter_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto Alimento Inicio',
        domain=[('type', '=', 'consu')],
        required=True,  # Si es obligatorio
        ondelete='restrict',  # Previene eliminar productos en uso
        check_company=True,  # Si trabajas con multi-compañía
    )

    feed_finisher_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Producto Alimento Final',
        domain=[('type', '=', 'consu')],
        required=True,
        ondelete='restrict',
        check_company=True,
    )
    
    # Stock disponible de productos seleccionados (computado)
    starter_stock_available = fields.Float(
        string='Stock Disponible - Alimento Inicio',
        compute='_compute_stock_available',
        digits='Product Unit',
        store=True,
        help='Cantidad disponible del producto de alimento inicio'
    )
    
    finisher_stock_available = fields.Float(
        string='Stock Disponible - Alimento Final', 
        compute='_compute_stock_available',
        digits='Product Unit',
        store=True,
        help='Cantidad disponible del producto de alimento final'
    )

    # Ubicación por lote (opcional, recomendado)
    location_id = fields.Many2one("stock.location", string="Ubicación del lote", readonly=True)

    # Costeo operativo (sin contabilidad)
    total_cost = fields.Float(string="Costo Operativo Acumulado", digits=(16, 2), default=0.0)
    cost_feed = fields.Float(string="Costo Alimento", digits=(16, 2), default=0.0)
    cost_other = fields.Float(string="Otros Costos Manuales", digits=(16, 2), default=0.0)

    # KPIs
    age_days = fields.Integer(string="Edad (días)", compute="_compute_kpis", store=True)
    dead_qty = fields.Integer(string="Mortalidad acumulada", compute="_compute_kpis", store=True)
    culled_qty = fields.Integer(string="Descartes acumulados", compute="_compute_kpis", store=True)
    alive_qty = fields.Integer(string="Aves vivas", compute="_compute_kpis", store=True)
    mortality_pct = fields.Float(string="% Bajas", compute="_compute_kpis", store=True, digits=(16, 2))

    feed_total_kg = fields.Float(string="Alimento acumulado (kg)", compute="_compute_kpis", store=True, digits=(16, 3))
    water_total_l = fields.Float(string="Agua acumulada (L)", compute="_compute_kpis", store=True, digits=(16, 2))
    avg_weight_g = fields.Float(string="Peso promedio (g)", compute="_compute_kpis", store=True, digits=(16, 2))
    fcr = fields.Float(string="FCR (estimado)", compute="_compute_kpis", store=True, digits=(16, 3))

    _sql_constraints = [
        ("uniq_broiler_flock_name", "unique(name, company_id)", "Ya existe un lote con ese nombre.")
    ]

    @api.constrains("initial_qty")
    def _check_initial_qty(self):
        for r in self:
            if r.initial_qty <= 0:
                raise ValidationError("La cantidad inicial debe ser mayor que 0.")

    # -------------------------
    # Ubicaciones
    # -------------------------
    def _get_broiler_parent_location(self):
        StockLoc = self.env["stock.location"]
        stock_loc = self.env.ref("stock.stock_location_stock")
        parent = StockLoc.search([("name", "=", "Broiler"), ("location_id", "=", stock_loc.id)], limit=1)
        if not parent:
            parent = StockLoc.create({
                "name": "Broiler",
                "usage": "internal",
                "location_id": stock_loc.id,
            })
        return parent

    def _get_consumption_location(self):
        StockLoc = self.env["stock.location"]
        parent = self._get_broiler_parent_location()
        cons = StockLoc.search([("name", "=", "Consumo"), ("location_id", "=", parent.id)], limit=1)
        if not cons:
            cons = StockLoc.create({
                "name": "Consumo",
                "usage": "production",
                "location_id": parent.id,
            })
        return cons

    @api.model_create_multi
    def create(self, vals_list):
        # Generar nombre
        for vals in vals_list:
            date_in = vals.get("date_in") or fields.Datetime.now()
            date_in = fields.Datetime.to_datetime(date_in)
            company_id = vals.get("company_id") or self.env.company.id

            if not vals.get("name") or vals.get("name") == "/":
                vals["name"] = self._make_lote_name(date_in, company_id)

        records = super().create(vals_list)

        # Crear ubicación por lote (tipo Produccion)
        for flock in records:
            if not flock.location_id and flock.name and flock.name.startswith("LOTE"):
                parent = flock._get_broiler_parent_location()
                loc = self.env["stock.location"].create({
                    "name": f"{flock.name}",
                    "usage": "production",
                    "location_id": parent.id,
                })
                flock.location_id = loc.id

        return records

    def write(self, vals):
        # Si cambian date_in en borrador, re-nombrar
        if "date_in" in vals:
            new_date = fields.Datetime.to_datetime(vals["date_in"])
            for rec in self:
                if rec.state == "draft" and rec.name and rec.name.startswith("LOTE_"):
                    vals2 = dict(vals)
                    vals2["name"] = rec._make_lote_name(new_date)
                    super(BroilerFlock, rec).write(vals2)
            return True
        return super().write(vals)

    def _make_lote_name(self, date_in, company_id=None):
        if company_id is None:
            company_id = self.company_id.id if self.company_id else self.env.company.id
        ddmmyyyy = date_in.strftime("%d%m%Y")
        now = fields.Datetime.now().strftime("%H%M%S")
        return f"LOTE_{ddmmyyyy}{now}"

    def action_view_pending_pickings(self):
        self.ensure_one()
        broiler_picking_type = self.env.ref("broiler_farm.picking_type_salida_broiler", False)
        domain = [("state", "in", ["assigned", "waiting", "confirmed"])]
        if broiler_picking_type:
            domain.append(("picking_type_id", "=", broiler_picking_type.id))
        return {
            "name": "Pickings Pendientes",
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"create": False},
        }

    # -------------------------
    # KPIs
    # -------------------------
    @api.depends(
        "date_in", "initial_qty",
        "daily_log_ids.date",
        "daily_log_ids.dead_qty",
        "daily_log_ids.culled_qty",
        "daily_log_ids.feed_kg",
        "daily_log_ids.water_l",
        "daily_log_ids.avg_weight_g",
    )
    def _compute_kpis(self):
        for flock in self:
            if flock.date_in:
                today = fields.Datetime.now()
                flock.age_days = max((today - flock.date_in).days, 0)
            else:
                flock.age_days = 0

            dead = sum(flock.daily_log_ids.mapped("dead_qty"))
            culled = sum(flock.daily_log_ids.mapped("culled_qty"))
            total_out = dead + culled

            flock.dead_qty = dead
            flock.culled_qty = culled
            flock.alive_qty = max((flock.initial_qty or 0) - total_out, 0)
            flock.mortality_pct = (total_out / flock.initial_qty * 100.0) if flock.initial_qty else 0.0

            flock.feed_total_kg = sum(flock.daily_log_ids.mapped("feed_kg"))
            flock.water_total_l = sum(flock.daily_log_ids.mapped("water_l"))

            last_with_weight = flock.daily_log_ids.filtered(lambda x: x.avg_weight_g and x.avg_weight_g > 0).sorted("date")
            flock.avg_weight_g = last_with_weight[-1].avg_weight_g if last_with_weight else 0.0

            initial_weight_g = 40.0
            gain_per_bird_kg = max((flock.avg_weight_g - initial_weight_g) / 1000.0, 0.0)
            total_gain_kg = gain_per_bird_kg * flock.alive_qty
            flock.fcr = (flock.feed_total_kg / total_gain_kg) if total_gain_kg > 0 else 0.0

    # -------------------------
    # Botones
    # -------------------------
    def action_set_active(self):
        self.write({"state": "active"})

    def action_set_closed(self):
        self.write({"state": "closed"})
    
    @api.depends('feed_starter_product_tmpl_id', 'feed_finisher_product_tmpl_id')
    def _compute_stock_available(self):
        """Calcular stock disponible de los productos de alimento"""
        for flock in self:
            starter_qty = 0.0
            finisher_qty = 0.0
            
            # Stock disponible del alimento inicio
            if flock.feed_starter_product_tmpl_id:
                starter_variant = self.env['product.product'].search([
                    ('product_tmpl_id', '=', flock.feed_starter_product_tmpl_id.id)
                ], limit=1)
                if starter_variant:
                    # Buscar stock en todas las ubicaciones internas
                    quants = self.env['stock.quant'].search([
                        ('product_id', '=', starter_variant.id),
                        ('location_id.usage', '=', 'internal'),
                        ('quantity', '>', 0)
                    ])
                    starter_qty = sum(quants.mapped('quantity'))
            
            # Stock disponible del alimento final
            if flock.feed_finisher_product_tmpl_id:
                finisher_variant = self.env['product.product'].search([
                    ('product_tmpl_id', '=', flock.feed_finisher_product_tmpl_id.id)
                ], limit=1)
                if finisher_variant:
                    quants = self.env['stock.quant'].search([
                        ('product_id', '=', finisher_variant.id),
                        ('location_id.usage', '=', 'internal'),
                        ('quantity', '>', 0)
                    ])
                    finisher_qty = sum(quants.mapped('quantity'))
            
            flock.starter_stock_available = starter_qty
            flock.finisher_stock_available = finisher_qty
    
    def action_update_other_costs(self):
        """Wizard para actualizar otros costos manualmente"""
        return {
            'name': 'Actualizar Costos Manuales',
            'type': 'ir.actions.act_window',
            'res_model': 'broiler.flock.cost.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_flock_id': self.id},
        }

