#!/usr/bin/env python3
"""Merge per-tile eco samples into sample.npz for clustering.

Example:
  python scripts/10_merge_eco_samples.py --eco-id 6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io import merge_eco_tile_samples, save_eco_merged_sample
from src.utils import eco_merged_dir, inventory_dir, load_configs, resolve_results_dir


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merge per-tile eco samples")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--eco-config", default=None)
    p.add_argument("--eco-id", type=int, required=True)
    p.add_argument("--year", type=int, default=None)
    p.add_argument("--n-pixels", type=int, default=None)
    p.add_argument(
        "--balance",
        choices=["equal_per_tile", "area_proportional"],
        default=None,
    )
    p.add_argument("--tiles-dir", default=None)
    p.add_argument("--out-dir", default=None)
    p.add_argument(
        "--tiles-list",
        default=None,
        help="If set, require one partial sample per tile in the list",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_configs(ROOT / args.config, args.eco_config)
    sampling = cfg.get("sampling", {})
    year = args.year or int(cfg["project"].get("mosaic_year") or 2015)
    n_pixels = args.n_pixels or int(sampling.get("n_pixels_eco", 100_000))
    balance = args.balance or sampling.get("balance", "equal_per_tile")
    random_state = int(sampling.get("random_state", 42))

    results_dir = resolve_results_dir(cfg, ROOT)
    eco_dir = Path(args.out_dir or eco_merged_dir(results_dir, args.eco_id, year))
    tiles_dir = Path(args.tiles_dir or eco_dir / "tiles")

    if args.tiles_list:
        expected = [
            ln.strip()
            for ln in Path(args.tiles_list).read_text().splitlines()
            if ln.strip()
        ]
        missing = [
            t for t in expected if not (tiles_dir / f"{t}.json").is_file()
        ]
        if missing:
            print(f"Missing tile samples: {missing}", file=sys.stderr)
            return 1

    print(
        json.dumps(
            {
                "eco_id": args.eco_id,
                "year": year,
                "tiles_dir": str(tiles_dir),
                "n_pixels": n_pixels,
                "balance": balance,
            }
        )
    )

    payload = merge_eco_tile_samples(
        tiles_dir=tiles_dir,
        n_pixels=n_pixels,
        balance=balance,
        random_state=random_state,
        eco_id=args.eco_id,
        year=year,
    )
    meta = save_eco_merged_sample(eco_dir, payload)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
