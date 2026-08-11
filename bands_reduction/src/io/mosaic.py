"""Mosaic path resolution and metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import rasterio
from rasterio.warp import transform_bounds

MosaicLayout = Literal["mgrs_subdir", "cim_flat"]
CIM_TILE_RE = re.compile(r"^(CHILE-[A-Z]{2}-\d{2}-[A-Z]-[A-Z])-\d{4}-")


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


def mosaic_layout_from_paths(paths: dict[str, Any]) -> MosaicLayout:
    layout = (paths.get("mosaic_layout") or "mgrs_subdir").strip()
    if layout not in ("mgrs_subdir", "cim_flat"):
        raise ValueError(f"Unknown mosaic_layout: {layout!r}")
    return layout  # type: ignore[return-value]


def parse_cim_tile_id(filename: str) -> str | None:
    m = CIM_TILE_RE.match(Path(filename).name)
    return m.group(1) if m else None


def resolve_mosaic_path(
    mosaics_dir: str | Path,
    tile: str,
    year: int,
    filename_template: str,
    *,
    layout: MosaicLayout = "mgrs_subdir",
) -> Path:
    """Resolve mosaic GeoTIFF for a tile id."""
    mosaics_dir = Path(mosaics_dir)
    filename = filename_template.format(tile=tile, year=year)
    if layout == "cim_flat":
        path = mosaics_dir / filename
    else:
        path = mosaics_dir / tile / filename
    if not path.is_file():
        raise FileNotFoundError(f"Mosaic not found: {path}")
    return path


def list_available_tiles(
    mosaics_dir: str | Path,
    year: int,
    filename_template: str,
    *,
    layout: MosaicLayout = "mgrs_subdir",
) -> list[str]:
    """Return sorted tile ids with a resolvable mosaic file."""
    mosaics_dir = Path(mosaics_dir)
    tiles: list[str] = []

    if layout == "cim_flat":
        for f in sorted(mosaics_dir.glob("*.tif")):
            tile = parse_cim_tile_id(f.name)
            if tile is None:
                continue
            try:
                resolve_mosaic_path(
                    mosaics_dir, tile, year, filename_template, layout=layout
                )
                tiles.append(tile)
            except FileNotFoundError:
                continue
        return sorted(set(tiles))

    for d in sorted(mosaics_dir.iterdir()):
        if not d.is_dir():
            continue
        tile = d.name
        try:
            resolve_mosaic_path(
                mosaics_dir, tile, year, filename_template, layout=layout
            )
            tiles.append(tile)
        except FileNotFoundError:
            continue
    return tiles


def tile_bounds_wgs84(path: Path) -> tuple[float, float, float, float]:
    """Return west, south, east, north in EPSG:4326."""
    with rasterio.open(path) as ds:
        b = ds.bounds
        if ds.crs and str(ds.crs) != "EPSG:4326":
            b = transform_bounds(ds.crs, "EPSG:4326", *b)
    west, east = min(b.left, b.right), max(b.left, b.right)
    south, north = min(b.bottom, b.top), max(b.bottom, b.top)
    return west, south, east, north


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
