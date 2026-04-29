# mosaico_reduce

Pipeline de mosaicos Landsat para Chile con foco en control de sensores, exportacion segura en cuenta compartida y seguimiento de discontinuidades NDWI.

## Archivos clave del flujo

- `mapbiomas_Chile_mosaics_landsat_v1.py`: script principal de generacion/exportacion de mosaicos.
- `input_params_2026_SJ-18-X-B.json`: parametros por fila (grid, ano, satelite, fechas, filtros).
- `ndwi_incongruence_report.py`: diagnostico de quiebre NDWI por sensor en serie temporal.

## Flujo de trabajo aplicado en esta iteracion

1. Se acoto la corrida de prueba a `SJ-18-X-B` usando `input_params_2026_SJ-18-X-B.json`.
2. Se corrio diagnostico NDWI con `ndwi_incongruence_report.py` para detectar quiebre inter-sensor.
3. Se ajusto `mapbiomas_Chile_mosaics_landsat_v1.py` para:
   - controlar combinaciones ano/satelite,
   - exportar a una coleccion de prueba separada,
   - limitar bandas finales a opticas + NDVI/NDWI,
   - forzar tag de corrida en cuenta compartida.

## Cambios importantes en `mapbiomas_Chile_mosaics_landsat_v1.py`

### 1) Regla de sensores por ano (control de calidad)

Se incorporo `valid_sensors_for_year(year)` y un guard estricto:

- `MOSAIC_STRICT_SENSOR_YEAR_GUARD=1` (default): filas invalidas `year + satellite` se saltan.
- `MOSAIC_STRICT_SENSOR_YEAR_GUARD=0`: solo warning (modo flexible).

Regla vigente:
- `l7` permitido entre `1984-01-01` y `2017-01-01` (ano `< 2017`).
- `2017-2020`: solo `l8`.
- `>=2021`: `l8` y `l9`.

### 2) Salida de pruebas separada

La salida se dirige a:
- `projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2`

Esto evita mezclar resultados de prueba con otras colecciones historicas.

### 3) Export reducido a bandas nucleares (enfocado en NDWI)

Con `MOSAIC_CORE_BANDS_ONLY_EXPORT=1` (default), el mosaico final conserva solo:

- `blue_median`
- `green_median`
- `red_median`
- `nir_median`
- `swir1_median`
- `swir2_median`
- `ndvi_median`
- `ndwi_median`

Con esto se eliminan bandas extra (SMA, topografia e indices no requeridos para este test).

### 3.1) Cambio aplicado en la definicion de NDWI

Se deja explicitado el ajuste de indice usado en este flujo:

- Antes: NDWI calculado como normalizado de `swir` y `nir`.
- Ahora: NDWI calculado como normalizado de `green` y `nir`.

Este cambio se incorporo para mantener consistencia con el criterio de analisis actual del proyecto.

### 4) Tag obligatorio de corrida (cuenta compartida)

`MOSAIC_REQUIRE_EXPORT_TAG=1` (default) obliga definir `MOSAIC_EXPORT_TAG`.

Si falta el tag, el script falla al inicio para evitar colisiones/duplicados en la cola de Earth Engine.

## Rol de `input_params_2026_SJ-18-X-B.json`

Este JSON define la corrida fila a fila:
- `country`, `grid_name`, `year`, `satellite`
- ventana temporal (`t0_s`, `t1_s`)
- `cloud_cover`, `black_list`, `use_tile_mask`

Se usa para pruebas controladas por tile/ano/sensor y para validar reglas de consistencia.

## Rol de `ndwi_incongruence_report.py`

Script de diagnostico que:
- consulta la coleccion de mosaicos,
- filtra por `grid_name=SJ-18-X-B`,
- toma `ndwi_median`,
- compara estadisticamente periodos pre-2013 y post-2012.

Objetivo: evidenciar si el cambio de sensor produce salto estructural en NDWI.

## Ejecucion recomendada (PowerShell)

Desde la raiz del repo:

```powershell
$env:MOSAIC_EXPORT_TAG='pedro-YYYYMMDD-a'
$env:MOSAIC_REQUIRE_EXPORT_TAG='1'
$env:MOSAIC_STRICT_SENSOR_YEAR_GUARD='1'
$env:MOSAIC_CORE_BANDS_ONLY_EXPORT='1'
$env:MOSAIC_REDUCED_MODE='1'
$env:MOSAIC_MAX_JOBS='1'   # smoke test opcional
python .\mosaico_reduce\mapbiomas_Chile_mosaics_landsat_v1.py
```