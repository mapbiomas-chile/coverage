#!/usr/bin/env python3
"""Cluster bands for one tile at several |r| thresholds (no representatives).

Example:
  python scripts/legacy/07_cluster_tile_thresholds.py --tile 19KCQ \\
    --corr-thresholds 0.95,0.90,0.85
  # → results/E2/2015/02_clusters_by_tile/tiles/19KCQ/{0.95,0.90,0.85}/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import rasterio

from src.evaluation.correlation import abs_corrcoef
from src.io import (
    read_mosaic_info,
    resolve_mosaic_path,
    sample_pixels_from_mask,
    warp_eco_mask_to_mosaic,
)
from src.selection import cluster_bands_from_corr_abs, save_band_clusters
from src.utils import (
    clusters_by_tile_dir,
    corr_threshold_dirname,
    load_yaml,
    resolve_results_dir,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Per-tile band clustering at multiple |r| cuts")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--tile", required=True)
    p.add_argument("--eco-id", type=int, default=2)
    p.add_argument("--year", type=int, default=None)
    p.add_argument(
        "--corr-thresholds",
        default="0.95,0.90,0.85",
        help="Comma-separated |r| cutoffs (distance d=1-|r|)",
    )
    p.add_argument("--n-pixels", type=int, default=None)
    p.add_argument("--random-state", type=int, default=None)
    p.add_argument(
        "--out-root",
        default=None,
        help="Parent of per-tile dirs (default: .../02_clusters_by_tile/tiles)",
    )
    p.add_argument(
        "--save-corr",
        action="store_true",
        help="Also save corr_abs.npy under the tile folder",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    paths = cfg["paths"]
    sampling = cfg.get("sampling", {})
    clustering = cfg.get("clustering", {})

    year = args.year or int(cfg["project"].get("mosaic_year") or cfg["project"].get("year"))
    n_pixels = args.n_pixels or int(
        clustering.get("per_tile_n_pixels") or sampling.get("n_pixels", 30_000)
    )
    random_state = args.random_state or int(sampling.get("random_state", 42))
    linkage = clustering.get("linkage", "average")

    corr_thrs = [float(x.strip()) for x in args.corr_thresholds.split(",") if x.strip()]
    if not corr_thrs:
        print("No corr thresholds", file=sys.stderr)
        return 1

    mosaics_dir = paths.get("mosaics_dir") or paths.get("mosaic")
    template = paths.get(
        "mosaic_filename_template",
        "TMP-CHILE-{tile}-{year}-SBAND-184B.tif",
    )
    mosaic_path = resolve_mosaic_path(mosaics_dir, args.tile, year, template)
    info = read_mosaic_info(mosaic_path)

    with rasterio.open(mosaic_path) as ds:
        band_names = list(ds.descriptions)

    stats = warp_eco_mask_to_mosaic(
        ecoregions_path=paths["ecoregions"],
        mosaic_crs=info.crs,
        mosaic_transform=info.transform,
        mosaic_width=info.width,
        mosaic_height=info.height,
        ecoregion_id=args.eco_id,
    )
    if stats.n_eco == 0:
        print(
            json.dumps(
                {
                    "tile": args.tile,
                    "eco_id": args.eco_id,
                    "status": "SKIP",
                    "reason": "no_eco_pixels",
                }
            )
        )
        return 0

    sample = sample_pixels_from_mask(
        mosaic_path,
        stats.mask,
        n_pixels=n_pixels,
        random_state=random_state,
    )
    if sample.n_finite < 10:
        print(
            json.dumps(
                {
                    "tile": args.tile,
                    "status": "SKIP",
                    "reason": "too_few_finite_samples",
                    "n_finite": sample.n_finite,
                }
            )
        )
        return 0

    corr = abs_corrcoef(sample.X)

    results_dir = resolve_results_dir(cfg, ROOT)
    default_tiles_root = clusters_by_tile_dir(results_dir, args.eco_id, year) / "tiles"
    out_root = Path(args.out_root or default_tiles_root)
    tile_dir = out_root / args.tile
    tile_dir.mkdir(parents=True, exist_ok=True)

    if args.save_corr:
        np.save(tile_dir / "corr_abs.npy", corr)

    tile_meta = {
        "tile": args.tile,
        "year": year,
        "eco_id": args.eco_id,
        "mosaic_path": str(mosaic_path),
        "n_eco_pixels": stats.n_eco,
        "pct_eco": round(stats.pct_eco, 4),
        "n_requested": sample.n_requested,
        "n_drawn": sample.n_drawn,
        "n_finite": sample.n_finite,
        "random_state": random_state,
        "linkage": linkage,
        "corr_thresholds": corr_thrs,
        "band_names": band_names,
    }
    (tile_dir / "tile_meta.json").write_text(json.dumps(tile_meta, indent=2) + "\n")

    name_by_idx = {
        i: band_names[i] if band_names[i] else f"band_{i}" for i in range(len(band_names))
    }

    results_brief = []
    for thr in corr_thrs:
        d_cut = 1.0 - thr
        result = cluster_bands_from_corr_abs(
            corr,
            distance_threshold=d_cut,
            linkage_method=linkage,
        )
        result["assignment"]["band_name"] = result["assignment"]["band_index"].map(
            name_by_idx
        )
        out_dir = tile_dir / corr_threshold_dirname(thr)
        summary = save_band_clusters(
            result,
            out_dir,
            extra_meta={
                "tile": args.tile,
                "eco_id": args.eco_id,
                "year": year,
                "corr_threshold": thr,
                "n_finite_samples": sample.n_finite,
                "n_eco_pixels": stats.n_eco,
            },
        )
        results_brief.append(
            {
                "corr_threshold": thr,
                "distance_threshold": d_cut,
                "n_clusters": summary["n_clusters"],
                "n_singletons": summary["n_singletons"],
                "n_multi": summary["n_multi"],
                "out_dir": summary["out_dir"],
            }
        )

    payload = {
        "tile": args.tile,
        "eco_id": args.eco_id,
        "status": "PASS",
        "n_finite": sample.n_finite,
        "thresholds": results_brief,
        "tile_dir": str(tile_dir),
    }
    (tile_dir / "thresholds_summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
