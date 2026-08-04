"""Mosaic path resolution, metadata, and band-name helpers."""

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
