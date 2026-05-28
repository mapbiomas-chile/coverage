"""Earth Engine assets and local path conventions for cim_mgrs_regrid."""

from __future__ import annotations

from pathlib import Path

# Repo root (cim_mgrs_regrid/ directory that contains this package)
REPO_ROOT = Path(__file__).resolve().parents[1]

# Local-only directories (gitignored)
DATA_DIR = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"

DEFAULT_PARAMS_XLSX = DATA_DIR / "03-parametros-124grids-19962025.xlsx"
DEFAULT_PARAMS_JSON = OUTPUT_DIR / "input_params.json"
DEFAULT_PARAMS_JSON_CIM = OUTPUT_DIR / "input_params_cim.json"
DEFAULT_XWALK_CSV = OUTPUT_DIR / "cim_mgrs_xwalk.csv"

# Min fraction of CIM area overlapping MGRS to include a tile in remap (0 = any touch)
DEFAULT_MIN_OVERLAP_FRAC_OF_CIM = 0.0

# Earth Engine
DEFAULT_EE_PROJECT = "mapbiomas-chile"

# Grilla CIM (geometría de trabajo en el pipeline Landsat actual)
ASSET_CIM_GRID = "projects/mapbiomas-workspace/AUXILIAR/cim-world-1-250000"
CIM_GRID_NAME_PROP = "name"

# Grilla MGRS Colección 3 (objetivo del regrillado)
ASSET_MGRS_TILES = (
    "projects/mapbiomas-chile/assets/LULC/COLLECTION-03/ANCILLARY_DATA/Tiles_Chile_Sentinel"
)

# Colección histórica de mosaicos exportados por celda CIM (salida antigua)
ASSET_LEGACY_MOSAICS = "projects/mapbiomas-chile/assets/MOSAICS/cartas-chile-2"

# Campos candidatos para identificar una tesela MGRS (mismo orden que test_tile_selection.js)
MGRS_TILE_ID_FIELDS = (
    "name",
    "Name",
    "tile",
    "Tile",
    "id",
    "ID",
    "TILE_ID",
    "tile_id",
    "MGRS_TILE",
    "mgrs_tile",
    "MGRS",
    "mgrs",
)
