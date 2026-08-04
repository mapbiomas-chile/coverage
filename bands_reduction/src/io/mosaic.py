"""Mosaic path resolution and metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rasterio


@dataclass(frozen=True)
class MosaicInfo:
    path: Path
    crs: Any
    width: int
    height: int
    count: int
    dtype: str
    nodata: float | None
    res: tuple[float, float]
    bounds: rasterio.coords.BoundingBox
    transform: Any


def resolve_mosaic_path(
    mosaics_dir: str | Path,
    tile: str,
    year: int,
    filename_template: str,
) -> Path:
    """Build path: {mosaics_dir}/{tile}/TMP-CHILE-{tile}-{year}-SBAND-184B.tif"""
    mosaics_dir = Path(mosaics_dir)
    filename = filename_template.format(tile=tile, year=year)
    path = mosaics_dir / tile / filename
    if not path.is_file():
        raise FileNotFoundError(f"Mosaic not found: {path}")
    return path


def read_mosaic_info(path: str | Path) -> MosaicInfo:
    path = Path(path)
    with rasterio.open(path) as ds:
        return MosaicInfo(
            path=path,
            crs=ds.crs,
            width=ds.width,
            height=ds.height,
            count=ds.count,
            dtype=ds.dtypes[0],
            nodata=ds.nodata,
            res=ds.res,
            bounds=ds.bounds,
            transform=ds.transform,
        )
