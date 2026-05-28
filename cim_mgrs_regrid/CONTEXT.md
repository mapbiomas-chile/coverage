# Design context (chat handoff)

Use this when reopening only this folder or starting a new chat. In Cursor: `@CONTEXT.md` at the start.

## Goal

Switch from **CIM** cells to **MGRS** (`Tiles_Chile_Sentinel`) without losing excluded scenes (`black_list`). Clipping must apply **only where a Landsat scene matches** the specific tile (not a global bbox).

## Validated data

- **Excel / Google Sheet:** same content; local copy at `data/03-parametros-124grids-19962025.xlsx` (do not version).
- Sheet `tabla` from Downloads / Drive.
- **Columns:** `YEAR`, `GRID_NAME`, `SATELLITE`, `BLACK LIST`, `USETILEMASK`, `SATELLITE_COMMENT`.
- **124 grids**, years **1996–2025**, **3,720 rows**.
- **653** rows with `BLACK LIST` populated.
- Matches `legacy/input_params_2026.json` on keys `(year, grid_name, satellite)`.
- With `MOSAIC_STRICT_SENSOR_YEAR_GUARD=1`, **18** Excel rows would be skipped by the current script’s year/sensor rules.

## Agreed terminology

| Concept | Term |
|---------|------|
| CIM → MGRS (new grid) | **regridding** / `cim_mgrs_regrid` |
| Relationship between grids | **spatial crosswalk** (`xwalk/`) |
| Keep exclusions | carry `black_list` (scene IDs, grid-independent) |
| Clipping | **intersection clip** scene ∩ MGRS cell |

## Module name

Chosen folder: **`cim_mgrs_regrid`** (alternatives considered: `cim_mgrs_xwalk`, `cim_mgrs_bl`).

## Current pipeline (reference)

In `mapbiomas_Chile_mosaics_landsat_v1.py`:

1. Geometry from `cim-world-1-250000` filtered by `grid_name`.
2. `getCollection(..., geometry=grid, trashList=black_list)`.
3. WRS tiles + `landsat-mask` if `use_tile_mask=true`.

On migration: replace step 1 with MGRS geometry (or CIM→MGRS crosswalk); steps 2–3 keep the same `black_list` semantics.

## Assets (agreed)

| Role | Asset |
|------|--------|
| Exported mosaics (CIM) | `projects/mapbiomas-chile/assets/MOSAICS/cartas-chile-2` |
| MGRS grid C03 | `projects/mapbiomas-chile/assets/LULC/COLLECTION-03/ANCILLARY_DATA/Tiles_Chile_Sentinel` |
| CIM geometry in pipeline | `projects/mapbiomas-workspace/AUXILIAR/cim-world-1-250000` |

## Repo implementation

- `scripts/build_xwalk.py` → `output/cim_mgrs_xwalk.csv`
- `scripts/excel_to_mgrs_json.py` → `output/input_params.json` (**grid_name = MGRS**, `cim_name` + `black_list` aligned with CIM)
- `scripts/excel_to_json.py` → `output/input_params_cim.json` (CIM reference only)
- CI: tests without GEE

## Next steps

1. Run `inspect_assets.py` and confirm the MGRS id field.
2. Pilot crosswalk: `build_xwalk.py --cim SE-19-V-D`.
3. Clip contract: `grid_name` + JSON row → MGRS geometry (or 1:N union) + unchanged `black_list`.
4. Wire MGRS geometry into `mapbiomas_Chile_mosaics_landsat_v1.py` after validating 1–3.
