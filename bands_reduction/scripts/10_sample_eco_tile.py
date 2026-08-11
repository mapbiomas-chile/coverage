#!/usr/bin/env python3
"""Sample pixels inside one tile for an ecoregion (partial pool for merge).

Example:
  python scripts/10_sample_eco_tile.py --eco-id 6 --tile CHILE-SI-19-V-C
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.mosaic import mosaic_layout_from_paths
from src.io import sample_eco_tile, save_eco_tile_sample
from src.utils import eco_merged_dir, load_configs, resolve_results_dir


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sample one tile inside an ecoregion")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--eco-config", default=None)
    p.add_argument("--eco-id", type=int, required=True)
    p.add_argument("--tile", required=True)
    p.add_argument("--year", type=int, default=None)
    p.add_argument(
        "--max-pixels",
        type=int,
        default=None,
        help="Max pixels to draw from this tile (default: n_pixels_eco from config)",
    )
    p.add_argument("--out-dir", default=None, help="Default: .../eco_merged/tiles/")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_configs(ROOT / args.config, args.eco_config)
    paths = cfg["paths"]
    sampling = cfg.get("sampling", {})
    year = args.year or int(cfg["project"].get("mosaic_year") or 2015)
    max_pixels = args.max_pixels or int(sampling.get("n_pixels_eco", 100_000))
    random_state = int(sampling.get("random_state", 42))

    results_dir = resolve_results_dir(cfg, ROOT)
    out_dir = Path(
        args.out_dir or eco_merged_dir(results_dir, args.eco_id, year) / "tiles"
    )

    print(
        json.dumps(
            {
                "eco_id": args.eco_id,
                "tile": args.tile,
                "year": year,
                "max_pixels": max_pixels,
                "out_dir": str(out_dir),
            }
        )
    )

    payload = sample_eco_tile(
        tile=args.tile,
        mosaics_dir=paths["mosaics_dir"],
        mosaic_filename_template=paths.get(
            "mosaic_filename_template",
            "TMP-CHILE-{tile}-{year}-SBAND-184B.tif",
        ),
        ecoregions_path=paths["ecoregions"],
        eco_id=args.eco_id,
        year=year,
        max_pixels=max_pixels,
        random_state=random_state,
        mosaic_layout=mosaic_layout_from_paths(paths),
    )
    meta = save_eco_tile_sample(out_dir, payload)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
