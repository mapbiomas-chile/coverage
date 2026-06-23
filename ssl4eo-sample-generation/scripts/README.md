# Scripts — SSL4EO sample generation (scale300)

Run all commands from the repository root (`ssl4eo-sample-generation/`).

On cluster, set data output root first:

```bash
export GRILLAS_ROOT=/home/lserey/mapbiomas_land/prod/samples
export MAPBIOMAS_LAND_ROOT=/home/lserey/mapbiomas_land
source cluster/activate_mb_labels.sh
```

## Pipeline numerado (01–08)

| Paso | Script | Función | Salida principal |
|------|--------|---------|------------------|
| **01** | `01_local_grid_characterization.py` | Caracterización de grillas candidatas (rasterio) | `intermediate_files/grid_characterization/*.zip` |
| **02** | `02_rectangle_selection.py` | Selección balanceada; **4 corridas** (UTM18/19 × 2×2/3×3); anti-solape global | `final_samples/UTM{18\|19}/{homogeneo_2x2\|mixto_3x3}/seleccion_*.{geojson,gpkg,csv}` |
| **03** | `03_annotate_grid_taxonomy.py` | Taxonomía N1/N2/N3 | `*_taxonomia_n3.csv` |
| **04** | `04_rectangle_selection_review.py` | Tablas y reporte de revisión | `intermediate_files/review/01_*` … `09_*`, `REVISION_COMPLETA*.txt` |
| **05** | `05_balance_audit.py` | Auditoría de balanceo (14 criterios) | `AUDITORIA_BALANCEO.txt` |
| **06** | `06_visualize_reports.py` | Dashboard Streamlit / export HTML | `revision_dashboard.html` |
| **07** | `07_generate_rectangle_review_plan.py` | Plan de revisión temporal por rectángulo | `plan_revision_UTM{18\|19}_{homogeneo_2x2\|mixto_3x3}_scale300.csv` |
| **08** | `08_consolidate_national_review_plan.py` | Plan nacional consolidado | `plan_revision_nacional_scale300.csv`, etc. |

> Los prefijos `08_clases_criticas_*` en `intermediate_files/review/` son **nombres de archivos CSV** generados por el paso **04**, no un script aparte.

### Orden de ejecución (cluster)

`cluster/run_pipeline_02_08.sh`:

1. **01** (opcional) — 4 ZIPs de caracterización  
2. **02** × 4 — selección por huso y tamaño  
3. **03** + **07** por cada selección  
4. **04** → **05** → **08** → **06**

## Módulos auxiliares (sin número)

| Módulo | Uso |
|--------|-----|
| `local_grid_characterization.py` | Lógica raster/MGRS del paso 01 |
| `cluster_config.py` | Rutas de insumos en cluster |
| `project_paths.py` | `GRILLAS_ROOT`, helpers de rutas |
| `selection_balancing.py` | Balanceo ecorregional, split, cupos |
| `ecoregion_names.py` | Etiquetas E1–E15 (continental) |
| `critical_classes.py` | Clases críticas / raras |
| `taxonomy_classes.py` | Lookup taxonomía MapBiomas C2 N3 |

## Paso 01 — Caracterización

```bash
python scripts/01_local_grid_characterization.py --run-scale300-all
```

## Paso 02 — Selección (4 corridas)

```bash
python scripts/02_rectangle_selection.py \
  --homogeneo intermediate_files/grid_characterization/grilla_ssl4eo_muestras_homogeneo_2x2_UTM18_scale300_n3.zip

python scripts/02_rectangle_selection.py \
  --mixto intermediate_files/grid_characterization/grilla_ssl4eo_muestras_mixto_3x3_UTM18_scale300_n3.zip
```

Repetir para UTM19, o ejecutar `bash cluster/run_pipeline_02_08.sh`.

## Pasos 03–08 — Comandos rápidos

```bash
python scripts/03_annotate_grid_taxonomy.py \
  -i final_samples/UTM18/homogeneo_2x2/seleccion_grilla_ssl4eo_muestras_homogeneo_2x2_UTM18_scale300.csv

python scripts/04_rectangle_selection_review.py --utm 18 19
python scripts/05_balance_audit.py

python scripts/07_generate_rectangle_review_plan.py \
  -i final_samples/UTM18/homogeneo_2x2/seleccion_grilla_ssl4eo_muestras_homogeneo_2x2_UTM18_scale300.geojson \
  -o intermediate_files/review/plan_revision_UTM18_homogeneo_2x2_scale300.csv

python scripts/08_consolidate_national_review_plan.py --out-dir intermediate_files/review

streamlit run scripts/06_visualize_reports.py
python scripts/06_visualize_reports.py \
  --export-html intermediate_files/review/revision_dashboard.html
```

Ver también: [../README.md](../README.md), [../cluster/README.md](../cluster/README.md).
