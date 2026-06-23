"""Rutas comunes del proyecto MapBiomas muestras SSL4EO (scale300)."""

import os
from pathlib import Path

MAPBIOMAS_LAND_ROOT = Path(
    os.environ.get("MAPBIOMAS_LAND_ROOT", "/home/lserey/mapbiomas_land")
)

_grillas_root = os.environ.get("GRILLAS_ROOT")
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if _grillas_root:
    GRILLAS_ROOT = Path(_grillas_root)
else:
    GRILLAS_ROOT = REPO_ROOT
FINALES_DIR = GRILLAS_ROOT / "final_samples"
INTERMEDIOS_DIR = GRILLAS_ROOT / "intermediate_files"
GRID_CHARACTERIZATION_DIR = INTERMEDIOS_DIR / "grid_characterization"
REVISION_DIR = INTERMEDIOS_DIR / "review"
CHIPS_DIR = INTERMEDIOS_DIR / "chips_1x1"

GRID_TAGS = ("homogeneo_2x2", "mixto_3x3")

# GeoJSON/CSV bajo final_samples/UTM{18|19}/{homogeneo_2x2|mixto_3x3}/
SELECTION_GEOJSON_GLOB = "final_samples/UTM*/**/seleccion_*.geojson"
SELECTION_CSV_GLOB = "final_samples/UTM*/**/seleccion_*.csv"


def selection_output_dir(utm: int, grid_tag: str) -> Path:
    """Directorio de salida para una seleccion (huso + tamano de rectangulo)."""
    return FINALES_DIR / f"UTM{utm}" / grid_tag


def selection_base_name(
    utm: int,
    grid_tag: str,
    scale: str = "scale300",
) -> str:
    return f"grilla_ssl4eo_muestras_{grid_tag}_UTM{utm}_{scale}"


def selection_paths(utm: int, grid_tag: str, scale: str = "scale300") -> dict[str, Path]:
    out_dir = selection_output_dir(utm, grid_tag)
    stem = selection_base_name(utm, grid_tag, scale)
    return {
        "dir": out_dir,
        "gpkg": out_dir / f"seleccion_{stem}.gpkg",
        "geojson": out_dir / f"seleccion_{stem}.geojson",
        "csv": out_dir / f"seleccion_{stem}.csv",
        "reservas": out_dir / f"reservas_{stem}.csv",
        "taxonomia": out_dir / f"seleccion_{stem}_taxonomia_n3.csv",
    }


def plan_revision_path(utm: int, grid_tag: str, scale: str = "scale300") -> Path:
    return REVISION_DIR / f"plan_revision_UTM{utm}_{grid_tag}_{scale}.csv"


def discover_selection_geojsons() -> list[Path]:
    return sorted(FINALES_DIR.glob("UTM*/**/seleccion_*.geojson"))


def infer_grid_tag(path: Path) -> str:
    for tag in GRID_TAGS:
        if tag in path.parts:
            return tag
    name = path.stem.upper()
    if "HOMOGENEO" in name and "2X2" in name:
        return "homogeneo_2x2"
    if "MIXTO" in name and "3X3" in name:
        return "mixto_3x3"
    return "combined"
