# Reporte: posible incongruencia NDWI por cambio de sensor

## Contexto
- Area de analisis: `inputs/gpk/Muestra_Lagogpk.gpkg`
- Tile: `SJ-18-X-B`
- Coleccion consultada: `projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2`
- Variable analizada: `ndwi_median` (re-escalada a valor real con `/10000`)

## Hallazgo principal
Se observa un quiebre en la serie anual de NDWI desde 2013, coincidente con el cambio de sensor (L5/L7 -> L8 y luego L9).

- Periodo 1998-2012 (L5/L7): media = **1.5936** (n=15)
- Periodo 2013-2025 (L8/L9): media = **1.1781** (n=14)
- Cambio medio relativo: **-26.1%**
- Salto puntual 2012 -> 2013: **-33.0%** (de 1.6290 a 1.0907)

## Evidencia resumida
- Pre-2013:
  - rango: 1.4726 a 1.7544
  - mediana: 1.6008
- Post-2012:
  - rango: 0.9581 a 1.3191
  - mediana: 1.1593

Adicionalmente se detecto un duplicado historico para 2017 (`PROD` y `PRUEBA`) en la misma coleccion, que puede introducir ruido si no se filtra por sufijo/version.

## Interpretacion tecnica (hipotesis)
La caida estructural es consistente con un sesgo inter-sensor, mas que con un cambio fisico abrupto del cuerpo de agua:

1. Diferencias de respuesta espectral entre sensores (TM/ETM+ vs OLI/OLI-2).
2. Cambios de composicion anual (mosaico) entre periodos con distinta disponibilidad/calidad.
3. Mezcla de productos/sufijos en la coleccion historica (`PROD`, `PRUEBA`, `REDUCED`).

## Recomendaciones
1. Analizar por periodos (pre-2013 y post-2012) mientras no haya armonizacion.
2. Filtrar estrictamente por sufijo de corrida al generar series temporales.
3. Implementar armonizacion por sensor (offset o regresion) usando anos de traslape/puntos estables.
4. Evitar mezclar outputs de prueba y produccion en la misma consulta.

## Fuente de datos para este reporte
Calculado con el script:
- `mosaico_reduce/ndwi_incongruence_report.py`

y complementado con:
- `mosaico_reduce/plot_ndwi_gpkg.py`
- `outputs/ndwi_muestra_lago_timeseries.png`
