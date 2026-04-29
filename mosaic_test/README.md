# mosaico_test

Repositorio de trabajo para pruebas y ajuste del pipeline de mosaicos Landsat (Chile), con foco en control de sensores, exportaciones seguras en cuenta compartida y validacion de discontinuidades NDWI.

## Estructura actual

- `mosaico_reduce/`: pipeline principal y utilidades de analisis/graficos.
- `test_mosaico_reduce/`: perfiles y runners de prueba/diagnostico.
- `inputs/`: insumos locales.
- `outputs/`: salidas generadas (graficos, reportes exportados, artefactos de diagnostico).

> Nota: este repo fue aplanado para evitar git anidado. Antes el trabajo estaba dentro de `coverage-main/`.

## Salidas generadas

Para evitar confusiones al versionar y subir a GitHub, todas las salidas generadas deben quedar en:

- `C:\Users\pedro\Documents\mosaico_test\outputs`

Los scripts de diagnostico y graficado del repo ya vienen configurados para escribir por defecto en esa carpeta.

## Bloque de pruebas (`test_mosaico_reduce`)

### Objetivo principal

- Diagnosticar discontinuidades por cambio de sensor (`L5/L7 -> L8/L9`) en bandas e indices.
- Verificar congruencia entre nombre de banda y rango espectral esperado.
- Ejecutar pruebas reproducibles sin alterar el flujo productivo.

### Archivos clave

- `test_mosaico_reduce/test_profile.json`: perfil de corrida para prueba de mosaico.
- `test_mosaico_reduce/run_test_flow.py`: validacion espacial y mosaico de prueba.
- `test_mosaico_reduce/diagnosis_profile.json`: perfil para diagnostico de discontinuidad.
- `test_mosaico_reduce/run_discontinuity_diagnosis.py`: reporte numerico y grafico NDWI.
- `test_mosaico_reduce/run_band_naming_audit.py`: auditoria de nomenclatura espectral.

### Flujo recomendado de diagnostico

Desde la raiz del repo:

```powershell
python .\test_mosaico_reduce\run_test_flow.py
python .\test_mosaico_reduce\run_discontinuity_diagnosis.py
python .\test_mosaico_reduce\run_band_naming_audit.py
```

## Cambios principales aplicados

### 1) Control ano/satelite
En `mosaico_reduce/mapbiomas_Chile_mosaics_landsat_v1.py` se agrego validacion de combinaciones `year + satellite`:

- `l7` permitido en ventana solicitada: `1984-01-01` a `2017-01-01` (ano `< 2017`).
- Si una fila no cumple regla, se bloquea (o advierte segun configuracion).

Variable asociada:
- `MOSAIC_STRICT_SENSOR_YEAR_GUARD` (default `1`).

### 2) Salida de exportacion para pruebas
La coleccion de salida fue cambiada a:
- `projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2`

### 3) Export solo con bandas nucleares
Se forzo export final con bandas:
- `blue_median`, `green_median`, `red_median`, `nir_median`, `swir1_median`, `swir2_median`, `ndvi_median`, `ndwi_median`

Variable asociada:
- `MOSAIC_CORE_BANDS_ONLY_EXPORT` (default `1`).

### 4) Modo seguro en cuenta compartida
Se agrego proteccion para impedir corridas sin tag:

- `MOSAIC_REQUIRE_EXPORT_TAG` (default `1`).
- Si falta `MOSAIC_EXPORT_TAG`, el script falla al inicio con error explicito.

Esto evita mezclar tareas de distintos usuarios en la misma cola de Earth Engine.

## Ejecucion recomendada (PowerShell)

Desde la raiz del repo:

```powershell
$env:MOSAIC_EXPORT_TAG='pedro-YYYYMMDD-a'
$env:MOSAIC_REQUIRE_EXPORT_TAG='1'
$env:MOSAIC_CORE_BANDS_ONLY_EXPORT='1'
$env:MOSAIC_REDUCED_MODE='1'
$env:MOSAIC_STRICT_SENSOR_YEAR_GUARD='1'
$env:MOSAIC_MAX_JOBS='1'   # smoke test opcional
python .\mosaico_reduce\mapbiomas_Chile_mosaics_landsat_v1.py
```

## Ver tareas en Earth Engine

- Web: https://code.earthengine.google.com/tasks
- CLI:

```powershell
earthengine --project mapbiomas-chile task list | Select-String "TMP-CHILE"
```

## Publicacion a GitHub

Objetivo: `https://github.com/mapbiomas-chile/coverage`

Si falla push por SSH (`Permission denied (publickey)`), configurar credenciales y reintentar:

```powershell
git push "git@github.com:mapbiomas-chile/coverage.git" main
```

Alternativa HTTPS:

```powershell
git push "https://github.com/mapbiomas-chile/coverage.git" main
```
