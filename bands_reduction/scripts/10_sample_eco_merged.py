#!/usr/bin/env python3
"""Sample ~N pixels inside an ecoregion across all inventory tiles (merged pool).

Example:
  python scripts/10_sample_eco_merged.py --eco-id 2
  # → results/E2/2015/eco_merged/sample.npz
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io import sample_ecoregion_merged, save_eco_merged_sample
from src.utils import (
    eco_merged_dir,
    inventory_dir,
    load_configs,
    resolve_results_dir,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merged eco pixel sample across tiles")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--eco-config", default=None, help="Optional ecoregion yaml")
    p.add_argument("--eco-id", type=int, default=2)
    p.add_argument("--year", type=int, default=None)
    p.add_argument("--n-pixels", type=int, default=None)
    p.add_argument(
        "--balance",
        choices=["equal_per_tile", "area_proportional"],
        default=None,
    )
    p.add_argument(
        "--tiles-list",
        default=None,
        help="Default: results/E{eco}/{year}/01_inventory/tiles.txt",
    )
    p.add_argument("--out-dir", default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_configs(ROOT / args.config, args.eco_config)
    paths = cfg["paths"]
    sampling = cfg.get("sampling", {})
    year = args.year or int(cfg["project"].get("mosaic_year") or 2015)
    n_pixels = args.n_pixels or int(sampling.get("n_pixels_eco", 100_000))
    balance = args.balance or sampling.get("balance", "equal_per_tile")
    random_state = int(sampling.get("random_state", 42))

    results_dir = resolve_results_dir(cfg, ROOT)
    inv = inventory_dir(results_dir, args.eco_id, year)
    tiles_list = Path(args.tiles_list or inv / "tiles.txt")
    if not tiles_list.is_file():
        print(
            f"Tile list not found: {tiles_list}\n"
            f"Run: python scripts/06_inventory_eco_tiles.py --eco-id {args.eco_id}",
            file=sys.stderr,
        )
        return 1
    tiles = [ln.strip() for ln in tiles_list.read_text().splitlines() if ln.strip()]
    if not tiles:
        print("Empty tile list", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir or eco_merged_dir(results_dir, args.eco_id, year))

    print(
        json.dumps(
            {
                "eco_id": args.eco_id,
                "year": year,
                "n_tiles": len(tiles),
                "n_pixels": n_pixels,
                "balance": balance,
            }
        )
    )

    payload = sample_ecoregion_merged(
        tiles=tiles,
        mosaics_dir=paths["mosaics_dir"],
        mosaic_filename_template=paths.get(
            "mosaic_filename_template",
            "TMP-CHILE-{tile}-{year}-SBAND-184B.tif",
        ),
        ecoregions_path=paths["ecoregions"],
        eco_id=args.eco_id,
        year=year,
        n_pixels=n_pixels,
        balance=balance,
        random_state=random_state,
    )
    meta = save_eco_merged_sample(out_dir, payload)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
