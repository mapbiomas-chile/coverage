"""Attach LULC class labels to mosaic-grid sample pixels."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import xy
from rasterio.warp import transform as warp_transform


def attach_labels_from_raster(
    *,
    mosaic_path: str | Path,
    labels_path: str | Path,
    rows: np.ndarray,
    cols: np.ndarray,
    nodata_values: tuple[int, ...] = (0,),
) -> np.ndarray:
    """Sample a classification raster at mosaic pixel centers.

    Returns int32 array of length n. Invalid / nodata samples are set to -1.
    """
    rows = np.asarray(rows)
    cols = np.asarray(cols)
    if rows.shape != cols.shape:
        raise ValueError("rows and cols must have the same shape")

    with rasterio.open(mosaic_path) as mosaic:
        xs, ys = xy(mosaic.transform, rows, cols, offset="center")
        src_crs = mosaic.crs

    with rasterio.open(labels_path) as labels:
        dst_crs = labels.crs
        if src_crs != dst_crs:
            xs, ys = warp_transform(src_crs, dst_crs, xs, ys)
        values = np.array(
            [v[0] for v in labels.sample(zip(xs, ys))],
            dtype=np.float64,
        )
        label_nodata = labels.nodata

    y = np.full(rows.shape[0], -1, dtype=np.int32)
    valid = np.isfinite(values)
    if label_nodata is not None:
        valid &= values != label_nodata
    for nd in nodata_values:
        valid &= values != nd
    y[valid] = values[valid].astype(np.int32)
    return y
