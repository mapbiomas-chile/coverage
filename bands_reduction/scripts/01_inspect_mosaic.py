#!/usr/bin/env python3
"""Inspect a 184-band mosaic tile (F0 helper)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.mosaic import find_mosaic_tile, mosaic_profile, read_band_names
from src.utils.config import load_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/global.yaml")
    parser.add_argument("--tile", required=True, help="MGRS tile id, e.g. 19KCQ")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None, help="Optional JSON output path")
    args = parser.parse_args()

    cfg = load_yaml(ROOT / args.config if not Path(args.config).is_absolute() else args.config)
    year = args.year or int(cfg.get("project", {}).get("year", 2015))
    mosaic_dir = cfg["paths"]["mosaic"]
    mosaic_path = find_mosaic_tile(mosaic_dir, args.tile, year)
    profile = mosaic_profile(mosaic_path)
    names = read_band_names(mosaic_path)
    report = {
        "tile": args.tile,
        "year": year,
        "mosaic": profile,
        "band_names_head": names[:10],
        "n_bands": len(names),
        "bands_ok": len(names) == int(cfg.get("project", {}).get("n_bands_full", 184)),
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
