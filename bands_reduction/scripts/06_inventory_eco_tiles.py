#!/usr/bin/env python3
"""List MGRS tiles (2015 184B mosaics) that intersect an ecoregion id.

Example:
  python scripts/06_inventory_eco_tiles.py --eco-id 2
  # → results/E2/2015/01_inventory/tiles.csv (+ tiles.txt)
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
from rasterio.windows import from_bounds
from tqdm import tqdm

from src.io import resolve_mosaic_path
from src.utils import inventory_dir, load_yaml, resolve_results_dir


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Inventory tiles intersecting an ecoregion")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--eco-id", type=int, default=2)
    p.add_argument("--year", type=int, default=None)
    p.add_argument(
        "--tiles-gpkg",
        default="/home/lserey/mapbiomas_land/ancillary_data/Tiles_Chile_Sentinel.gpkg",
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
    window = window.intersection(
        rasterio.windows.Window(0, 0, eco_ds.width, eco_ds.height)
    )
    if window.width <= 0 or window.height <= 0:
        return False, 0
    data = eco_ds.read(1, window=window, boundless=True, fill_value=0)
    n = int((data == eco_id).sum())
    return n > 0, n


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
    results_dir = resolve_results_dir(cfg, ROOT)
    inv = inventory_dir(results_dir, args.eco_id, year)
    out_csv = Path(args.out or inv / "tiles.csv")
    out_list = Path(args.out_list or inv / "tiles.txt")

    available = []
    for d in sorted(mosaics_dir.iterdir()):
        if not d.is_dir():
            continue
        tile = d.name
        try:
            resolve_mosaic_path(mosaics_dir, tile, year, template)
            available.append(tile)
        except FileNotFoundError:
            continue

    import geopandas as gpd

    gdf = gpd.read_file(args.tiles_gpkg)
    name_col = "Name" if "Name" in gdf.columns else gdf.columns[0]
    gdf = gdf[gdf[name_col].isin(available)].copy()

    rows = []
    with rasterio.open(paths["ecoregions"]) as eco_ds:
        for _, row in tqdm(gdf.iterrows(), total=len(gdf), desc=f"eco={args.eco_id}"):
            tile = str(row[name_col])
            minx, miny, maxx, maxy = row.geometry.bounds
            ok, n_approx = tile_has_eco(eco_ds, minx, miny, maxx, maxy, args.eco_id)
            if not ok:
                continue
            mosaic = resolve_mosaic_path(mosaics_dir, tile, year, template)
            rows.append(
                {
                    "tile": tile,
                    "year": year,
                    "eco_id": args.eco_id,
                    "n_eco_bbox_approx": n_approx,
                    "mosaic_path": str(mosaic),
                    "west": minx,
                    "south": miny,
                    "east": maxx,
                    "north": maxy,
                }
            )

    df = pd.DataFrame(rows).sort_values("tile").reset_index(drop=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    out_list.write_text("\n".join(df["tile"].tolist()) + ("\n" if len(df) else ""))
    print(f"tiles_with_mosaic_2015={len(available)}")
    print(f"tiles_intersect_eco_{args.eco_id}={len(df)}")
    print(f"wrote {out_csv}")
    print(f"wrote {out_list}")
    return 0 if len(df) else 1


if __name__ == "__main__":
    raise SystemExit(main())
