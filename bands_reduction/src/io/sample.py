"""Sample mosaic pixels inside an ecoregion mask (unsupervised)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window


@dataclass(frozen=True)
class PixelSample:
    X: np.ndarray  # (n, n_bands) float32
    rows: np.ndarray  # int32
    cols: np.ndarray  # int32
    n_requested: int
    n_eco_available: int
    n_drawn: int
    n_finite: int
    random_state: int


def sample_pixels_from_mask(
    mosaic_path: str | Path,
    mask: np.ndarray,
    n_pixels: int = 50_000,
    random_state: int = 42,
) -> PixelSample:
    """
    Draw up to ``n_pixels`` random cells where ``mask`` is True and read all bands.

    Drops samples with any non-finite value across bands.
    """
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2D, got shape {mask.shape}")

    rows_all, cols_all = np.nonzero(mask)
    n_eco = int(rows_all.size)
    if n_eco == 0:
        raise ValueError("Ecoregion mask is empty; nothing to sample")

    rng = np.random.default_rng(random_state)
    n_draw = min(int(n_pixels), n_eco)
    pick = rng.choice(n_eco, size=n_draw, replace=False)
    rows = rows_all[pick].astype(np.int32)
    cols = cols_all[pick].astype(np.int32)

    # Sort by row for fewer, more sequential strip reads
    order = np.argsort(rows, kind="stable")
    rows = rows[order]
    cols = cols[order]

    with rasterio.open(mosaic_path) as ds:
        if ds.height != mask.shape[0] or ds.width != mask.shape[1]:
            raise ValueError(
                f"mask shape {mask.shape} != mosaic grid {(ds.height, ds.width)}"
            )
        n_bands = ds.count
        X = np.empty((n_draw, n_bands), dtype=np.float32)

        for r in np.unique(rows):
            sel = rows == r
            c_sel = cols[sel]
            strip = ds.read(window=Window(0, int(r), ds.width, 1))  # (bands, 1, W)
            X[sel] = strip[:, 0, c_sel].T

    finite = np.isfinite(X).all(axis=1)
    n_finite = int(finite.sum())
    return PixelSample(
        X=X[finite],
        rows=rows[finite],
        cols=cols[finite],
        n_requested=int(n_pixels),
        n_eco_available=n_eco,
        n_drawn=n_draw,
        n_finite=n_finite,
        random_state=int(random_state),
    )


def save_pixel_sample(
    out_dir: str | Path,
    sample: PixelSample,
    *,
    tile: str,
    year: int,
    ecoregion_id: int,
    mosaic_path: str | Path,
) -> dict:
    """Write X/rows/cols (.npz) + meta.json under out_dir. Returns meta dict."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"E{ecoregion_id}_{tile}_{year}_n{sample.n_finite}"
    npz_path = out_dir / f"{stem}.npz"
    meta_path = out_dir / f"{stem}.meta.json"

    np.savez_compressed(
        npz_path,
        X=sample.X,
        rows=sample.rows,
        cols=sample.cols,
    )

    meta = {
        "tile": tile,
        "year": int(year),
        "ecoregion_id": int(ecoregion_id),
        "mosaic_path": str(mosaic_path),
        "npz_path": str(npz_path),
        "meta_path": str(meta_path),
        "n_requested": sample.n_requested,
        "n_eco_available": sample.n_eco_available,
        "n_drawn": sample.n_drawn,
        "n_finite": sample.n_finite,
        "n_bands": int(sample.X.shape[1]) if sample.X.ndim == 2 else 0,
        "shape": list(sample.X.shape),
        "random_state": sample.random_state,
        "dtype": str(sample.X.dtype),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta
