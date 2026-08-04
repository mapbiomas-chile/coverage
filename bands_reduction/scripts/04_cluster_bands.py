#!/usr/bin/env python3
"""F2 step 1: cluster bands from |r| matrix (no representatives yet).

Example:
  python scripts/04_cluster_bands.py \\
    --corr-abs .../eda/E2_19KCQ_2015_n50000/corr_abs.npy \\
    --distance-threshold 0.10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from src.selection import cluster_bands_from_corr_abs, save_band_clusters
from src.utils import load_yaml


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="F2: hierarchical band clustering only")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument(
        "--corr-abs",
        default=None,
        help="Path to corr_abs.npy (default: E2 EDA under results_dir)",
    )
    p.add_argument(
        "--distance-threshold",
        type=float,
        default=0.10,
        help="Cut distance d=1-|r| (default 0.10 => |r|>=0.90)",
    )
    p.add_argument("--linkage", default="average")
    p.add_argument(
        "--out-dir",
        default=None,
        help="Default: {results_dir}/clusters/{eda_stem}_d{thr}",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    results_dir = Path(cfg["paths"]["results_dir"])

    corr_path = Path(
        args.corr_abs
        or results_dir / "eda" / "E2_19KCQ_2015_n50000" / "corr_abs.npy"
    )
    if not corr_path.is_file():
        print(f"corr_abs not found: {corr_path}", file=sys.stderr)
        return 1

    corr = np.load(corr_path)
    result = cluster_bands_from_corr_abs(
        corr,
        distance_threshold=args.distance_threshold,
        linkage_method=args.linkage,
    )

    stem = corr_path.parent.name  # e.g. E2_19KCQ_2015_n50000
    thr_tag = f"d{args.distance_threshold:.2f}".replace(".", "p")
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else results_dir / "clusters" / f"{stem}_{thr_tag}"
    )

    summary = save_band_clusters(
        result,
        out_dir,
        extra_meta={
            "corr_abs": str(corr_path),
            "eda_dir": str(corr_path.parent),
        },
    )
    # preview largest multi-member clusters
    multi = [c for c in json.loads(Path(summary["clusters_json"]).read_text()) if c["size"] > 1]
    summary["preview_largest_multi"] = multi[:10]
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
