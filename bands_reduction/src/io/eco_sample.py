"""Sample pixels across all tiles intersecting an ecoregion (merged pool)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import rasterio

from .ecoregion import warp_eco_mask_to_mosaic
from .mosaic import read_mosaic_info, resolve_mosaic_path
from .sample import sample_pixels_from_mask

Balance = Literal["equal_per_tile", "area_proportional"]


def _quota_per_tile(
    n_eco_list: list[int],
    n_total: int,
    balance: Balance,
) -> list[int]:
    n_tiles = len(n_eco_list)
    if n_tiles == 0:
        return []
    eco = np.asarray(n_eco_list, dtype=np.int64)
    if balance == "area_proportional":
        weights = eco.astype(np.float64)
        weights = weights / weights.sum() if weights.sum() > 0 else np.ones(n_tiles) / n_tiles
        raw = weights * n_total
        quotas = np.floor(raw).astype(int)
        # assign remainder to largest fractional parts
        rem = int(n_total - quotas.sum())
        order = np.argsort(-(raw - quotas))
        for k in range(rem):
            quotas[order[k % n_tiles]] += 1
    else:
        # equal_per_tile, then clip to available
        base = n_total // n_tiles
        rem = n_total % n_tiles
        quotas = np.full(n_tiles, base, dtype=int)
        quotas[:rem] += 1

    quotas = np.minimum(quotas, eco)
    # redistribute shortfall if some tiles had too few eco pixels
    shortfall = int(n_total - quotas.sum())
    if shortfall > 0:
        spare = eco - quotas
        for i in np.argsort(-spare):
            if shortfall <= 0:
                break
            add = min(int(spare[i]), shortfall)
            quotas[i] += add
            shortfall -= add
    return [int(x) for x in quotas]


def sample_ecoregion_merged(
    *,
    tiles: list[str],
    mosaics_dir: str | Path,
    mosaic_filename_template: str,
    ecoregions_path: str | Path,
    eco_id: int,
    year: int,
    n_pixels: int,
    balance: Balance = "equal_per_tile",
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Sample up to ``n_pixels`` finite cells inside eco_id across tiles; stack X.

    Returns dict with X (float32), band_names, per_tile stats, meta fields.
    """
    # first pass: eco counts
    tile_stats = []
    for tile in tiles:
        mosaic = resolve_mosaic_path(mosaics_dir, tile, year, mosaic_filename_template)
        info = read_mosaic_info(mosaic)
        stats = warp_eco_mask_to_mosaic(
            ecoregions_path=ecoregions_path,
            mosaic_crs=info.crs,
            mosaic_transform=info.transform,
            mosaic_width=info.width,
            mosaic_height=info.height,
            ecoregion_id=eco_id,
        )
        tile_stats.append(
            {
                "tile": tile,
                "mosaic_path": str(mosaic),
                "n_eco": int(stats.n_eco),
                "pct_eco": float(stats.pct_eco),
                "mask": stats.mask,
                "info": info,
            }
        )

    usable = [t for t in tile_stats if t["n_eco"] > 0]
    if not usable:
        raise ValueError(f"No eco={eco_id} pixels in any of {len(tiles)} tiles")

    quotas = _quota_per_tile(
        [t["n_eco"] for t in usable],
        int(n_pixels),
        balance,
    )

    # band names from first mosaic
    with rasterio.open(usable[0]["mosaic_path"]) as ds:
        band_names = [
            d if d else f"band_{i}" for i, d in enumerate(ds.descriptions)
        ]

    blocks: list[np.ndarray] = []
    tile_rows = []
    for t, q in zip(usable, quotas):
        if q <= 0:
            tile_rows.append(
                {
                    "tile": t["tile"],
                    "n_eco": t["n_eco"],
                    "pct_eco": t["pct_eco"],
                    "quota": 0,
                    "n_finite": 0,
                    "mosaic_path": t["mosaic_path"],
                }
            )
            continue
        # distinct seed per tile for reproducibility
        seed = int(random_state) + sum(ord(c) for c in t["tile"])
        sample = sample_pixels_from_mask(
            t["mosaic_path"],
            t["mask"],
            n_pixels=q,
            random_state=seed,
        )
        blocks.append(sample.X)
        tile_rows.append(
            {
                "tile": t["tile"],
                "n_eco": t["n_eco"],
                "pct_eco": t["pct_eco"],
                "quota": q,
                "n_requested": sample.n_requested,
                "n_drawn": sample.n_drawn,
                "n_finite": sample.n_finite,
                "mosaic_path": t["mosaic_path"],
            }
        )

    if not blocks:
        raise ValueError("All tile quotas were zero")

    X = np.vstack(blocks).astype(np.float32, copy=False)
    return {
        "X": X,
        "band_names": band_names,
        "tiles_table": pd.DataFrame(tile_rows),
        "eco_id": int(eco_id),
        "year": int(year),
        "n_pixels_target": int(n_pixels),
        "n_finite_total": int(X.shape[0]),
        "balance": balance,
        "random_state": int(random_state),
        "n_bands": int(X.shape[1]),
    }


def save_eco_merged_sample(out_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    npz_path = out_dir / "sample.npz"
    meta_path = out_dir / "sample_meta.json"
    tiles_csv = out_dir / "sample_tiles.csv"

    np.savez_compressed(npz_path, X=payload["X"])
    payload["tiles_table"].to_csv(tiles_csv, index=False)

    meta = {
        "eco_id": payload["eco_id"],
        "year": payload["year"],
        "n_pixels_target": payload["n_pixels_target"],
        "n_finite_total": payload["n_finite_total"],
        "n_bands": payload["n_bands"],
        "balance": payload["balance"],
        "random_state": payload["random_state"],
        "band_names": payload["band_names"],
        "npz_path": str(npz_path),
        "tiles_csv": str(tiles_csv),
        "n_tiles_used": int((payload["tiles_table"]["n_finite"] > 0).sum()),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    meta["meta_path"] = str(meta_path)
    return meta
