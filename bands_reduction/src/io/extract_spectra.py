"""Extract 184-band spectra for labeled sample geometries from mosaic tiles."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio


def list_mosaic_tiles(mosaic_dir: str | Path) -> list[str]:
    mosaic_dir = Path(mosaic_dir)
    return sorted(p.name for p in mosaic_dir.iterdir() if p.is_dir())


def mosaic_path_for_tile(mosaic_dir: str | Path, tile: str, year: int = 2015) -> Path:
    mosaic_dir = Path(mosaic_dir)
    name = f"TMP-CHILE-{tile}-{year}-SBAND-184B.tif"
    path = mosaic_dir / tile / name
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def load_all_train_samples(samples_dir: str | Path) -> gpd.GeoDataFrame:
    """Load layer 'train' from every E*.gpkg in samples_dir."""
    samples_dir = Path(samples_dir)
    frames: list[gpd.GeoDataFrame] = []
    for gpkg in sorted(samples_dir.glob("E*.gpkg")):
        gdf = gpd.read_file(gpkg, layer="train")
        gdf["source_gpkg"] = gpkg.name
        frames.append(gdf)
    if not frames:
        raise FileNotFoundError(f"No E*.gpkg train layers in {samples_dir}")
    out = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    if out.crs is None:
        out = out.set_crs("EPSG:4326")
    return out


def assign_tiles(
    samples: gpd.GeoDataFrame,
    tiles_gpkg: str | Path,
    mosaic_tiles: list[str],
) -> gpd.GeoDataFrame:
    """Assign each sample to one mosaic tile via representative_point."""
    foot = gpd.read_file(tiles_gpkg)
    if "Name" not in foot.columns:
        raise KeyError(f"Expected 'Name' in {tiles_gpkg}, got {list(foot.columns)}")
    foot = foot[foot["Name"].isin(mosaic_tiles)].copy()
    if foot.crs != samples.crs:
        foot = foot.to_crs(samples.crs)

    pts = samples.copy()
    pts["geometry"] = pts.geometry.representative_point()
    pts["sample_id"] = np.arange(len(pts), dtype=np.int32)
    joined = gpd.sjoin(
        pts[["sample_id", "geometry"]],
        foot[["Name", "geometry"]],
        how="left",
        predicate="intersects",
    )
    joined = joined.drop_duplicates(subset=["sample_id"], keep="first")
    tile_by_id = joined.set_index("sample_id")["Name"]
    out = samples.copy()
    out["sample_id"] = np.arange(len(out), dtype=np.int32)
    out["tile"] = out["sample_id"].map(tile_by_id)
    return out


def _sample_tile_worker(payload: dict[str, Any]) -> dict[str, Any]:
    """Worker: sample centroids for all rows assigned to one tile."""
    tile = payload["tile"]
    mosaic = payload["mosaic_path"]
    xs = payload["xs"]
    ys = payload["ys"]
    sample_ids = payload["sample_ids"]
    n_bands = payload["n_bands"]

    X = np.full((len(sample_ids), n_bands), np.nan, dtype=np.float32)
    ok = np.zeros(len(sample_ids), dtype=bool)
    with rasterio.open(mosaic) as ds:
        if ds.count != n_bands:
            raise ValueError(f"{mosaic} has {ds.count} bands, expected {n_bands}")
        coords = list(zip(xs, ys))
        for i, vals in enumerate(ds.sample(coords)):
            arr = np.asarray(vals, dtype=np.float32)
            if arr.shape[0] != n_bands:
                continue
            if not np.isfinite(arr).any():
                continue
            X[i] = arr
            ok[i] = bool(np.isfinite(arr).all())
    return {
        "tile": tile,
        "sample_ids": np.asarray(sample_ids, dtype=np.int32),
        "X": X,
        "ok": ok,
    }


def extract_spectra_by_tile(
    samples_with_tiles: gpd.GeoDataFrame,
    mosaic_dir: str | Path,
    *,
    year: int = 2015,
    n_bands: int = 184,
    max_workers: int = 4,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Return X (n,184), ok mask, band_names. Rows align with samples_with_tiles order."""
    mosaic_dir = Path(mosaic_dir)
    n = len(samples_with_tiles)
    X = np.full((n, n_bands), np.nan, dtype=np.float32)
    ok = np.zeros(n, dtype=bool)

    band_names: list[str] | None = None
    valid = samples_with_tiles["tile"].notna()
    groups = samples_with_tiles.loc[valid].groupby("tile", sort=True)

    jobs: list[dict[str, Any]] = []
    for tile, grp in groups:
        mpath = mosaic_path_for_tile(mosaic_dir, tile, year)
        if band_names is None:
            with rasterio.open(mpath) as ds:
                band_names = [
                    d if d else f"band_{i}"
                    for i, d in enumerate(ds.descriptions, start=1)
                ]
        with rasterio.open(mpath) as ds:
            pts = gpd.GeoDataFrame(
                {
                    "sample_id": grp["sample_id"].to_numpy(),
                    "row_pos": grp.index.to_numpy(),
                },
                geometry=grp.geometry.representative_point().to_numpy(),
                crs=samples_with_tiles.crs,
            ).to_crs(ds.crs)
        jobs.append(
            {
                "tile": tile,
                "mosaic_path": str(mpath),
                "xs": pts.geometry.x.to_numpy(),
                "ys": pts.geometry.y.to_numpy(),
                "sample_ids": pts["sample_id"].to_numpy(),
                "row_pos": pts["row_pos"].to_numpy(),
                "n_bands": n_bands,
            }
        )

    if band_names is None:
        band_names = [f"band_{i}" for i in range(1, n_bands + 1)]

    id_to_row = {
        int(sid): int(pos)
        for sid, pos in zip(
            samples_with_tiles["sample_id"].to_numpy(),
            np.arange(n),
        )
    }

    workers = max(1, min(max_workers, len(jobs)))
    payloads = [{k: v for k, v in j.items() if k != "row_pos"} for j in jobs]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_sample_tile_worker, p): p["tile"] for p in payloads}
        for fut in as_completed(futs):
            results.append(fut.result())

    for res in results:
        for sid, xrow, is_ok in zip(res["sample_ids"], res["X"], res["ok"]):
            r = id_to_row[int(sid)]
            X[r] = xrow
            ok[r] = bool(is_ok)

    return X, ok, band_names
