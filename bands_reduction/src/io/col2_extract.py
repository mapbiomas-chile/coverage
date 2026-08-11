"""Extract 184-band values at Col2 sample polygons (train/val layers)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import Point, box

from src.io.mosaic import (
    MosaicLayout,
    list_available_tiles,
    read_mosaic_info,
    resolve_mosaic_path,
    tile_bounds_wgs84,
)

LayerName = Literal["train", "val"]
ECO_GPKG = {
    1: "E1_Puna_seca_andina.gpkg",
    2: "E2_Desierto_Atacama.gpkg",
    3: "E3_Matorral_norte_1.gpkg",
    4: "E4_Estepa_andina.gpkg",
    5: "E5_Matorral_norte_2.gpkg",
    6: "E6_Andes_norte.gpkg",
    7: "E7_Andes_central.gpkg",
    8: "E8_Matorral_sur.gpkg",
    9: "E9_Costa_Norte.gpkg",
    10: "E10_Andes_Sur.gpkg",
    11: "E11_Costa_Sur_1.gpkg",
    12: "E12_Costa_Sur_2.gpkg",
    13: "E13_Andes_Sur_Costa.gpkg",
    14: "E14_Estepa_patagonica.gpkg",
    15: "E15_Bosque_subpolar.gpkg",
}


def load_tiles_gdf(
    mosaics_dir: Path,
    tiles_gpkg: Path,
    available_tiles: list[str],
    *,
    year: int,
    filename_template: str,
    layout: MosaicLayout = "mgrs_subdir",
) -> gpd.GeoDataFrame:
    if layout == "cim_flat":
        rows = []
        for tile in available_tiles:
            mosaic = resolve_mosaic_path(
                mosaics_dir, tile, year, filename_template, layout=layout
            )
            west, south, east, north = tile_bounds_wgs84(mosaic)
            rows.append({"tile": tile, "geometry": box(west, south, east, north)})
        return gpd.GeoDataFrame(rows, crs="EPSG:4326")

    gdf = gpd.read_file(tiles_gpkg)
    name_col = "Name" if "Name" in gdf.columns else gdf.columns[0]
    gdf = gdf[gdf[name_col].isin(available_tiles)].copy()
    gdf = gdf.to_crs("EPSG:4326")
    gdf["tile"] = gdf[name_col].astype(str)
    return gdf[["tile", "geometry"]]


def assign_tiles(points: gpd.GeoDataFrame, tiles: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    pts = points.copy()
    pts["_orig_idx"] = np.arange(len(pts))
    pts = pts.to_crs("EPSG:4326")
    joined = gpd.sjoin(pts, tiles, how="left", predicate="within")
    if "index_right" in joined.columns:
        joined = joined.drop(columns=["index_right"])
    joined = joined.sort_values("_orig_idx").drop_duplicates(subset=["_orig_idx"], keep="first")
    return joined.drop(columns=["_orig_idx"])


def sample_point_from_mosaic(
    mosaic_path: Path,
    x: float,
    y: float,
    *,
    point_crs: str = "EPSG:4326",
) -> np.ndarray | None:
    with rasterio.open(mosaic_path) as ds:
        if str(point_crs) != str(ds.crs):
            pt = gpd.GeoSeries([Point(x, y)], crs=point_crs).to_crs(ds.crs).iloc[0]
            x, y = float(pt.x), float(pt.y)
        vals = list(ds.sample([(x, y)]))[0]
    arr = np.asarray(vals, dtype=np.float64)
    if arr.size == 0 or not np.isfinite(arr).all():
        return None
    return arr


def extract_col2_layer(
    *,
    samples_dir: Path,
    mosaics_dir: Path,
    tiles_gpkg: Path,
    year: int,
    filename_template: str,
    layer: LayerName,
    eco_ids: list[int] | None = None,
    exclude_classes: tuple[int, ...] = (33, 34),
    mosaic_layout: MosaicLayout = "mgrs_subdir",
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, list[str]]:
    """Extract X, y, index for Col2 polygons from gpkg layers."""
    eco_ids = eco_ids or list(ECO_GPKG.keys())
    available = list_available_tiles(
        mosaics_dir, year, filename_template, layout=mosaic_layout
    )
    tiles = load_tiles_gdf(
        mosaics_dir,
        tiles_gpkg,
        available,
        year=year,
        filename_template=filename_template,
        layout=mosaic_layout,
    )

    rows: list[dict[str, Any]] = []
    band_names: list[str] | None = None
    sample_id = 0

    for eco_id in eco_ids:
        gpkg_name = ECO_GPKG[eco_id]
        gpkg_path = samples_dir / gpkg_name
        if not gpkg_path.is_file():
            raise FileNotFoundError(gpkg_path)
        gdf = gpd.read_file(gpkg_path, layer=layer)
        gdf = gdf[~gdf["class"].isin(list(exclude_classes))].copy()
        gdf["rep_point"] = gdf.geometry.representative_point()
        pts = gpd.GeoDataFrame(
            gdf.drop(columns="geometry"),
            geometry=gdf["rep_point"],
            crs=gdf.crs,
        )
        pts = assign_tiles(pts, tiles)

        for _, row in pts.iterrows():
            tile = row.get("tile")
            if pd.isna(tile):
                continue
            geom: Point = row.geometry
            point_crs = str(pts.crs) if pts.crs is not None else "EPSG:4326"
            mosaic_path = resolve_mosaic_path(
                mosaics_dir, str(tile), year, filename_template, layout=mosaic_layout
            )
            vals = sample_point_from_mosaic(
                mosaic_path,
                float(geom.x),
                float(geom.y),
                point_crs=point_crs,
            )
            if vals is None:
                continue
            if band_names is None:
                with rasterio.open(mosaic_path) as ds:
                    band_names = [
                        d if d else f"band_{i}" for i, d in enumerate(ds.descriptions, start=1)
                    ]
                if len(band_names) != vals.size:
                    band_names = [f"band_{i}" for i in range(vals.size)]
            rows.append(
                {
                    "sample_id": sample_id,
                    "eco_id": int(eco_id),
                    "eco_name": str(row.get("eco_name", f"E{eco_id}")),
                    "class": int(row["class"]),
                    "tile": str(tile),
                    "source_gpkg": gpkg_name,
                    "X": vals,
                }
            )
            sample_id += 1

    if not rows:
        raise ValueError(f"No samples extracted for layer={layer} eco_ids={eco_ids}")

    idx = pd.DataFrame(
        [{k: r[k] for k in ("sample_id", "eco_id", "eco_name", "class", "tile", "source_gpkg")} for r in rows]
    )
    X = np.vstack([r["X"] for r in rows]).astype(np.float64)
    y = idx["class"].to_numpy(dtype=np.int32)
    assert band_names is not None
    return X, y, idx, band_names


def save_col2_npz(
    out_dir: Path,
    *,
    scope: str,
    layer: LayerName,
    year: int,
    X: np.ndarray,
    y: np.ndarray,
    index: pd.DataFrame,
    band_names: list[str],
    meta_extra: dict[str, Any] | None = None,
) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"chile_{layer}_184"
    npz_path = out_dir / f"{tag}.npz"
    index_path = out_dir / f"{tag}_index.csv"
    meta_path = out_dir / f"{tag}.meta.json"

    np.savez_compressed(npz_path, X=X, y=y)
    index.to_csv(index_path, index=False)
    meta = {
        "scope": scope,
        "layer": layer,
        "year": year,
        "n_bands": len(band_names),
        "n": int(X.shape[0]),
        "band_names": band_names,
        "npz_path": str(npz_path),
        "index_path": str(index_path),
        "extraction": "representative_point + rasterio.sample",
    }
    if meta_extra:
        meta.update(meta_extra)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return {"npz": str(npz_path), "index": str(index_path), "meta": str(meta_path)}
