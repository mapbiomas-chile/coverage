"""Ecoregion mask warped onto a mosaic grid."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject


@dataclass(frozen=True)
class EcoMaskStats:
    ecoregion_id: int
    n_pixels: int
    n_eco: int
    pct_eco: float
    mask: np.ndarray  # bool, shape (height, width) in mosaic grid


def warp_eco_mask_to_mosaic(
    ecoregions_path: str | Path,
    mosaic_crs: Any,
    mosaic_transform: Any,
    mosaic_width: int,
    mosaic_height: int,
    ecoregion_id: int,
) -> EcoMaskStats:
    """
    Reproject the national ecoregion raster onto the mosaic grid (nearest).

    Returns a boolean mask where eco == ecoregion_id.
    """
    ecoregions_path = Path(ecoregions_path)
    dst = np.zeros((mosaic_height, mosaic_width), dtype=np.int16)

    with rasterio.open(ecoregions_path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=mosaic_transform,
            dst_crs=mosaic_crs,
            resampling=Resampling.nearest,
            src_nodata=src.nodata if src.nodata is not None else 0,
            dst_nodata=0,
        )

    mask = dst == int(ecoregion_id)
    n_pixels = int(mask.size)
    n_eco = int(mask.sum())
    pct_eco = 100.0 * n_eco / n_pixels if n_pixels else 0.0
    return EcoMaskStats(
        ecoregion_id=int(ecoregion_id),
        n_pixels=n_pixels,
        n_eco=n_eco,
        pct_eco=pct_eco,
        mask=mask,
    )
