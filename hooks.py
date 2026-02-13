import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

def _fix_sequence_on_install(env, *args):
    """Ajusta la secuencia SB al último número usado en stock_picking"""
    try:
        cr = env.cr
        if args:
            cr = args[0]
        # Buscar el picking type SB
        cr.execute("SELECT id, sequence_id FROM stock_picking_type WHERE sequence_code = 'SB'")
        result = cr.fetchone()
        if not result:
            _logger.info('No se encontró picking type con secuencia SB')
            return
        
        picking_type_id, sequence_id = result
        
        # Calcular el siguiente número basado en los pickings existentes
        cr.execute("""
            SELECT COALESCE(MAX(CAST(SUBSTRING(name FROM 4 FOR 5) AS INTEGER)), 0) + 1
            FROM stock_picking 
            WHERE name LIKE 'SB_%'
        """)
        next_num = cr.fetchone()[0]
        
        # Actualizar la secuencia
        cr.execute("""
            UPDATE ir_sequence 
            SET number_next = %s 
            WHERE id = %s
        """, (next_num, sequence_id))
        
        _logger.info('Secuencia SB ajustada a %s', next_num)
        
    except Exception as e:
        _logger.warning('Error ajustando secuencia: %s', e)

def _clean_data(env):
    """Limpia todos los datos de broiler_farm"""
    _logger.info('=== LIMPIANDO DATOS BROILER FARM ===')
    try:
        # 1. Obtener picking type SB primero
        env.cr.execute("SELECT id FROM stock_picking_type WHERE sequence_code = 'SB'")
        sb_type_ids = [r[0] for r in env.cr.fetchall()]
        
        # 2. Eliminar pickings de Salida Broiler (todos)
        if sb_type_ids:
            env.cr.execute("""
                DELETE FROM stock_picking 
                WHERE picking_type_id IN %s
            """, (tuple(sb_type_ids),))
            _logger.info('Pickings eliminados')
        
        # 3. Eliminar stock moves relacionados con broiler_daily_log
        env.cr.execute("""
            DELETE FROM stock_move 
            WHERE broiler_daily_log_id IN (
                SELECT id FROM broiler_daily_log
            )
        """)
        _logger.info('Stock moves eliminados')
        
        # 4. Eliminar registros diarios
        env.cr.execute("DELETE FROM broiler_daily_log")
        _logger.info('Registros diarios eliminados')
        
        # 5. Eliminar lotes
        env.cr.execute("DELETE FROM broiler_flock")
        _logger.info('Lotes eliminados')
        
        # 6. Eliminar ubicaciones de broiler
        env.cr.execute("""
            DELETE FROM stock_location 
            WHERE name IN ('Broiler', 'Consumo Broiler')
            AND location_id IN (
                SELECT id FROM stock_location WHERE name = 'Stock'
            )
        """)
        _logger.info('Ubicaciones eliminadas')
        
        # 7. Eliminar picking type Salida Broiler (ahora sin referencias)
        if sb_type_ids:
            env.cr.execute("""
                DELETE FROM stock_picking_type 
                WHERE id IN %s
            """, (tuple(sb_type_ids),))
            _logger.info('Picking type eliminado')
        
        # 8. Eliminar secuencias
        env.cr.execute("""
            DELETE FROM ir_sequence 
            WHERE code IN ('broiler.daily.log', 'broiler_farm.salida_broiler')
        """)
        _logger.info('Secuencias eliminadas')
        
        # 9. Limpiar duplicados en stock_picking (por si hay registros huérfanos)
        env.cr.execute("""
            DELETE FROM stock_picking
            WHERE id IN (
                SELECT id FROM (
                    SELECT id, ROW_NUMBER() OVER (PARTITION BY name, company_id ORDER BY id) as rn
                    FROM stock_picking
                    WHERE name LIKE 'SB_%'
                ) t WHERE rn > 1
            )
        """)
        
        # 10. Resetear secuencia de SB al siguiente número disponible
        env.cr.execute("""
            SELECT COALESCE(MAX(CAST(SUBSTRING(name FROM 4 FOR 5) AS INTEGER)), 0) + 1
            FROM stock_picking 
            WHERE name LIKE 'SB_%'
        """)
        next_num = env.cr.fetchone()[0]
        env.cr.execute("""
            UPDATE ir_sequence 
            SET number_next = %s 
            WHERE code = 'stock.picking.type.salida.broiler'
            OR name LIKE '%%Salida Broiler%%'
        """, (next_num,))
        _logger.info(f'Secuencia reseteada a {next_num}')
        
    except Exception as e:
        _logger.error(f'Error limpiando datos: {e}')
        raise

def uninstall_hook(cr, registry):
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        _clean_data(env)
        _logger.info('=== UNINSTALL HOOK COMPLETADO ===')
    except Exception as e:
        _logger.error(f'Error en uninstall_hook: {e}')
        import traceback
        _logger.error(traceback.format_exc())
