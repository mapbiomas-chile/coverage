"""Rutas de insumos en el cluster y prefijos GCS para modo --data-source cluster."""

from __future__ import annotations

from pathlib import Path

from project_paths import MAPBIOMAS_LAND_ROOT

ANCILLARY_DIR = MAPBIOMAS_LAND_ROOT / "ancillary_data"
LANDCOVER_DIR = ANCILLARY_DIR / "landcover_col2"
ECO_TIF = ANCILLARY_DIR / "ecorregiones_col3_30m.tif"
MGRS_GPKG = ANCILLARY_DIR / "Tiles_Chile_Sentinel.gpkg"

DEFAULT_EE_PROJECT = "mapbiomas-chile"
# Exports SHP (descarga al cluster).
GCS_BUCKET = "mapbiomas-chile"
# GeoTIFF para ee.Image.loadGeoTIFF (debe estar en us-central1 o multi-region US).
GCS_INPUT_BUCKET = "mapbiomas-chile-coverage-test-staging"
GCS_INPUT_PREFIX = "ssl4eo_sample_generation/inputs"
GCS_EXPORT_PREFIX = "image_download/ssl4eo_sample_generation/exports"


def landcover_gcs_uri(
    year: int,
    *,
    bucket: str = GCS_INPUT_BUCKET,
    prefix: str = GCS_INPUT_PREFIX,
) -> str:
    rel = f"{prefix.strip('/')}/landcover_col2/classification_{year}.tif"
    return f"gs://{bucket}/{rel}"


def eco_gcs_uri(*, bucket: str = GCS_INPUT_BUCKET, prefix: str = GCS_INPUT_PREFIX) -> str:
    rel = f"{prefix.strip('/')}/ecorregiones_col3_30m.tif"
    return f"gs://{bucket}/{rel}"


def export_gcs_prefix(export_name: str, *, bucket: str = GCS_BUCKET, prefix: str = GCS_EXPORT_PREFIX) -> str:
    """Prefijo GCS (sin gs://) para Export.table.toCloudStorage."""
    return f"{prefix.strip('/')}/{export_name}"


def check_cluster_inputs(
    *,
    start_year: int,
    end_year: int,
    landcover_dir: Path = LANDCOVER_DIR,
    eco_tif: Path = ECO_TIF,
    mgrs_gpkg: Path = MGRS_GPKG,
) -> list[str]:
    missing: list[str] = []
    if not mgrs_gpkg.is_file():
        missing.append(str(mgrs_gpkg))
    if not eco_tif.is_file():
        missing.append(str(eco_tif))
    for year in range(start_year, end_year + 1):
        path = landcover_dir / f"classification_{year}.tif"
        if not path.is_file():
            missing.append(str(path))
    return missing
