"""Caracterizacion local de grillas SSL4EO (sin Earth Engine)."""

from __future__ import annotations

import math
import shutil
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from shapely.geometry import box, mapping

from cluster_config import ECO_TIF, LANDCOVER_DIR, MGRS_GPKG, check_cluster_inputs
from ecoregion_names import ECO_NAMES
from project_paths import GRID_CHARACTERIZATION_DIR
from taxonomy_classes import (
    NIVEL1_CODE_DICT,
    NIVEL1_NAMES_DICT,
    NIVEL2_CODE_DICT,
    NIVEL2_NAMES_DICT,
    NIVEL3_CODE_DICT,
    NIVEL3_NAMES_DICT,
)

PERIODS = [
    {"name": "P1", "start": 1999, "end": 2005, "nYears": 7},
    {"name": "P2", "start": 2006, "end": 2012, "nYears": 7},
    {"name": "P3", "start": 2013, "end": 2018, "nYears": 6},
    {"name": "P4", "start": 2019, "end": 2024, "nYears": 6},
]

UTM_EPSG = {12: 32712, 17: 32717, 18: 32718, 19: 32719}
MGRS_NAME_FIELD = "Name"
CRITICAL_CLASS_IDS = {23, 61, 33, 67}
NORTH_FOREST_ID = 3
NORTH_FOREST_LAT = -33.2
ACHAPARRADO_ID = 67
TRANSVERSAL_CLASS_IDS = {11, 73, 74, 18, 19, 36, 9, 79, 80, 24, 30, 75, 34}
CONFUSION_PAIRS_DICT = {
    1: [10, 66], 3: [66, 60, 67, 10], 59: [66, 60, 3], 60: [66, 3, 67, 10],
    67: [66, 60, 12, 10], 10: [66, 12, 63, 3], 12: [63, 15, 66, 10],
    63: [12, 15, 66, 10], 66: [3, 60, 12, 63, 10], 14: [15, 12, 63],
    15: [12, 63, 14], 22: [29, 25, 23, 61], 23: [61, 29, 25], 61: [23, 25, 29],
    29: [23, 25, 61, 22], 25: [29, 23, 61, 22], 26: [33], 33: [26], 27: [],
}


def safe_pct(num: float, den: float) -> float:
    return float(num / den * 100.0) if den > 0 else 0.0


def dominant(counts: Counter, total: float) -> tuple[int, float]:
    if not counts or total <= 0:
        return -9999, 0.0
    val, cnt = counts.most_common(1)[0]
    return int(val), safe_pct(cnt, total)


def shannon_index(counts: Counter, total: float) -> float:
    if total <= 0:
        return 0.0
    h = 0.0
    for cnt in counts.values():
        p = cnt / total
        if p > 0:
            h -= p * math.log(p)
    return h


def max_stable_run(stable_flags: list[bool]) -> tuple[int, int, int]:
    best_len = best_start = 0
    cur_len = cur_start = 0
    for idx, flag in enumerate(stable_flags):
        if flag:
            if cur_len == 0:
                cur_start = idx
            cur_len += 1
            if cur_len > best_len:
                best_len = cur_len
                best_start = cur_start
        else:
            cur_len = 0
    if best_len == 0:
        return 0, -9999, -9999
    return best_len, best_start, best_start + best_len - 1


@dataclass
class RunConfig:
    dataset_name: str = "muestras"
    rect_chips_side: int = 2
    chip_pixels: int = 264
    pixel_size: int = 30
    target_utm_zone: int = 19
    stats_scale: int = 300
    start_year: int = 1999
    end_year: int = 2024
    stable_year_pix_threshold: float = 0.75
    min_valid_area_pct: float = 20.0
    min_mgrs_dom_pct: float = 60.0
    class_level: str = "n3"
    landcover_dir: Path = LANDCOVER_DIR
    eco_tif: Path = ECO_TIF
    mgrs_gpkg: Path = MGRS_GPKG


def export_name(cfg: RunConfig) -> str:
    grid_mode = "homogeneo" if cfg.rect_chips_side <= 2 else "mixto"
    level_tag = "_n3" if cfg.class_level == "n3" else "_general"
    return (
        f"grilla_ssl4eo_{cfg.dataset_name}_{grid_mode}_"
        f"{cfg.rect_chips_side}x{cfg.rect_chips_side}_UTM{cfg.target_utm_zone}_"
        f"scale{cfg.stats_scale}{level_tag}"
    )


def load_mgrs(cfg: RunConfig) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(cfg.mgrs_gpkg)
    if MGRS_NAME_FIELD not in gdf.columns:
        raise ValueError(f"Columna {MGRS_NAME_FIELD} no encontrada en {cfg.mgrs_gpkg}")
    gdf = gdf.copy()
    gdf["mgrs_name"] = gdf[MGRS_NAME_FIELD].astype(str)
    gdf["utm_zone"] = gdf["mgrs_name"].str.slice(0, 2).astype(int)
    return gdf[gdf["utm_zone"] == cfg.target_utm_zone].reset_index(drop=True)


def build_rectangles(tile_row: pd.Series, cfg: RunConfig) -> gpd.GeoDataFrame:
    epsg = UTM_EPSG[cfg.target_utm_zone]
    grid_mode = "homogeneo" if cfg.rect_chips_side <= 2 else "mixto"
    chip_size_m = cfg.chip_pixels * cfg.pixel_size
    rect_size_m = chip_size_m * cfg.rect_chips_side
    rect_area_m2 = rect_size_m * rect_size_m
    min_rect_area_frac = 0.99

    tile_name = tile_row["mgrs_name"]
    tile_gdf = gpd.GeoDataFrame([tile_row], geometry="geometry", crs="EPSG:4326")
    tile_utm = tile_gdf.to_crs(epsg)
    minx, miny, maxx, maxy = tile_utm.total_bounds

    n_cols = int(math.floor((maxx - minx) / rect_size_m))
    n_rows = int(math.floor((maxy - miny) / rect_size_m))
    tile_geom = tile_utm.geometry.iloc[0]

    rows = []
    for r in range(n_rows):
        for c in range(n_cols):
            x0 = minx + c * rect_size_m
            x1 = x0 + rect_size_m
            y1 = maxy - r * rect_size_m
            y0 = y1 - rect_size_m
            rect = box(x0, y0, x1, y1)
            if not rect.intersects(tile_geom):
                continue
            inter = rect.intersection(tile_geom)
            if inter.is_empty:
                continue
            rect_frac = inter.area / rect_area_m2
            if rect_frac < min_rect_area_frac:
                continue
            rect_id = (
                f"{tile_name}_{grid_mode}_{cfg.rect_chips_side}x{cfg.rect_chips_side}_"
                f"C{c:03d}_R{r:03d}"
            )
            rows.append({
                "geometry": inter,
                "rect_id": rect_id,
                "col_idx": c,
                "row_idx": r,
                "mgrs_src": tile_name,
                "dataset": cfg.dataset_name,
                "grid_mode": grid_mode,
                "rect_side": cfg.rect_chips_side,
                "rect_m": rect_size_m,
                "rect_area": inter.area,
                "rect_frac": rect_frac,
                "chip_px": cfg.chip_pixels,
                "chip_m": chip_size_m,
                "n_chips_b": cfg.rect_chips_side * cfg.rect_chips_side,
                "utm_zone": cfg.target_utm_zone,
                "utm_epsg": f"EPSG:{epsg}",
                "align": "upper_left",
            })
    if not rows:
        return gpd.GeoDataFrame(columns=["geometry"], crs=f"EPSG:{epsg}")
    return gpd.GeoDataFrame(rows, crs=f"EPSG:{epsg}")


def _read_resampled(path: Path, dst_crs: str, transform, width: int, height: int) -> np.ndarray:
    out = np.zeros((height, width), dtype=np.int16)
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=out,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=Resampling.nearest,
        )
    return out


def _tile_grid(bounds: tuple[float, float, float, float], resolution: float):
    minx, miny, maxx, maxy = bounds
    width = max(1, int(math.ceil((maxx - minx) / resolution)))
    height = max(1, int(math.ceil((maxy - miny) / resolution)))
    transform = from_origin(minx, maxy, resolution, resolution)
    return transform, width, height


def _stats_for_rect(
    label_idx: int,
    labels: np.ndarray,
    eco: np.ndarray,
    years: np.ndarray,
    lats: np.ndarray,
    meta: dict,
    mgrs_geoms: gpd.GeoDataFrame,
    cfg: RunConfig,
) -> dict | None:
    mask = labels == label_idx
    if not mask.any():
        return None

    n_pixels = int(mask.sum())
    eco_px = eco[mask]
    year_px = years[:, mask]
    lat_px = lats[mask]

    mode_px = np.apply_along_axis(
        lambda row: np.bincount(row.astype(np.int32), minlength=128).argmax(),
        0,
        year_px,
    )
    valid = (eco_px > 0) & (mode_px != 27)
    valid_count = int(valid.sum())
    val_pct = safe_pct(valid_count, n_pixels)
    if val_pct < cfg.min_valid_area_pct:
        return None

    eco_valid = eco_px[valid]
    mode_valid = mode_px[valid]
    year_valid = year_px[:, valid]
    lat_valid = lat_px[valid]

    eco_counts = Counter(int(v) for v in eco_valid)
    mode_counts = Counter(int(v) for v in mode_valid)
    last_counts = Counter(int(v) for v in year_valid[-1])

    eco_id, eco_pct = dominant(eco_counts, valid_count)
    mode_id, mode_pct = dominant(mode_counts, valid_count)
    last_id, last_pct = dominant(last_counts, valid_count)

    transitions = np.mean(year_valid[1:] != year_valid[:-1], axis=0)
    tr_pct = float(np.mean(transitions) * 100.0)

    stab_flags = year_valid == mode_valid
    stab_pct = float(np.mean(stab_flags) * 100.0)

    crit_pct = float(np.mean(np.isin(mode_valid, list(CRITICAL_CLASS_IDS))) * 100.0)
    nfor_pct = float(
        np.mean((mode_valid == NORTH_FOREST_ID) & (lat_valid >= NORTH_FOREST_LAT)) * 100.0
    )
    achap_pct = float(np.mean(mode_valid == ACHAPARRADO_ID) * 100.0)
    tran_pct = float(np.mean(np.isin(mode_valid, list(TRANSVERSAL_CLASS_IDS))) * 100.0)
    noobs_pct = float(np.mean(mode_valid == 27) * 100.0)

    shannon = shannon_index(mode_counts, valid_count)
    conf_ids = CONFUSION_PAIRS_DICT.get(mode_id, [])
    conf_area = sum(mode_counts.get(cid, 0) for cid in conf_ids)
    conf_risk_pct = safe_pct(conf_area, valid_count)

    year_stability = np.mean(stab_flags, axis=1)
    stable_years = [
        cfg.start_year + i
        for i, frac in enumerate(year_stability)
        if frac >= cfg.stable_year_pix_threshold
    ]
    stable_yrs_str = ",".join(str(y) for y in stable_years)
    n_stable_years = len(stable_years)
    stable_yr_pct = safe_pct(n_stable_years, cfg.end_year - cfg.start_year + 1)

    stable_flags_full = [
        float(year_stability[i]) >= cfg.stable_year_pix_threshold
        for i in range(cfg.end_year - cfg.start_year + 1)
    ]
    max_stab_run, run_start_idx, run_end_idx = max_stable_run(stable_flags_full)
    run_start = cfg.start_year + run_start_idx if max_stab_run > 0 else -9999
    run_end = cfg.start_year + run_end_idx if max_stab_run > 0 else -9999

    rect_geom = meta["geometry"]
    total_area = rect_geom.area
    inter = mgrs_geoms.copy()
    inter["inter_area"] = inter.geometry.intersection(rect_geom).area
    inter = inter[inter["inter_area"] > 0].sort_values("inter_area", ascending=False)
    if inter.empty:
        return None
    mgrs_dom = inter.iloc[0]["mgrs_name"]
    mgrs_pct = safe_pct(float(inter.iloc[0]["inter_area"]), total_area)
    if mgrs_pct < cfg.min_mgrs_dom_pct:
        return None

    period_stats = {}
    for period in PERIODS:
        p_years = list(range(period["start"], period["end"] + 1))
        idxs = [y - cfg.start_year for y in p_years]
        p_stack = year_valid[idxs, :]
        p_mode = np.apply_along_axis(
            lambda row: np.bincount(row.astype(np.int32), minlength=128).argmax(),
            0,
            p_stack,
        )
        p_counts = Counter(int(v) for v in p_mode)
        p_id, p_pct = dominant(p_counts, valid_count)
        stable_years = []
        for i, y in enumerate(p_years):
            frac = float(np.mean(p_stack[i] == p_mode))
            if frac >= cfg.stable_year_pix_threshold:
                stable_years.append(y)
        period_stats[period["name"]] = {
            "id": p_id,
            "name": NIVEL3_NAMES_DICT.get(str(p_id), "sin_nombre"),
            "pct": p_pct,
            "n_stable": len(stable_years),
            "stab_pct": safe_pct(len(stable_years), period["nYears"]),
            "yrs_str": ",".join(str(y) for y in stable_years),
        }

    p3 = period_stats["P3"]
    p4 = period_stats["P4"]
    if tr_pct >= 15:
        dim_temporal = "transicion"
    elif (
        max_stab_run < 5
        and (p3["n_stable"] >= 3 or p4["n_stable"] >= 3)
    ) or tran_pct > 0:
        dim_temporal = "anual"
    else:
        dim_temporal = "estable"

    if mode_pct >= 85 and shannon <= 0.3:
        dim_espacial = "homogenea"
    elif len(mode_counts) <= 4 and mode_pct >= 45:
        dim_espacial = "simple_media"
    else:
        dim_espacial = "compleja"
    sample_type = f"{dim_temporal}_{dim_espacial}"

    priority_score = (
        val_pct / 100 * 2.0
        + crit_pct / 100 * 4.0
        + nfor_pct / 100 * 3.0
        + achap_pct / 100 * 3.0
        + min(len(mode_counts), 19) / 19 * 2.0
        + shannon / math.log(19) * 1.5
        + tr_pct / 100 * 1.5
        + noobs_pct * -0.05
    )

    mode_key = str(mode_id)
    last_key = str(last_id)
    props = {
        **meta,
        "grid_id": meta["rect_id"],
        "area_km2": total_area / 1e6,
        "val_pct": val_pct,
        "mgrs_dom": mgrs_dom,
        "mgrs_pct": mgrs_pct,
        "n_mgrs": len(inter),
        "eco_id": eco_id,
        "eco_name": ECO_NAMES.get(str(eco_id), "sin_nombre"),
        "eco_pct": eco_pct,
        "mode_id": mode_id,
        "mode_name": NIVEL3_NAMES_DICT.get(mode_key, "sin_nombre"),
        "mode_pct": mode_pct,
        "n_mode": len(mode_counts),
        "last_id": last_id,
        "last_name": NIVEL3_NAMES_DICT.get(last_key, "sin_nombre"),
        "last_pct": last_pct,
        "tr_pct": tr_pct,
        "stab_pct": stab_pct,
        "noobs_pct": noobs_pct,
        "crit_pct": crit_pct,
        "nfor_pct": nfor_pct,
        "achap_pct": achap_pct,
        "tran_pct": tran_pct,
        "shannon": shannon,
        "conf_risk": conf_risk_pct,
        "stab_yrs": stable_yrs_str,
        "n_stab_yrs": n_stable_years,
        "stb_yr_pct": stable_yr_pct,
        "mx_stb_run": max_stab_run,
        "run_start": run_start,
        "run_end": run_end,
        "dim_temp": dim_temporal,
        "dim_spat": dim_espacial,
        "samp_type": sample_type,
        "prio_sc": priority_score,
        "cls_lvl": cfg.class_level,
        "n1_cd": NIVEL1_CODE_DICT.get(mode_key, ""),
        "n2_cd": NIVEL2_CODE_DICT.get(mode_key, ""),
        "n3_cd": NIVEL3_CODE_DICT.get(mode_key, ""),
        "n1_nm": NIVEL1_NAMES_DICT.get(mode_key, ""),
        "n2_nm": NIVEL2_NAMES_DICT.get(mode_key, ""),
        "ln1_cd": NIVEL1_CODE_DICT.get(last_key, ""),
        "ln2_cd": NIVEL2_CODE_DICT.get(last_key, ""),
        "ln3_cd": NIVEL3_CODE_DICT.get(last_key, ""),
    }
    for period in PERIODS:
        p = period_stats[period["name"]]
        props[f"md_id_{period['name']}"] = p["id"]
        props[f"md_nm_{period['name']}"] = p["name"]
        props[f"md_pct_{period['name']}"] = p["pct"]
        props[f"n_stb_{period['name']}"] = p["n_stable"]
        props[f"stb_p_{period['name']}"] = p["stab_pct"]
        props[f"stb_yrs_{period['name']}"] = p["yrs_str"]
    return props


def characterize_tile(tile_row: pd.Series, cfg: RunConfig, mgrs_zone: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    rects = build_rectangles(tile_row, cfg)
    if rects.empty:
        return rects

    epsg = UTM_EPSG[cfg.target_utm_zone]
    dst_crs = f"EPSG:{epsg}"
    minx, miny, maxx, maxy = rects.total_bounds
    transform, width, height = _tile_grid((minx, miny, maxx, maxy), cfg.stats_scale)

    eco = _read_resampled(cfg.eco_tif, dst_crs, transform, width, height)
    years = []
    for year in range(cfg.start_year, cfg.end_year + 1):
        path = cfg.landcover_dir / f"classification_{year}.tif"
        years.append(_read_resampled(path, dst_crs, transform, width, height))
    year_stack = np.stack(years, axis=0)

    yy, xx = np.indices((height, width))
    xs = transform.c + (xx + 0.5) * transform.a
    ys = transform.f + (yy + 0.5) * transform.e
    lon, lat = rasterio.warp.transform(dst_crs, "EPSG:4326", xs.ravel(), ys.ravel())
    lats = np.array(lat, dtype=np.float64).reshape(height, width)

    labels = np.zeros((height, width), dtype=np.int32)
    rect_meta: dict[int, dict] = {}
    for idx, (_, row) in enumerate(rects.iterrows(), start=1):
        geom = row.geometry
        burned = rasterize(
            [(mapping(geom), idx)],
            out_shape=labels.shape,
            transform=transform,
            fill=0,
            dtype=np.int32,
        )
        labels = np.maximum(labels, burned)
        rect_meta[idx] = row.to_dict()

    out_rows = []
    for idx, meta in rect_meta.items():
        stats = _stats_for_rect(
            idx, labels, eco, year_stack, lats, meta, mgrs_zone, cfg
        )
        if stats is None:
            continue
        out_rows.append(stats)

    if not out_rows:
        return gpd.GeoDataFrame(columns=["geometry"], crs=dst_crs)
    return gpd.GeoDataFrame(out_rows, crs=dst_crs)


def characterize(cfg: RunConfig, *, tile_names: list[str] | None = None) -> gpd.GeoDataFrame:
    missing = check_cluster_inputs(
        start_year=cfg.start_year,
        end_year=cfg.end_year,
        landcover_dir=cfg.landcover_dir,
        eco_tif=cfg.eco_tif,
        mgrs_gpkg=cfg.mgrs_gpkg,
    )
    if missing:
        raise FileNotFoundError("Faltan insumos:\n  " + "\n  ".join(missing))

    mgrs = load_mgrs(cfg)
    if tile_names:
        mgrs = mgrs[mgrs["mgrs_name"].isin(tile_names)].reset_index(drop=True)
    mgrs_utm = mgrs.to_crs(UTM_EPSG[cfg.target_utm_zone])

    parts = []
    for i, row in mgrs.iterrows():
        print(f"  Tile {row['mgrs_name']} ({i + 1}/{len(mgrs)})")
        part = characterize_tile(row, cfg, mgrs_utm)
        if not part.empty:
            parts.append(part)

    if not parts:
        return gpd.GeoDataFrame(columns=["geometry"], crs=f"EPSG:{UTM_EPSG[cfg.target_utm_zone]}")
    return pd.concat(parts, ignore_index=True)


def write_geopackage_zip(gdf: gpd.GeoDataFrame, out_zip: Path) -> Path:
    """Empaqueta la grilla en GeoPackage dentro de un ZIP (sin shapefile)."""
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    staging = out_zip.with_suffix("")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    gpkg_path = staging / "grilla.gpkg"
    export_gdf = gdf.copy()
    for col in export_gdf.columns:
        if col == "geometry":
            continue
        if export_gdf[col].dtype == object:
            export_gdf[col] = export_gdf[col].astype(str)
    export_gdf.to_file(gpkg_path, layer="grilla", driver="GPKG")
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(gpkg_path, arcname="grilla.gpkg")
    shutil.rmtree(staging)
    return out_zip


def run_and_export(cfg: RunConfig, output_dir: Path = GRID_CHARACTERIZATION_DIR) -> Path:
    print(
        f"Caracterizacion local UTM{cfg.target_utm_zone} "
        f"{cfg.rect_chips_side}x{cfg.rect_chips_side} scale{cfg.stats_scale}"
    )
    gdf = characterize(cfg)
    print(f"  Rectangulos filtrados: {len(gdf)}")
    name = export_name(cfg)
    out_zip = output_dir / f"{name}.zip"
    write_geopackage_zip(gdf, out_zip)
    print(f"  Exportado: {out_zip}")
    return out_zip
