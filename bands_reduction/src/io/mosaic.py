"""Mosaic helpers (184-band Landsat MapBiomas tiles)."""
from __future__ import annotations

from pathlib import Path

import rasterio


def find_mosaic_tile(mosaic_dir: str | Path, tile: str, year: int = 2015) -> Path:
    """Resolve TMP-CHILE-<TILE>-<YEAR>-SBAND-184B.tif under mosaic_dir/<TILE>/."""
    mosaic_dir = Path(mosaic_dir)
    name = f"TMP-CHILE-{tile}-{year}-SBAND-184B.tif"
    candidates = [
        mosaic_dir / tile / name,
        mosaic_dir / name,
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"Mosaic tile not found for {tile=} {year=}. Tried: "
        + ", ".join(str(c) for c in candidates)
    )


def read_band_names(mosaic_path: str | Path) -> list[str]:
    with rasterio.open(mosaic_path) as ds:
        names = []
        for i, desc in enumerate(ds.descriptions, start=1):
            names.append(desc if desc else f"band_{i}")
        return names


def mosaic_profile(mosaic_path: str | Path) -> dict:
    with rasterio.open(mosaic_path) as ds:
        return {
            "path": str(mosaic_path),
            "crs": str(ds.crs) if ds.crs else None,
            "width": ds.width,
            "height": ds.height,
            "count": ds.count,
            "dtype": str(ds.dtypes[0]),
            "transform": list(ds.transform)[:6],
            "bounds": list(ds.bounds),
        }
