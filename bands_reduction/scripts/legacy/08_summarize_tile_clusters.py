#!/usr/bin/env python3
"""Collect per-tile threshold summaries into one CSV.

Default root: results/E2/2015/02_clusters_by_tile/tiles
Default out:  results/E2/2015/02_clusters_by_tile/summary_n_clusters.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.utils import clusters_by_tile_dir, load_yaml, resolve_results_dir


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--eco-id", type=int, default=2)
    p.add_argument("--year", type=int, default=None)
    p.add_argument(
        "--root",
        default=None,
        help="Folder with per-tile subdirs (default: .../02_clusters_by_tile/tiles)",
    )
    p.add_argument(
        "--out",
        default=None,
        help="Output CSV (default: .../02_clusters_by_tile/summary_n_clusters.csv)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    year = args.year or int(cfg["project"].get("mosaic_year") or cfg["project"].get("year"))
    results_dir = resolve_results_dir(cfg, ROOT)
    stage = clusters_by_tile_dir(results_dir, args.eco_id, year)
    root = Path(args.root or stage / "tiles")
    out = Path(args.out or stage / "summary_n_clusters.csv")

    rows = []
    for meta in sorted(root.glob("*/thresholds_summary.json")):
        data = json.loads(meta.read_text())
        tile = data.get("tile", meta.parent.name)
        for t in data.get("thresholds", []):
            rows.append(
                {
                    "tile": tile,
                    "status": data.get("status"),
                    "n_finite": data.get("n_finite"),
                    **t,
                }
            )
    if not rows:
        print(f"No summaries under {root}", file=sys.stderr)
        return 1
    df = pd.DataFrame(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(df.groupby("corr_threshold")["n_clusters"].describe().to_string())
    print(f"wrote {out} rows={len(df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
