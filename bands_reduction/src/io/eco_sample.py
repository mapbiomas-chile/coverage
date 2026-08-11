"""Sample pixels across all tiles intersecting an ecoregion (merged pool)."""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import rasterio

from .ecoregion import warp_eco_mask_to_mosaic
from .mosaic import read_mosaic_info, resolve_mosaic_path
from .sample import sample_pixels_from_mask

Balance = Literal["equal_per_tile", "area_proportional"]


def _tile_eco_stats(
    tile: str,
    mosaics_dir: str,
    mosaic_filename_template: str,
    mosaic_layout: str,
    ecoregions_path: str,
    eco_id: int,
    year: int,
) -> dict[str, Any]:
    mosaic = resolve_mosaic_path(
        mosaics_dir,
        tile,
        year,
        mosaic_filename_template,
        layout=mosaic_layout,  # type: ignore[arg-type]
    )
    info = read_mosaic_info(mosaic)
    stats = warp_eco_mask_to_mosaic(
        ecoregions_path=ecoregions_path,
        mosaic_crs=info.crs,
        mosaic_transform=info.transform,
        mosaic_width=info.width,
        mosaic_height=info.height,
        ecoregion_id=eco_id,
    )
    return {
        "tile": tile,
        "mosaic_path": str(mosaic),
        "n_eco": int(stats.n_eco),
        "pct_eco": float(stats.pct_eco),
        "mask": stats.mask,
    }


def _tile_sample_block(
    tile: str,
    mosaic_path: str,
    mask: np.ndarray,
    quota: int,
    random_state: int,
) -> dict[str, Any]:
    if quota <= 0:
        return {
            "tile": tile,
            "mosaic_path": mosaic_path,
            "quota": 0,
            "n_requested": 0,
            "n_drawn": 0,
            "n_finite": 0,
            "X": None,
        }
    seed = int(random_state) + sum(ord(c) for c in tile)
    sample = sample_pixels_from_mask(
        mosaic_path,
        mask,
        n_pixels=quota,
        random_state=seed,
    )
    return {
        "tile": tile,
        "mosaic_path": mosaic_path,
        "quota": quota,
        "n_requested": sample.n_requested,
        "n_drawn": sample.n_drawn,
        "n_finite": sample.n_finite,
        "X": sample.X,
    }


def quota_per_tile(
    n_eco_list: list[int],
    n_total: int,
    balance: Balance,
) -> list[int]:
    return _quota_per_tile(n_eco_list, n_total, balance)


def sample_eco_tile(
    *,
    tile: str,
    mosaics_dir: str | Path,
    mosaic_filename_template: str,
    ecoregions_path: str | Path,
    eco_id: int,
    year: int,
    max_pixels: int,
    random_state: int = 42,
    mosaic_layout: str = "mgrs_subdir",
) -> dict[str, Any]:
    """Warp eco mask on one tile and sample up to ``max_pixels`` finite cells."""
    stats = _tile_eco_stats(
        tile,
        str(mosaics_dir),
        mosaic_filename_template,
        mosaic_layout,
        str(ecoregions_path),
        eco_id,
        year,
    )
    if stats["n_eco"] <= 0:
        raise ValueError(f"No eco={eco_id} pixels in tile {tile}")

    n_draw = min(int(stats["n_eco"]), int(max_pixels))
    seed = int(random_state) + sum(ord(c) for c in tile)
    sample = sample_pixels_from_mask(
        stats["mosaic_path"],
        stats["mask"],
        n_pixels=n_draw,
        random_state=seed,
    )

    with rasterio.open(stats["mosaic_path"]) as ds:
        band_names = [
            d if d else f"band_{i}" for i, d in enumerate(ds.descriptions)
        ]

    return {
        "X": sample.X.astype(np.float32, copy=False),
        "band_names": band_names,
        "tile": tile,
        "mosaic_path": stats["mosaic_path"],
        "n_eco": int(stats["n_eco"]),
        "pct_eco": float(stats["pct_eco"]),
        "n_requested": int(n_draw),
        "n_drawn": int(sample.n_drawn),
        "n_finite": int(sample.n_finite),
        "eco_id": int(eco_id),
        "year": int(year),
        "random_state": int(random_state),
    }


def save_eco_tile_sample(out_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tile = payload["tile"]
    npz_path = out_dir / f"{tile}.npz"
    meta_path = out_dir / f"{tile}.json"

    np.savez_compressed(npz_path, X=payload["X"])
    meta = {
        "tile": tile,
        "eco_id": payload["eco_id"],
        "year": payload["year"],
        "mosaic_path": payload["mosaic_path"],
        "n_eco": payload["n_eco"],
        "pct_eco": payload["pct_eco"],
        "n_requested": payload["n_requested"],
        "n_drawn": payload["n_drawn"],
        "n_finite": payload["n_finite"],
        "n_bands": int(payload["X"].shape[1]),
        "band_names": payload["band_names"],
        "random_state": payload["random_state"],
        "npz_path": str(npz_path),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    meta["meta_path"] = str(meta_path)
    return meta


def merge_eco_tile_samples(
    *,
    tiles_dir: str | Path,
    n_pixels: int,
    balance: Balance = "equal_per_tile",
    random_state: int = 42,
    eco_id: int | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    """Merge per-tile NPZ files into one eco-merged sample pool."""
    tiles_dir = Path(tiles_dir)
    metas: list[dict[str, Any]] = []
    for meta_path in sorted(tiles_dir.glob("*.json")):
        meta = json.loads(meta_path.read_text())
        if eco_id is not None and int(meta.get("eco_id", -1)) != int(eco_id):
            continue
        if int(meta.get("n_finite", 0)) <= 0:
            continue
        metas.append(meta)

    if not metas:
        raise ValueError(f"No tile samples found in {tiles_dir}")

    eco_id = int(eco_id if eco_id is not None else metas[0]["eco_id"])
    year = int(year if year is not None else metas[0]["year"])
    metas.sort(key=lambda m: m["tile"])

    quotas = quota_per_tile(
        [int(m["n_eco"]) for m in metas],
        int(n_pixels),
        balance,
    )

    blocks: list[np.ndarray] = []
    tile_rows: list[dict[str, Any]] = []
    band_names = metas[0]["band_names"]

    for meta, quota in zip(metas, quotas):
        X = np.load(meta["npz_path"])["X"]
        n_finite = int(X.shape[0])
        if quota <= 0 or n_finite <= 0:
            tile_rows.append(
                {
                    "tile": meta["tile"],
                    "n_eco": meta["n_eco"],
                    "pct_eco": meta["pct_eco"],
                    "quota": 0,
                    "n_finite": 0,
                    "mosaic_path": meta["mosaic_path"],
                }
            )
            continue

        if n_finite > quota:
            seed = int(random_state) + sum(ord(c) for c in meta["tile"])
            rng = np.random.default_rng(seed)
            pick = rng.choice(n_finite, size=quota, replace=False)
            X = X[pick]

        blocks.append(X.astype(np.float32, copy=False))
        tile_rows.append(
            {
                "tile": meta["tile"],
                "n_eco": meta["n_eco"],
                "pct_eco": meta["pct_eco"],
                "quota": quota,
                "n_requested": quota,
                "n_drawn": min(int(meta["n_drawn"]), n_finite),
                "n_finite": int(X.shape[0]),
                "mosaic_path": meta["mosaic_path"],
            }
        )

    if not blocks:
        raise ValueError("All tile quotas were zero after merge")

    X = np.vstack(blocks).astype(np.float32, copy=False)
    return {
        "X": X,
        "band_names": band_names,
        "tiles_table": pd.DataFrame(tile_rows),
        "eco_id": eco_id,
        "year": year,
        "n_pixels_target": int(n_pixels),
        "n_finite_total": int(X.shape[0]),
        "balance": balance,
        "random_state": int(random_state),
        "n_bands": int(X.shape[1]),
    }


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
    mosaic_layout: str = "mgrs_subdir",
    n_workers: int = 1,
) -> dict[str, Any]:
    """
    Sample up to ``n_pixels`` finite cells inside eco_id across tiles; stack X.

    Returns dict with X (float32), band_names, per_tile stats, meta fields.
    """
    mosaics_dir_s = str(mosaics_dir)
    ecoregions_path_s = str(ecoregions_path)
    workers = max(1, int(n_workers))

    def _stats_args(tile: str) -> tuple[Any, ...]:
        return (
            tile,
            mosaics_dir_s,
            mosaic_filename_template,
            mosaic_layout,
            ecoregions_path_s,
            eco_id,
            year,
        )

    tile_stats: list[dict[str, Any]]
    if workers == 1:
        tile_stats = [_tile_eco_stats(*_stats_args(tile)) for tile in tiles]
    else:
        tile_stats = [None] * len(tiles)  # type: ignore[list-item]
        with ProcessPoolExecutor(max_workers=min(workers, len(tiles))) as pool:
            futures = {
                pool.submit(_tile_eco_stats, *_stats_args(tile)): i
                for i, tile in enumerate(tiles)
            }
            for fut in as_completed(futures):
                tile_stats[futures[fut]] = fut.result()

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

    sample_jobs = list(zip(usable, quotas))
    sampled: list[dict[str, Any]]
    if workers == 1:
        sampled = [
            {
                **_tile_sample_block(
                    t["tile"],
                    t["mosaic_path"],
                    t["mask"],
                    q,
                    random_state,
                ),
                "n_eco": t["n_eco"],
                "pct_eco": t["pct_eco"],
            }
            for t, q in sample_jobs
        ]
    else:
        sampled = [None] * len(sample_jobs)  # type: ignore[list-item]
        with ProcessPoolExecutor(max_workers=min(workers, len(sample_jobs))) as pool:
            futures = {
                pool.submit(
                    _tile_sample_block,
                    t["tile"],
                    t["mosaic_path"],
                    t["mask"],
                    q,
                    random_state,
                ): i
                for i, (t, q) in enumerate(sample_jobs)
            }
            for fut in as_completed(futures):
                i = futures[fut]
                row = fut.result()
                t = usable[i]
                row["n_eco"] = t["n_eco"]
                row["pct_eco"] = t["pct_eco"]
                sampled[i] = row

    blocks: list[np.ndarray] = []
    tile_rows = []
    for row in sampled:
        tile_rows.append(
            {
                "tile": row["tile"],
                "n_eco": row["n_eco"],
                "pct_eco": row["pct_eco"],
                "quota": row["quota"],
                "n_finite": row["n_finite"],
                "mosaic_path": row["mosaic_path"],
                **(
                    {
                        "n_requested": row["n_requested"],
                        "n_drawn": row["n_drawn"],
                    }
                    if row["quota"] > 0
                    else {}
                ),
            }
        )
        if row["X"] is not None:
            blocks.append(row["X"])

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
