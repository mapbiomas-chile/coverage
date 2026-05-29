# mosaico_reduce

Landsat mosaic pipeline for Chile (CIM 1:250k grid) with sensor guards, safe exports in a shared Earth Engine account, and NDWI discontinuity tracking.

## Key files

| File | Role |
|------|------|
| `mapbiomas_Chile_mosaics_landsat_v1.py` | Main mosaic generation and export script |
| `input_params_2026_SJ-18-X-B.json` | Row-level parameters (grid, year, satellite, dates, filters) |
| `run_pipeline.py` | GPKG overlap check → mosaic script (modular entry point) |
| `check_gpkg_tile_overlap.py` | Standalone GPKG vs CIM tile intersection test |
| `ndwi_incongruence_report.py` | NDWI sensor-shift diagnostic on exported assets |
| `plot_ndwi_gpkg.py` | NDWI time-series plot for the sample GPKG area |
| `plot_all_bands_gpkg.py` | Multi-band median time-series plot |
| `format_params_tsv.py` / `params.tsv` | TSV parameter formatting utilities |
| `ndwi_sensor_shift_report.md` | Written findings from the SJ-18-X-B NDWI analysis |

## Workflow in this iteration

1. Scope test runs to tile `SJ-18-X-B` via `input_params_2026_SJ-18-X-B.json`.
2. Run NDWI diagnostics with `ndwi_incongruence_report.py` to detect inter-sensor breaks.
3. Adjust `mapbiomas_Chile_mosaics_landsat_v1.py` for sensor/year guards, isolated test exports, core-band output, and mandatory export tags.

## Changes in `mapbiomas_Chile_mosaics_landsat_v1.py`

### 1) Sensor/year quality guard

`valid_sensors_for_year(year)` enforces allowed Landsat sensors per year:

| Year range | Primary sensors | Notes |
|------------|-----------------|-------|
| ≤ 1998 | `l4`, `l5` | `l7` also allowed from 1984 |
| 1999–2012 | `l5` | `l7` also allowed from 1984 |
| 2013–2020 | `l8` | `l7` also allowed until 2016 |
| ≥ 2021 | `l8`, `l9` | |

`l7` window: **1984-01-01 → 2017-01-01** (year `< 2017`).

- `MOSAIC_STRICT_SENSOR_YEAR_GUARD=1` (default): invalid `year + satellite` rows are skipped.
- `MOSAIC_STRICT_SENSOR_YEAR_GUARD=0`: warning only.

### 2) Isolated test output

Exports target:

- `projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2`

Export suffix: `-REDUCED-NDVI-NDWI-v2` (plus optional `MOSAIC_EXPORT_TAG`).

### 3) Core-band export

With `MOSAIC_CORE_BANDS_ONLY_EXPORT=1` (default), the final mosaic keeps only:

- `blue_median`, `green_median`, `red_median`, `nir_median`, `swir1_median`, `swir2_median`, `ndvi_median`, `ndwi_median`

Extra bands (SMA, terrain, additional statistics) are dropped.

### 4) NDWI definition

- **Before:** NDWI as normalized difference of swir and nir.
- **Now:** NDWI as normalized difference of **green** and **nir**, aligned with the current project analysis criteria.

### 5) Mandatory export tag (shared account)

- `MOSAIC_REQUIRE_EXPORT_TAG=1` (default): requires `MOSAIC_EXPORT_TAG`; script exits early if missing.
- Prevents task/asset collisions when multiple users share the same Earth Engine project.

### 6) Runtime switches

| Variable | Default | Purpose |
|----------|---------|---------|
| `MOSAIC_REDUCED_MODE` | `1` | Reduced optical + NDVI/NDWI pipeline |
| `MOSAIC_STRICT_SENSOR_YEAR_GUARD` | `1` | Skip invalid year/sensor rows |
| `MOSAIC_CORE_BANDS_ONLY_EXPORT` | `1` | Export core bands only |
| `MOSAIC_REQUIRE_EXPORT_TAG` | `1` | Require explicit export tag |
| `MOSAIC_EXPORT_TAG` | — | Unique suffix appended to asset names |
| `MOSAIC_MAX_JOBS` | — | Limit rows per territory (smoke tests) |
| `MOSAIC_SKIP_ACTIVE_TASK_GUARD` | `0` | Skip slow `ee.batch.Task.list()` at startup |

## `input_params_2026_SJ-18-X-B.json`

Each JSON row defines one export job:

- `country`, `grid_name`, `year`, `satellite`
- Time window (`t0_s`, `t1_s`)
- `cloud_cover`, `black_list`, `use_tile_mask`

Used for controlled tile/year/sensor tests and guard validation.

## `ndwi_incongruence_report.py`

Diagnostic script that:

- Queries the mosaic collection
- Filters by `grid_name=SJ-18-X-B`
- Reads `ndwi_median`
- Compares pre-2013 vs post-2012 periods statistically

Goal: detect whether sensor changes produce a structural NDWI shift.

## Recommended execution (PowerShell)

From `mosaic_test/mosaico_reduce`:

**Direct script:**

```powershell
$env:MOSAIC_EXPORT_TAG='pedro-YYYYMMDD-a'
$env:MOSAIC_REQUIRE_EXPORT_TAG='1'
$env:MOSAIC_STRICT_SENSOR_YEAR_GUARD='1'
$env:MOSAIC_CORE_BANDS_ONLY_EXPORT='1'
$env:MOSAIC_REDUCED_MODE='1'
$env:MOSAIC_MAX_JOBS='1'   # optional smoke test
python .\mapbiomas_Chile_mosaics_landsat_v1.py
```

**With GPKG overlap validation:**

```powershell
python .\run_pipeline.py --tile SJ-18-X-B --export-tag pedro-YYYYMMDD-a --max-jobs 1
```

**Overlap check only:**

```powershell
python .\check_gpkg_tile_overlap.py --gpkg ..\..\inputs\gpk\Muestra_Lagogpk.gpkg --tile SJ-18-X-B
```
