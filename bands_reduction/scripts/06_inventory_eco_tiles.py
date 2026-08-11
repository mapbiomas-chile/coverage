#!/usr/bin/env python3
"""List mosaic tiles (2015 184B) that intersect an ecoregion id.

Supports MGRS subdir layout and CIM flat layout (see paths.mosaic_layout).

Example:
  python scripts/06_inventory_eco_tiles.py --eco-id 2
  # → results/CIM2015/E2/2015/01_inventory/tiles.csv (+ tiles.txt)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import rasterio
from rasterio.errors import WindowError
from rasterio.windows import from_bounds
from tqdm import tqdm

from src.io.mosaic import (
    list_available_tiles,
    mosaic_layout_from_paths,
    resolve_mosaic_path,
    tile_bounds_wgs84,
)
from src.utils import inventory_dir, load_yaml, resolve_results_dir


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Inventory tiles intersecting an ecoregion")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--eco-id", type=int, default=2)
    p.add_argument("--year", type=int, default=None)
    p.add_argument(
        "--tiles-gpkg",
        default="/home/lserey/mapbiomas_land/ancillary_data/Tiles_Chile_Sentinel.gpkg",
        help="Used only for mosaic_layout=mgrs_subdir",
    )
    p.add_argument(
        "--out",
        default=None,
        help="CSV path (default: results/E{eco}/{year}/01_inventory/tiles.csv)",
    )
    p.add_argument(
        "--out-list",
        default=None,
        help="Plain tile list for SLURM (default: same dir tiles.txt)",
    )
    return p.parse_args()


def tile_has_eco(
    eco_ds: rasterio.DatasetReader,
    west: float,
    south: float,
    east: float,
    north: float,
    eco_id: int,
) -> tuple[bool, int]:
    """Approximate: any eco_id pixels in the geographic bbox of the tile."""
    try:
        window = from_bounds(west, south, east, north, transform=eco_ds.transform)
    except Exception:
        return False, 0
    try:
        window = window.intersection(
            rasterio.windows.Window(0, 0, eco_ds.width, eco_ds.height)
        )
    except rasterio.errors.WindowError:
        return False, 0
    if window.width <= 0 or window.height <= 0:
        return False, 0
    data = eco_ds.read(1, window=window, boundless=True, fill_value=0)
    n = int((data == eco_id).sum())
    return n > 0, n


def inventory_cim_flat(
    *,
    mosaics_dir: Path,
    template: str,
    layout: str,
    year: int,
    eco_id: int,
    ecoregions_path: str,
) -> pd.DataFrame:
    available = list_available_tiles(
        mosaics_dir, year, template, layout=layout  # type: ignore[arg-type]
    )
    rows = []
    with rasterio.open(ecoregions_path) as eco_ds:
        for tile in tqdm(available, desc=f"eco={eco_id}"):
            mosaic = resolve_mosaic_path(
                mosaics_dir, tile, year, template, layout=layout  # type: ignore[arg-type]
            )
            west, south, east, north = tile_bounds_wgs84(mosaic)
            ok, n_approx = tile_has_eco(eco_ds, west, south, east, north, eco_id)
            if not ok:
                continue
            rows.append(
                {
                    "tile": tile,
                    "year": year,
                    "eco_id": eco_id,
                    "n_eco_bbox_approx": n_approx,
                    "mosaic_path": str(mosaic),
                    "west": west,
                    "south": south,
                    "east": east,
                    "north": north,
                }
            )
    return pd.DataFrame(rows).sort_values("tile").reset_index(drop=True)


def inventory_mgrs_subdir(
    *,
    mosaics_dir: Path,
    template: str,
    layout: str,
    year: int,
    eco_id: int,
    ecoregions_path: str,
    tiles_gpkg: str,
) -> pd.DataFrame:
    import geopandas as gpd

    available = list_available_tiles(
        mosaics_dir, year, template, layout=layout  # type: ignore[arg-type]
    )
    gdf = gpd.read_file(tiles_gpkg)
    name_col = "Name" if "Name" in gdf.columns else gdf.columns[0]
    gdf = gdf[gdf[name_col].isin(available)].copy()

    rows = []
    with rasterio.open(ecoregions_path) as eco_ds:
        for _, row in tqdm(gdf.iterrows(), total=len(gdf), desc=f"eco={eco_id}"):
            tile = str(row[name_col])
            minx, miny, maxx, maxy = row.geometry.bounds
            ok, n_approx = tile_has_eco(eco_ds, minx, miny, maxx, maxy, eco_id)
            if not ok:
                continue
            mosaic = resolve_mosaic_path(
                mosaics_dir, tile, year, template, layout=layout  # type: ignore[arg-type]
            )
            rows.append(
                {
                    "tile": tile,
                    "year": year,
                    "eco_id": eco_id,
                    "n_eco_bbox_approx": n_approx,
                    "mosaic_path": str(mosaic),
                    "west": minx,
                    "south": miny,
                    "east": maxx,
                    "north": maxy,
                }
            )
    return pd.DataFrame(rows).sort_values("tile").reset_index(drop=True)


def main() -> int:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    paths = cfg["paths"]
    year = args.year or int(cfg["project"].get("mosaic_year") or cfg["project"].get("year"))
    mosaics_dir = Path(paths.get("mosaics_dir") or paths.get("mosaic"))
    template = paths.get(
        "mosaic_filename_template",
        "TMP-CHILE-{tile}-{year}-SBAND-184B.tif",
    )
    layout = mosaic_layout_from_paths(paths)
    results_dir = resolve_results_dir(cfg, ROOT)
    inv = inventory_dir(results_dir, args.eco_id, year)
    out_csv = Path(args.out or inv / "tiles.csv")
    out_list = Path(args.out_list or inv / "tiles.txt")

    available = list_available_tiles(
        mosaics_dir, year, template, layout=layout
    )

    if layout == "cim_flat":
        df = inventory_cim_flat(
            mosaics_dir=mosaics_dir,
            template=template,
            layout=layout,
            year=year,
            eco_id=args.eco_id,
            ecoregions_path=paths["ecoregions"],
        )
    else:
        df = inventory_mgrs_subdir(
            mosaics_dir=mosaics_dir,
            template=template,
            layout=layout,
            year=year,
            eco_id=args.eco_id,
            ecoregions_path=paths["ecoregions"],
            tiles_gpkg=args.tiles_gpkg,
        )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    out_list.write_text("\n".join(df["tile"].tolist()) + ("\n" if len(df) else ""))
    print(f"mosaic_layout={layout}")
    print(f"tiles_with_mosaic_{year}={len(available)}")
    print(f"tiles_intersect_eco_{args.eco_id}={len(df)}")
    print(f"wrote {out_csv}")
    print(f"wrote {out_list}")
    return 0 if len(df) else 1


if __name__ == "__main__":
    raise SystemExit(main())
