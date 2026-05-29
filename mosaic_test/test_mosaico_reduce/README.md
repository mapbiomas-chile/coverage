# test_mosaico_reduce

Isolated test harness for sensor discontinuities in the Landsat mosaic time series.

## Goals

- Diagnose discontinuities from the `L5/L7 → L8/L9` sensor transition across relevant bands (not just indices).
- Verify band naming against expected spectral ranges.
- Run reproducible tests without modifying the base operational workflow.
- Provide evidence and scripts suitable for version control.

## Structure

| File | Role |
|------|------|
| `test_profile.json` | Run profile for the controlled mosaic test |
| `run_test_flow.py` | Spatial validation + test mosaic via `../mosaico_reduce/run_pipeline.py` |
| `diagnosis_profile.json` | Profile for discontinuity diagnosis |
| `run_discontinuity_diagnosis.py` | Numeric report + NDWI time-series plot |
| `run_band_naming_audit.py` | Band name ↔ spectral range audit |
| `random_gpkg_sensor_diagnosis.py` | Random-sample sensor diagnosis helper |
| `sensor_discontinuity_random_samples.csv` | Sample output from random diagnosis runs |

Runners in this folder call scripts under `../mosaico_reduce` to avoid duplicating logic.

## Recommended flow

From `mosaic_test/`:

```powershell
python .\test_mosaico_reduce\run_test_flow.py
python .\test_mosaico_reduce\run_discontinuity_diagnosis.py
python .\test_mosaico_reduce\run_band_naming_audit.py
```

### 1) Controlled mosaic test

`run_test_flow.py` reads `test_profile.json` and invokes `mosaico_reduce/run_pipeline.py` with:

- `--gpkg`, `--tile`, `--project`, `--reduced`
- `--export-tag` (required for shared-account safety)
- `--max-jobs` (optional smoke-test limit)
- `--skip-task-guard` (when `skip_task_guard: true` in the profile)

Default profile targets tile `SJ-18-X-B` with `max_jobs: 1`.

### 2) Discontinuity diagnosis

`run_discontinuity_diagnosis.py` uses `diagnosis_profile.json` to produce numeric summaries and writes the NDWI plot to `../outputs/ndwi_muestra_lago_timeseries.png` by default.

### 3) Band naming audit

`run_band_naming_audit.py` checks that exported band names match expected Landsat spectral assignments.

## Pipeline changes validated by this harness

### Sensor/year guard (`MOSAIC_STRICT_SENSOR_YEAR_GUARD`)

Added in `../mosaico_reduce/mapbiomas_Chile_mosaics_landsat_v1.py`:

- Default: `1` — invalid `year + satellite` rows are **skipped** before export.
- Set to `0` for warning-only mode (diagnostic runs).

| Year range | Primary sensors | Notes |
|------------|-----------------|-------|
| ≤ 1998 | `l4`, `l5` | `l7` also allowed from 1984 |
| 1999–2012 | `l5` | `l7` also allowed from 1984 |
| 2013–2020 | `l8` | `l7` also allowed until 2016 |
| ≥ 2021 | `l8`, `l9` | |

`l7` window: **1984-01-01 → 2017-01-01**.

**Why:** prevents exports with sensors that do not match the nominal period and reduces artificial discontinuities from mixed-sensor years.

### Test export collection and core bands

- Output collection: `projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2`
- `MOSAIC_CORE_BANDS_ONLY_EXPORT=1` (default) keeps only:
  - `blue_median`, `green_median`, `red_median`, `nir_median`, `swir1_median`, `swir2_median`, `ndvi_median`, `ndwi_median`
- Set `MOSAIC_CORE_BANDS_ONLY_EXPORT=0` to restore legacy extra bands/statistics.

### Shared-account safety

- `MOSAIC_REQUIRE_EXPORT_TAG=1` (default): script exits if `MOSAIC_EXPORT_TAG` is not set.
- Use unique tags per run (e.g. `pedro-20260428-a`).

### Example (manual run)

```powershell
cd mosaic_test\mosaico_reduce
$env:MOSAIC_EXPORT_TAG='pedro-20260428-a'
$env:MOSAIC_REQUIRE_EXPORT_TAG='1'
$env:MOSAIC_CORE_BANDS_ONLY_EXPORT='1'
$env:MOSAIC_REDUCED_MODE='1'
python .\mapbiomas_Chile_mosaics_landsat_v1.py
```

Or use the test harness profile instead:

```powershell
cd mosaic_test
python .\test_mosaico_reduce\run_test_flow.py
```
