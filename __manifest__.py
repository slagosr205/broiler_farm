{
    "name": "Broiler Farm - Gestión de Pollos de Engorde",
    "version": "1.0.0",
    "category": "Operations/Agriculture",
    "summary": "Control de lotes, registros diarios y costos por compras en granja de pollos de engorde",
    "depends": ["base", "mail", "purchase", "stock", "mrp", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/picking_type_salida_broiler.xml",
        "data/reprocess_stock_moves.xml",
        "report/report_salida_broiler.xml",
        "report/report_broiler_flock.xml",

        # IMPORTANTE: primero vistas/actions, al final el menú
        "views/broiler_flock_views.xml",
        "views/broiler_daily_log_views.xml",
        "views/purchase_order_views.xml",
        "views/broiler_flock_cost_wizard_views.xml",
        "views/broiler_feed_consumption_views.xml",
        "views/broiler_farm_dashboard_views.xml",
        "views/broiler_menu.xml",
    ],
    "application": True,
    "license": "LGPL-3",
    "web_icon": "broiler_farm,static/description/icon.png",
}
