# mosaico_test

Working repository for testing and tuning the Landsat mosaic pipeline (Chile), focused on sensor controls, safe exports in a shared account, and NDWI discontinuity validation.

## Current structure

- `mosaico_reduce/`: main pipeline and analysis/plotting utilities.
- `test_mosaico_reduce/`: test/diagnostic profiles and runners.
- `inputs/`: local inputs.
- `outputs/`: generated outputs (plots, exported reports, diagnostic artifacts).

> Note: this repository was flattened to avoid nested git repositories. Previously, the work was inside `coverage-main/`.

## Generated outputs

To avoid confusion when versioning and pushing to GitHub, all generated outputs must be placed in:

- `C:\Users\pedro\Documents\mosaico_test\outputs`

The repository diagnostic and plotting scripts are already configured to write to that folder by default.

## Test block (`test_mosaico_reduce`)

### Main objective

- Diagnose discontinuities caused by sensor changes (`L5/L7 -> L8/L9`) in bands and indices.
- Verify consistency between band names and expected spectral ranges.
- Run reproducible tests without changing the production workflow.

### Key files

- `test_mosaico_reduce/test_profile.json`: run profile for mosaic testing.
- `test_mosaico_reduce/run_test_flow.py`: spatial validation and test mosaic generation.
- `test_mosaico_reduce/diagnosis_profile.json`: profile for discontinuity diagnosis.
- `test_mosaico_reduce/run_discontinuity_diagnosis.py`: numeric and NDWI plot report.
- `test_mosaico_reduce/run_band_naming_audit.py`: spectral naming audit.

### Recommended diagnostic flow

From the repository root:

```powershell
python .\test_mosaico_reduce\run_test_flow.py
python .\test_mosaico_reduce\run_discontinuity_diagnosis.py
python .\test_mosaico_reduce\run_band_naming_audit.py
```

## Main applied changes

### 1) Year/satellite control
In `mosaico_reduce/mapbiomas_Chile_mosaics_landsat_v1.py`, validation for `year + satellite` combinations was added:

- `l7` allowed in the requested window: `1984-01-01` to `2017-01-01` (year `< 2017`).
- If a row does not meet the rule, it is blocked (or warned, depending on configuration).

Associated variable:
- `MOSAIC_STRICT_SENSOR_YEAR_GUARD` (default `1`).

### 2) Export output for tests
The output collection was changed to:
- `projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2`

### 3) Export only core bands
Final export was forced to include bands:
- `blue_median`, `green_median`, `red_median`, `nir_median`, `swir1_median`, `swir2_median`, `ndvi_median`, `ndwi_median`

Associated variable:
- `MOSAIC_CORE_BANDS_ONLY_EXPORT` (default `1`).

### 4) Safe mode in shared account
Protection was added to prevent runs without a tag:

- `MOSAIC_REQUIRE_EXPORT_TAG` (default `1`).
- If `MOSAIC_EXPORT_TAG` is missing, the script fails at startup with an explicit error.

This avoids mixing tasks from different users in the same Earth Engine queue.

## Recommended execution (PowerShell)

From the repository root:

```powershell
$env:MOSAIC_EXPORT_TAG='pedro-YYYYMMDD-a'
$env:MOSAIC_REQUIRE_EXPORT_TAG='1'
$env:MOSAIC_CORE_BANDS_ONLY_EXPORT='1'
$env:MOSAIC_REDUCED_MODE='1'
$env:MOSAIC_STRICT_SENSOR_YEAR_GUARD='1'
$env:MOSAIC_MAX_JOBS='1'   # optional smoke test
python .\mosaico_reduce\mapbiomas_Chile_mosaics_landsat_v1.py
```

## View tasks in Earth Engine

- Web: https://code.earthengine.google.com/tasks
- CLI:

```powershell
earthengine --project mapbiomas-chile task list | Select-String "TMP-CHILE"
```

## Publishing to GitHub

Target: `https://github.com/mapbiomas-chile/coverage`

If push fails via SSH (`Permission denied (publickey)`), configure credentials and retry:

```powershell
git push "git@github.com:mapbiomas-chile/coverage.git" main
```

HTTPS alternative:

```powershell
git push "https://github.com/mapbiomas-chile/coverage.git" main
```
