#!/usr/bin/env python3
"""Estimate ecoregion polygon fill by complete CIM mosaic tiles (memory-safe).

Counts 30 m eco-raster pixels that fall in coarse cells with valid mosaic data.
Coarse factor F deduplicates overlaps between adjacent CIM tiles.

Example:
  python scripts/analyze_eco_mosaic_coverage.py
  python scripts/analyze_eco_mosaic_coverage.py --coarse-factor 1  # exact, needs ~8GB+ RAM
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import rasterio
from rasterio.errors import WindowError
from rasterio.windows import Window, from_bounds
from rasterio.warp import reproject, Resampling, transform_bounds

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import load_yaml, resolve_results_dir

ECO_NAMES = {
    1: "E1 Puna seca andina",
    2: "E2 Desierto de Atacama",
    3: "E3 Matorral norte 1",
    4: "E4 Estepa andina",
    5: "E5 Matorral norte 2",
    6: "E6 Andes norte",
    7: "E7 Andes central",
    8: "E8 Matorral sur",
    9: "E9 Costa norte",
    10: "E10 Andes sur",
    11: "E11 Costa sur 1",
    12: "E12 Costa sur 2",
    13: "E13 Andes sur costa",
    14: "E14 Estepa patagonica",
    15: "E15 Bosque subpolar",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eco mask fill vs complete CIM mosaics")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument(
        "--mosaic-shards-dir",
        default="/home/lserey/mapbiomas_land/mosaic_184bands/2015",
        help="Directory with CIM 184B shard GeoTIFFs",
    )
    p.add_argument(
        "--coarse-factor",
        type=int,
        default=4,
        help="Downsample factor for coverage OR grid (4 ≈ 120 m cells)",
    )
    p.add_argument(
        "--min-shards",
        type=int,
        default=6,
        help="Minimum shards to treat a CIM tile as complete",
    )
    p.add_argument(
        "--out",
        default=None,
        help="JSON output path (default: results/eco_mosaic_coverage.json)",
    )
    return p.parse_args()


def wgs84_bounds(left: float, bottom: float, right: float, top: float) -> tuple[float, float, float, float]:
    """Normalize WGS84 bounds to south/west/north/east order."""
    west, east = min(left, right), max(left, right)
    south, north = min(bottom, top), max(bottom, top)
    return west, south, east, north


def list_complete_cim_tiles(shards_dir: Path, min_shards: int) -> list[str]:
    pat = re.compile(r"^(CHILE-[A-Z]{2}-\d{2}-[A-Z]-[A-Z])-2015")
    counts: Counter[str] = Counter()
    for f in shards_dir.glob("*.tif"):
        m = pat.match(f.name)
        if m:
            counts[m.group(1)] += 1
    return sorted(t for t, n in counts.items() if n >= min_shards)


def tile_union_bounds_wgs84(tile: str, shards_dir: Path, dst_crs) -> tuple[float, float, float, float] | None:
    shards = sorted(shards_dir.glob(f"{tile}-*.tif"))
    if not shards:
        return None
    west = south = east = north = None
    for sp in shards:
        with rasterio.open(sp) as ms:
            b = ms.bounds
            if ms.crs != dst_crs:
                b = transform_bounds(ms.crs, dst_crs, *b)
            w, s, e, n = wgs84_bounds(b.left, b.bottom, b.right, b.top)
        west = w if west is None else min(west, w)
        south = s if south is None else min(south, s)
        east = e if east is None else max(east, e)
        north = n if north is None else max(north, n)
    return west, south, east, north


def window_from_bounds(
    bounds_wgs84: tuple[float, float, float, float],
    transform,
    width: int,
    height: int,
) -> Window | None:
    west, south, east, north = bounds_wgs84
    try:
        win = from_bounds(west, south, east, north, transform=transform)
        win = win.intersection(Window(0, 0, width, height)).round_offsets().round_lengths()
    except WindowError:
        return None
    if int(win.width) <= 0 or int(win.height) <= 0:
        return None
    return win


def build_coverage_grid(
    complete_tiles: list[str],
    shards_dir: Path,
    eco_src: rasterio.io.DatasetReader,
    coarse_factor: int,
) -> tuple[np.ndarray, list[str]]:
    """Global coarse grid: 1 where any complete CIM tile has valid mosaic data."""
    H, W = eco_src.height, eco_src.width
    Hc = (H + coarse_factor - 1) // coarse_factor
    Wc = (W + coarse_factor - 1) // coarse_factor
    covered = np.zeros((Hc, Wc), dtype=np.uint8)

    skipped: list[str] = []

    for i, tile in enumerate(complete_tiles, 1):
        bounds = tile_union_bounds_wgs84(tile, shards_dir, eco_src.crs)
        if bounds is None:
            continue
        win = window_from_bounds(bounds, eco_src.transform, W, H)
        if win is None:
            skipped.append(tile)
            continue

        c0, r0, ww, hh = map(int, (win.col_off, win.row_off, win.width, win.height))
        sub_tf = rasterio.windows.transform(win, eco_src.transform)
        tile_valid = np.zeros((hh, ww), dtype=bool)

        for sp in sorted(shards_dir.glob(f"{tile}-*.tif")):
            with rasterio.open(sp) as ms:
                dst = np.zeros((hh, ww), dtype=np.float32)
                reproject(
                    source=rasterio.band(ms, 1),
                    destination=dst,
                    src_transform=ms.transform,
                    src_crs=ms.crs,
                    dst_transform=sub_tf,
                    dst_crs=eco_src.crs,
                    resampling=Resampling.nearest,
                )
                nd = ms.nodata
                if nd is None:
                    tile_valid |= np.isfinite(dst) & (dst != 0)
                else:
                    tile_valid |= np.isfinite(dst) & (dst != nd)

        if not tile_valid.any():
            continue

        # Downsample valid mask to coarse grid and OR into global covered
        hc = (hh + coarse_factor - 1) // coarse_factor
        wc = (ww + coarse_factor - 1) // coarse_factor
        coarse_tile = np.zeros((hc, wc), dtype=bool)
        for ri in range(hc):
            for ci in range(wc):
                block = tile_valid[
                    ri * coarse_factor : (ri + 1) * coarse_factor,
                    ci * coarse_factor : (ci + 1) * coarse_factor,
                ]
                if block.size and block.any():
                    coarse_tile[ri, ci] = True

        r0c, c0c = r0 // coarse_factor, c0 // coarse_factor
        covered[r0c : r0c + hc, c0c : c0c + wc] |= coarse_tile.astype(np.uint8)

        if i % 7 == 0 or i == len(complete_tiles):
            print(f"  coverage tiles {i}/{len(complete_tiles)}", flush=True)

    if skipped:
        print(f"  skipped {len(skipped)} tile(s) outside eco raster: {', '.join(skipped)}")

    return covered, skipped


def count_eco_and_coverage(
    eco_src: rasterio.io.DatasetReader,
    covered: np.ndarray,
    coarse_factor: int,
) -> tuple[Counter[int], Counter[int]]:
    nat: Counter[int] = Counter()
    cov: Counter[int] = Counter()
    H, W = eco_src.height, eco_src.width
    chunk = 2048

    for row0 in range(0, H, chunk):
        rh = min(chunk, H - row0)
        eco_block = eco_src.read(1, window=Window(0, row0, W, rh))
        for e in range(1, 16):
            nat[e] += int((eco_block == e).sum())

        mask = eco_block > 0
        if not mask.any():
            continue
        rr, cc = np.nonzero(mask)
        gcr = (row0 + rr) // coarse_factor
        gcc = cc // coarse_factor
        is_cov = covered[gcr, gcc].astype(bool)
        if not is_cov.any():
            continue
        ev = eco_block[mask]
        is_cov = is_cov  # noqa: PLW0106 — clarity
        for e in range(1, 16):
            cov[e] += int(np.sum(is_cov & (ev == e)))

    return nat, cov


def main() -> None:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    shards_dir = Path(args.mosaic_shards_dir)
    eco_path = Path(cfg["paths"]["ecoregions"])
    results_dir = resolve_results_dir(cfg, ROOT)
    out_path = Path(args.out) if args.out else results_dir / "eco_mosaic_coverage.json"

    complete = list_complete_cim_tiles(shards_dir, args.min_shards)
    print(f"Complete CIM tiles: {len(complete)} (>= {args.min_shards} shards)")
    print(f"Coarse factor: {args.coarse_factor} (~{args.coarse_factor * 30} m cells)")

    with rasterio.open(eco_path) as eco_src:
        print("Building coarse mosaic coverage grid...", flush=True)
        covered, skipped = build_coverage_grid(complete, shards_dir, eco_src, args.coarse_factor)
        print("Counting eco pixels (national + covered)...", flush=True)
        nat, cov = count_eco_and_coverage(eco_src, covered, args.coarse_factor)

    rows = []
    for e in range(1, 16):
        n, c = nat[e], cov[e]
        pct = 100.0 * c / n if n else 0.0
        rows.append(
            {
                "eco_id": e,
                "eco_name": ECO_NAMES[e],
                "pixels_eco_national": n,
                "pixels_eco_covered": c,
                "pct_polygon_covered": round(pct, 2),
                "complete": pct >= 99.5,
            }
        )

    payload = {
        "complete_cim_tiles": len(complete),
        "tiles_used": len(complete) - len(skipped),
        "tiles_skipped_outside_eco": skipped,
        "min_shards": args.min_shards,
        "coarse_factor": args.coarse_factor,
        "approx_cell_m": args.coarse_factor * 30,
        "eco_raster": str(eco_path),
        "mosaic_shards_dir": str(shards_dir),
        "ecoregions": rows,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    print("\n=== Cobertura del polígono enmascarado (eco raster) ===")
    print(f"{'Eco':<6} {'% cubierto':>10}  {'px cubiertos':>14}  {'px nacional':>14}")
    for r in rows:
        tag = "SÍ" if r["complete"] else ("~casi" if r["pct_polygon_covered"] >= 95 else "NO")
        print(
            f"E{r['eco_id']:<2} {r['pct_polygon_covered']:9.1f}%  "
            f"{r['pixels_eco_covered']:14,d}  {r['pixels_eco_national']:14,d}  [{tag}]"
        )
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
