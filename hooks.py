from odoo import api

def uninstall_hook(cr, registry):
    try:
        env = api.Environment(cr, registry['res.users'].sudo().search([('id', '=', 1)]).id, {})
        
        # Buscar todos los registros diarios
        daily_logs = env['broiler.daily.log'].search([])
        for log in daily_logs:
            # Eliminar movimientos de stock asociados
            for move in log.stock_move_ids:
                if move.picking_id:
                    move.picking_id.unlink()
                move.unlink()
        
        # Eliminar pickings generados por el picking type Salida Broiler
        picking_type = env.ref('broiler_farm.picking_type_salida_broiler', False)
        if picking_type:
            pickings = env['stock.picking'].search([
                ('picking_type_id', '=', picking_type.id)
            ])
            pickings.unlink()
    except Exception:
        pass
