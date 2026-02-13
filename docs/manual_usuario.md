# Manual de Usuario - Módulo Broiler Farm

## Descripción General

El módulo **Broiler Farm** es un sistema de gestión integral para granjas de pollos de engorde (broilers). Permite controlar lotes, registrar consumos diarios, calcular costos operativos y generar reportes.

---

## Estructura del Menú

El módulo se accede desde el menú principal:

```
Granja Pollos
├── Dashboard        - Vista general de la granja
├── Lotes           - Gestión de lotes de pollos
└── Registros diarios - Registro de consumo diario
```

---

## 1. Lotes

### Crear un Nuevo Lote

1. Acceda a **Granja Pollos > Lotes**
2. Haga clic en **Crear**
3. Complete los campos obligatorios:
   - **Fecha y Hora de Ingreso**: Fecha de recepción del lote
   - **Cantidad Inicial**: Número de pollos recibidos
   - **Producto Alimento Inicio**: Producto de alimento para fase inicial
   - **Producto Alimento Final**: Producto de alimento para fase final
4. Complete campos opcionales:
   - **Granja**: Nombre de la granja
   - **Galpón**: Número o nombre del galpón
   - **Proveedor**: Nombre del proveedor
   - **Línea/Genética**: Tipo de raza
5. Guarde el lote

### Estados del Lote

- **Borrador**: Lote creado sin iniciar
- **Activo**: Lote en producción
- **Cerrado**: Lote terminado

### Acciones del Lote

- **Activar**: Cambia el estado a "Activo"
- **Cerrar**: Finaliza el lote
- **Actualizar Costos Manuales**: Wizard para agregar costos adicionales

### KPIs del Lote

El sistema calcula automáticamente:

| Campo | Descripción |
|-------|-------------|
| Edad (días) | Días transcurridos desde el ingreso |
| Mortalidad acumulada | Total de pollos muertos |
| Descartes acumulados | Total de pollos descartados |
| Aves vivas | Cantidad actual de pollos |
| % Bajas | Porcentaje de mortalidad + Descartes |
| Alimento acumulado (kg) | Total de alimento consumido |
| Agua acumulada (L) | Total de agua consumida |
| Peso promedio (g) | Último peso registrado |
| FCR (estimado) | Conversión alimenticia |
| Costo Alimento | Costo acumulado de alimento |
| Costo Operativo | Total de costos del lote |

---

## 2. Registros Diarios

### Crear un Registro Diario

1. Acceda a **Granja Pollos > Registros diarios**
2. Haga clic en **Crear**
3. Seleccione el **Lote**
4. Complete los datos del día:
   - **Fecha**: Fecha del registro
   - **Alimento Inicio (kg)**: Cantidad de alimento inicio consumida
   - **Alimento Final (kg)**: Cantidad de alimento final consumida
   - **Agua (L)**: Consumo de agua
   - **Mortalidad (unid)**: Pollos muertos ese día
   - **Descartes (unid)**: Pollos descartados
   - **Peso prom. muestreo (g)**: Peso promedio de la muestra
   - **Muestra (aves)**: Cantidad de aves pesadas
5. Guarde el registro

### Validaciones

- No permite valores negativos
- Si ingresa peso, debe indicar el tamaño de muestra
- No puede modificar registros de lotes cerrados

### Consumo de Alimento

Al guardar el registro, el sistema automáticamente:

1. Crea un **picking de salida** (tipo Salida Broiler)
2. Genera movimientos de stock para rebajar el inventario
3. Calcula el costo del alimento según el precio del producto

---

## 3. Dashboard

El dashboard muestra una vista consolidada de la granja con:

### KPIs Principales

- **Total Lotes**: Cantidad total de lotes
- **Activos**: Lotes en producción
- **Aves Vivas**: Total de pollos vivos
- **Pickings Pend.**: Transfers de alimento por confirmar
- **Costo Total**: Gasto operativo total
- **Peso Prom.**: Peso promedio de todos los lotes

### Gráficos

- **Estado de Lotes**: Distribución por estado (pie)
- **Pickings por Estado**: Estado de las transferencias (bar)
- **Peso Promedio por Lote**: Evolución de pesos (línea)

### Actualización

El dashboard se actualiza automáticamente cada minuto.

---

## 4. Costos del Lote

### Agregar Costos Manuales

1. Desde un lote, haga clic en **Actualizar Costos Manuales**
2. Complete:
   - **Descripción del Costo**: Concepto
   - **Monto del Costo**: Valor en dinero
   - **Tipo de Costo**: Medicina, Vacuna, Mano de Obra, etc.
3. Confirme

### Cálculo Automático de Costos

El sistema calcula automáticamente:

- **Costo Alimento**: Según movimientos de stock validados (precio del producto × cantidad)
- **Costo Operativo**: Suma de alimento + otros costos manuales

---

## 5. Picking Type "Salida Broiler"

El módulo crea automáticamente:

- **Ubicación**: "Consumo Broiler" (virtual)
- **Tipo de Operación**: "Salida Broiler" (código SB)
- **Secuencia**: Nombres aleatorios tipo SB_XXXXXXXX

### Funcionamiento

Cada registro diario genera un picking de salida de alimento:

1. **Origen**: Stock principal
2. **Destino**: Ubicación de consumo del lote
3. **Estado**: Asignado automáticamente

---

## 6. Configuración

### Productos de Alimento

Debe crear productos de tipo **Consumible** para usar en los lotes:

1. Vaya a **Inventario > Productos**
2. Cree productos con:
   - **Tipo**: Consumible
   - **Costo**: Precio por kg (usado para cálculos)

### Permisos

El módulo incluye control de acceso para usuarios:

- Acceso a lote, registros diarios, dashboard
- Permisos de lectura/escritura según configuración

---

## 7. Reportes

El módulo incluye reportes para:

- **Salida Broiler**: Detalle de transferencias de alimento
- **Lote**: Resumen de métricas del lote

---

## Troubleshooting

### Error de secuencia duplicada

Si ve error `stock_picking_name_uniq`, el sistema regenerará automáticamente un código único.

###pickings no se crean

Verifique que:
1. El tipo de operación "Salida Broiler" exista
2. Los productos de alimento tengan costo definido

### No aparecen productos en el registro diario

Los productos deben ser de tipo "Consumible" y estar activos.

---

## Glosario

| Término | Descripción |
|---------|-------------|
| Lote | Grupo de pollos ingresados en una fecha |
| Registro Diario | Datos de consumo de un día específico |
| FCR | Feed Conversion Rate (conversión alimenticia) |
| Mortalidad | Pollos muertos durante el ciclo |
| Descartes | Pollos eliminados por enfermedad/defecto |
| Picking | Transferencia de inventario |
| KPI | Indicador clave de rendimiento |
