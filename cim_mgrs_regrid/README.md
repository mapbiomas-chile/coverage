# cim_mgrs_regrid

Spatial regridding from **CIM 1:250,000** cells to **Chile MGRS tiles (Collection 3)**, preserving `black_list` per `(grid_name, year, satellite)` row and clipping only at scene–tile intersections.

**Tracked on GitHub:** Python code, tests, and documentation.  
**Not tracked:** parameter spreadsheets, generated JSON, crosswalk tables, or GEE exports (`data/` and `output/` are in `.gitignore`).

## Earth Engine assets

| Role | Asset |
|------|--------|
| CIM grid (Landsat pipeline geometry) | `projects/mapbiomas-workspace/AUXILIAR/cim-world-1-250000` |
| MGRS grid C03 (target) | `projects/mapbiomas-chile/assets/LULC/COLLECTION-03/ANCILLARY_DATA/Tiles_Chile_Sentinel` |
| Historical mosaics per CIM cell | `projects/mapbiomas-chile/assets/MOSAICS/cartas-chile-2` |

CIM grid name property: `name` (matches Excel `GRID_NAME`, e.g. `SE-19-V-D`).

## Run parameters (local input)

- Same source as the [Google Sheet](https://docs.google.com/spreadsheets/d/1bg4h66FYsxCifin06Pwjg_-kXhVIMd7n/edit) and `03-parametros-124grids-19962025.xlsx`.
- Sheet `tabla`: 3,720 rows = 124 grids × 1996–2025; 653 rows with `BLACK LIST`.
- Copy the `.xlsx` into `data/` (see `data/README.md`).

## Setup

```powershell
cd cim_mgrs_regrid
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
earthengine authenticate
```

## Scripts

```powershell
# 1) CIM <-> MGRS crosswalk (GEE, run once; writes output/cim_mgrs_xwalk.csv)
python scripts/build_xwalk.py

# 2) Final JSON with MGRS grid_name + black_list from CIM (output/input_params.json)
python scripts/excel_to_mgrs_json.py

# CIM-only JSON (reference / debug)
python scripts/excel_to_json.py --output output/input_params_cim.json

# GEE asset metadata
python scripts/inspect_assets.py
```

Each CIM Excel row is expanded to **one row per intersecting MGRS tile** (`overlap_frac_of_cim` in the crosswalk). The CIM row’s `black_list` is copied to each child MGRS row; if two CIM cells share the same tile for the same year/satellite, lists are **unioned**.

Extra field in MGRS JSON: `cim_name` (traceability to the source CIM cell).

## Layout

```
cim_mgrs_regrid/
  cim_mgrs_regrid/   # package: config, params, gee, xwalk, remap
  scripts/           # CLI
  tests/             # pytest (no GEE)
  data/              # local inputs (gitignored)
  output/            # JSON, crosswalk CSV (gitignored)
```

## Related code (coverage repo)

- Landsat pipeline: `mosaic_test/mosaico_reduce/mapbiomas_Chile_mosaics_landsat_v1.py`
- Sentinel tiles (GEE): `classification_test/test_tile_selection/test_tile_selection.js`

## Design context

See **`CONTEXT.md`**.
