# mosaic_test

Working area for testing and tuning the Landsat mosaic pipeline (Chile), focused on sensor controls, safe exports in a shared Earth Engine account, and NDWI discontinuity validation.

## Structure

| Folder | Purpose |
|--------|---------|
| `mosaico_reduce/` | Main CIM-grid pipeline and analysis/plotting utilities |
| `mosaico_reduce_mgrs/` | Same Landsat pipeline on MGRS tiles (2010–2016 sample) |
| `test_mosaico_reduce/` | Reproducible test/diagnostic profiles and runners |
| `inputs/` | Local inputs (e.g. sample GPKG under `inputs/gpk/`) |
| `outputs/` | Generated plots, reports, and diagnostic artifacts |

> This tree lives inside the `coverage` repository. It was flattened to avoid nested git repositories.

See each subfolder README for module-specific details:

- [mosaico_reduce/README.md](mosaico_reduce/README.md)
- [mosaico_reduce_mgrs/README.md](mosaico_reduce_mgrs/README.md)
- [test_mosaico_reduce/README.md](test_mosaico_reduce/README.md)

## Generated outputs

To keep the repository clean, write all generated artifacts under:

- `mosaic_test/outputs/`

Diagnostic and plotting scripts default to that relative path (e.g. `../outputs/` when run from a subfolder).

## Test block (`test_mosaico_reduce`)

### Goals

- Diagnose discontinuities caused by sensor changes (`L5/L7 → L8/L9`) in bands and indices.
- Verify consistency between band names and expected spectral ranges.
- Run reproducible tests without changing the production workflow.

### Key files

- `test_profile.json` — run profile for the controlled mosaic test.
- `run_test_flow.py` — spatial validation + test mosaic (wraps `mosaico_reduce/run_pipeline.py`).
- `diagnosis_profile.json` — profile for discontinuity diagnosis.
- `run_discontinuity_diagnosis.py` — numeric report and NDWI time-series plot.
- `run_band_naming_audit.py` — spectral naming audit.

### Recommended diagnostic flow

From `mosaic_test/`:

```powershell
python .\test_mosaico_reduce\run_test_flow.py
python .\test_mosaico_reduce\run_discontinuity_diagnosis.py
python .\test_mosaico_reduce\run_band_naming_audit.py
```

## Main pipeline changes

### 1) Year/satellite guard

In `mosaico_reduce/mapbiomas_Chile_mosaics_landsat_v1.py`, invalid `year + satellite` combinations are blocked before export:

| Year range | Primary sensors | Notes |
|------------|-----------------|-------|
| ≤ 1998 | `l4`, `l5` | `l7` also allowed from 1984 |
| 1999–2012 | `l5` | `l7` also allowed from 1984 |
| 2013–2020 | `l8` | `l7` also allowed until 2016 |
| ≥ 2021 | `l8`, `l9` | |

`l7` is allowed in the window **1984-01-01 → 2017-01-01** (year `< 2017`).

- `MOSAIC_STRICT_SENSOR_YEAR_GUARD=1` (default): invalid rows are **skipped**.
- `MOSAIC_STRICT_SENSOR_YEAR_GUARD=0`: warning only (diagnostic mode).

### 2) Test export collection

Exports go to:

- `projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2`

### 3) Core-band export

With `MOSAIC_CORE_BANDS_ONLY_EXPORT=1` (default), only these bands are kept:

- `blue_median`, `green_median`, `red_median`, `nir_median`, `swir1_median`, `swir2_median`, `ndvi_median`, `ndwi_median`

### 4) NDWI definition

NDWI is computed as a normalized difference of **green** and **nir** (replacing the previous swir/nir formulation) for consistency with the current project analysis criteria.

### 5) Shared-account safety

- `MOSAIC_REQUIRE_EXPORT_TAG=1` (default): the script fails at startup if `MOSAIC_EXPORT_TAG` is missing.
- Use a unique tag per run (e.g. `pedro-YYYYMMDD-a`) to avoid collisions in the Earth Engine task queue.

### 6) Modular runner

Both `mosaico_reduce/run_pipeline.py` and `mosaico_reduce_mgrs/run_pipeline.py`:

1. Validate GPKG ↔ tile overlap via `check_gpkg_tile_overlap.py`.
2. Launch the mosaic script only when overlap is confirmed.

Optional flags: `--export-tag`, `--max-jobs`, `--skip-task-guard` (sets `MOSAIC_SKIP_ACTIVE_TASK_GUARD=1` for faster startup).

## Recommended execution (PowerShell)

Direct mosaic script (CIM grid):

```powershell
cd mosaic_test\mosaico_reduce
$env:MOSAIC_EXPORT_TAG='pedro-YYYYMMDD-a'
$env:MOSAIC_REQUIRE_EXPORT_TAG='1'
$env:MOSAIC_CORE_BANDS_ONLY_EXPORT='1'
$env:MOSAIC_STRICT_SENSOR_YEAR_GUARD='1'
$env:MOSAIC_REDUCED_MODE='1'
$env:MOSAIC_MAX_JOBS='1'   # optional smoke test
python .\mapbiomas_Chile_mosaics_landsat_v1.py
```

With GPKG overlap check:

```powershell
cd mosaic_test\mosaico_reduce
python .\run_pipeline.py --tile SJ-18-X-B --export-tag pedro-YYYYMMDD-a --max-jobs 1
```

MGRS variant — see [mosaico_reduce_mgrs/README.md](mosaico_reduce_mgrs/README.md).

## Monitor Earth Engine tasks

- Web: https://code.earthengine.google.com/tasks
- CLI:

```powershell
earthengine --project mapbiomas-chile task list | Select-String "TMP-CHILE"
```
