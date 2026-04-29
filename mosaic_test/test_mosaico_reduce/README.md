# test_mosaico_reduce

Carpeta separada para abordar la discontinuidad entre sensores en la serie temporal.

## Objetivo principal
- Diagnosticar discontinuidades asociadas al cambio L5/L7 -> L8/L9 en todas las bandas relevantes (no solo indices).
- Verificar congruencia de nomenclatura de bandas respecto a su rango espectral esperado.
- Ejecutar pruebas reproducibles sin tocar el flujo operativo base.
- Preparar evidencia y scripts listos para subir a GitHub.

## Estructura
- `test_profile.json`: perfil de corrida del pipeline de prueba.
- `run_test_flow.py`: ejecuta validacion espacial + mosaico de prueba.
- `diagnosis_profile.json`: perfil para diagnostico de discontinuidad.
- `run_discontinuity_diagnosis.py`: ejecuta reporte numerico + grafico NDWI.
- `run_band_naming_audit.py`: auditoria de congruencia nombre de banda <-> rango espectral.

## Flujo recomendado
1. Correr un test de mosaico controlado:
   ```bash
   python run_test_flow.py
   ```
2. Correr diagnostico de discontinuidad:
   ```bash
   python run_discontinuity_diagnosis.py
   ```
3. Auditar nomenclatura espectral:
   ```bash
   python run_band_naming_audit.py
   ```

## Nota
Los runners de esta carpeta reutilizan scripts de `../mosaico_reduce` para evitar duplicar logica.

## Reporte de cambios aplicados (2026-04-28)

Se aplico una validacion explicita en `../mosaico_reduce/mapbiomas_Chile_mosaics_landsat_v1.py` para controlar combinaciones ano/sensor no estandar (incluyendo casos conflictivos posteriores a 2017).

- Nuevo switch de entorno: `MOSAIC_STRICT_SENSOR_YEAR_GUARD` (default: `1`).
- Con el guard estricto activo, filas del JSON con combinacion invalida `year + satellite` se **saltan** antes de exportar.
- Con `MOSAIC_STRICT_SENSOR_YEAR_GUARD=0`, el script solo emite warning y continua (modo compatible/diagnostico).

### Regla implementada por ano
- `<= 1998`: permitido `l4`, `l5` (+ `l7` desde 1984 por ventana solicitada)
- `1999-2012`: permitido `l5`, `l7`
- `2013-2016`: permitido `l8`, `l7`
- `2017-2020`: permitido `l8`
- `>= 2021`: permitido `l8`, `l9`

Ventana explicita solicitada para `l7`: `1984-01-01` a `2017-01-01` (inclusive/exclusive).

### Motivo tecnico
- Evita generar mosaicos con sensores que no corresponden al periodo nominal.
- Reduce la probabilidad de discontinuidades artificiales por mezcla de sensores en anos sensibles.
- Refuerza control de calidad antes del `Export.image.toAsset`.

## Reporte adicional: salida y bandas (2026-04-28)

Se ajusto la salida de exportacion y el contenido del mosaico final para facilitar validacion en GEE.

- Cambio de coleccion de salida:
  - de `projects/mapbiomas-chile/assets/MOSAICS/test_landcover`
  - a `projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2`
- Nuevo switch: `MOSAIC_CORE_BANDS_ONLY_EXPORT` (default: `1`).
- Con el switch activo, el export final conserva **solo** estas bandas:
  - `blue_median`, `green_median`, `red_median`, `nir_median`, `swir1_median`, `swir2_median`, `ndvi_median`, `ndwi_median`
- Si se requiere comportamiento historico, usar `MOSAIC_CORE_BANDS_ONLY_EXPORT=0`.

### Resultado esperado
- Las nuevas tareas se publican en `test_landcover_2`.
- El asset exportado queda limpio de bandas extra (SMA, topografia, estadisticos adicionales e indices fuera de NDVI/NDWI).

## Modo seguro para cuenta compartida (2026-04-28)

Para evitar mezclar tareas de distintos usuarios/corridas, el script ahora exige tag explicito por defecto.

- Nuevo switch: `MOSAIC_REQUIRE_EXPORT_TAG` (default: `1`).
- Si `MOSAIC_REQUIRE_EXPORT_TAG=1` y no defines `MOSAIC_EXPORT_TAG`, el script corta con error antes de exportar.
- Recomendacion: usar tags unicos por corrida, por ejemplo `pedro-20260428-a`.

### Ejemplo PowerShell
```powershell
$env:MOSAIC_EXPORT_TAG='pedro-20260428-a'
$env:MOSAIC_REQUIRE_EXPORT_TAG='1'
$env:MOSAIC_CORE_BANDS_ONLY_EXPORT='1'
$env:MOSAIC_REDUCED_MODE='1'
python .\mosaico_reduce\mapbiomas_Chile_mosaics_landsat_v1.py
```
