# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models


class BroilerFarmDashboard(models.Model):
    _name = "broiler.farm.dashboard"
    _description = "Dashboard Granja Pollos"
    _rec_name = "display_name"

    display_name = fields.Char(string="Dashboard", compute="_compute_display_name", store=False)

    # KPIs principales
    total_flocks = fields.Integer(string="Total Lotes", compute="_compute_kpis")
    active_flocks = fields.Integer(string="Lotes Activos", compute="_compute_kpis")
    closed_flocks = fields.Integer(string="Lotes Cerrados", compute="_compute_kpis")
    draft_flocks = fields.Integer(string="Lotes en Borrador", compute="_compute_kpis")

    total_birds = fields.Integer(string="Total Aves", compute="_compute_kpis")
    alive_birds = fields.Integer(string="Aves Vivas", compute="_compute_kpis")
    dead_birds = fields.Integer(string="Mortalidad Total", compute="_compute_kpis")

    total_cost = fields.Float(string="Costo Total Operativo", compute="_compute_kpis", digits=(16, 2))
    total_feed_cost = fields.Float(string="Costo Alimento", compute="_compute_kpis", digits=(16, 2))

    avg_weight_g = fields.Float(string="Peso Promedio (g)", compute="_compute_kpis", digits=(16, 2))
    avg_fcr = fields.Float(string="FCR Promedio", compute="_compute_kpis", digits=(16, 3))

    # Picks pendientes - filtrados por broiler
    pending_pickings_count = fields.Integer(string="Pickings Pendientes", compute="_compute_kpis")
    pending_pickings_ids = fields.Many2many(
        "stock.picking",
        string="Pickings Pendientes por Confirmar",
        compute="_compute_kpis"
    )

    # today's logs
    today_logs_count = fields.Integer(string="Registros de Hoy", compute="_compute_kpis")

    # Graph data
    flocks_graph = fields.Text(string="Gráfico Lotes", compute="_compute_graphs")
    pickings_graph = fields.Text(string="Gráfico Pickings", compute="_compute_graphs")

    @api.depends("display_name")
    def _compute_display_name(self):
        self.display_name = "Dashboard Granja"

    def _compute_kpis(self):
        for rec in self:
            flock_model = self.env["broiler.flock"]
            all_flocks = flock_model.search([])
            active_flocks = all_flocks.filtered(lambda f: f.state == "active")
            closed_flocks = all_flocks.filtered(lambda f: f.state == "closed")
            draft_flocks = all_flocks.filtered(lambda f: f.state == "draft")

            rec.total_flocks = len(all_flocks)
            rec.active_flocks = len(active_flocks)
            rec.closed_flocks = len(closed_flocks)
            rec.draft_flocks = len(draft_flocks)

            rec.total_birds = sum(all_flocks.mapped("initial_qty") or [0])
            rec.alive_birds = sum(all_flocks.mapped("alive_qty") or [0])
            rec.dead_birds = sum(all_flocks.mapped("dead_qty") or [0])

            rec.total_cost = sum(all_flocks.mapped("total_cost") or [0])
            rec.total_feed_cost = sum(all_flocks.mapped("cost_feed") or [0])

            weights = active_flocks.mapped("avg_weight_g")
            rec.avg_weight_g = sum(weights) / len(weights) if weights else 0.0

            fcrs = active_flocks.mapped("fcr")
            rec.avg_fcr = sum(fcrs) / len(fcrs) if fcrs else 0.0

            # Pickings filtrados por broiler (tiene broiler_flock_id o tipo de picking de salida broiler)
            picking_model = self.env["stock.picking"]
            broiler_picking_type = self.env.ref("broiler_farm.picking_type_salida_broiler", False)
            
            domain = [
                ("state", "in", ["assigned", "waiting", "confirmed"]),
            ]
            if broiler_picking_type:
                domain.append(("picking_type_id", "=", broiler_picking_type.id))
            
            pending_pickings = picking_model.search(domain)
            rec.pending_pickings_count = len(pending_pickings)
            rec.pending_pickings_ids = [(6, 0, pending_pickings.ids)]

            today = fields.Date.today()
            log_model = self.env["broiler.daily.log"]
            rec.today_logs_count = log_model.search_count([("date", "=", today)])

    def _compute_graphs(self):
        for rec in self:
            # Gráfico de lotes por estado (formato correcto para dashboard_graph)
            flocks_data = [{
                'key': 'Lotes',
                'values': [
                    {'label': 'Activos', 'value': rec.active_flocks or 0, 'type': 'past'},
                    {'label': 'Cerrados', 'value': rec.closed_flocks or 0, 'type': 'present'},
                    {'label': 'Borrador', 'value': rec.draft_flocks or 0, 'type': 'future'},
                ]
            }]
            rec.flocks_graph = json.dumps(flocks_data)

            # Gráfico de pickings
            pickings_data = [{
                'key': 'Pickings',
                'values': [
                    {'label': 'Pendientes', 'value': rec.pending_pickings_count or 0, 'type': 'past'},
                ]
            }]
            rec.pickings_graph = json.dumps(pickings_data)

    def action_view_pending_pickings(self):
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

    @api.model
    def get_dashboard_data(self):
        self.ensure_one()
        return {
            "total_flocks": self.total_flocks,
            "active_flocks": self.active_flocks,
            "closed_flocks": self.closed_flocks,
            "draft_flocks": self.draft_flocks,
            "alive_birds": self.alive_birds,
            "dead_birds": self.dead_birds,
            "total_cost": self.total_cost,
            "total_feed_cost": self.total_feed_cost,
            "avg_weight_g": self.avg_weight_g,
            "avg_fcr": self.avg_fcr,
            "pending_pickings_count": self.pending_pickings_count,
            "today_logs_count": self.today_logs_count,
        }
