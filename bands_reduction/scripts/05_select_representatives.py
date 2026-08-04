#!/usr/bin/env python3
"""F2 step 2: one representative band per cluster (central |r|).

Example:
  python scripts/05_select_representatives.py \\
    --cluster-dir .../clusters/E2_19KCQ_2015_n50000_d0p10
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

from src.selection.representatives import (
    save_representatives,
    select_central_representatives,
)
from src.utils import load_yaml


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="F2: select cluster representatives")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument(
        "--cluster-dir",
        default=None,
        help="Dir with band_cluster_labels.npy + cluster_summary.json",
    )
    p.add_argument(
        "--corr-abs",
        default=None,
        help="Override corr_abs.npy (default: from cluster_summary source)",
    )
    p.add_argument(
        "--out-dir",
        default=None,
        help="Default: {cluster-dir}/representatives",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    results_dir = Path(cfg["paths"]["results_dir"])

    cluster_dir = Path(
        args.cluster_dir
        or results_dir / "clusters" / "E2_19KCQ_2015_n50000_d0p10"
    )
    summary_path = cluster_dir / "cluster_summary.json"
    labels_path = cluster_dir / "band_cluster_labels.npy"
    if not labels_path.is_file():
        print(f"labels not found: {labels_path}", file=sys.stderr)
        return 1

    cluster_summary = {}
    if summary_path.is_file():
        cluster_summary = json.loads(summary_path.read_text())

    corr_path = Path(
        args.corr_abs
        or cluster_summary.get("source", {}).get("corr_abs")
        or results_dir / "eda" / "E2_19KCQ_2015_n50000" / "corr_abs.npy"
    )
    if not corr_path.is_file():
        print(f"corr_abs not found: {corr_path}", file=sys.stderr)
        return 1

    corr = np.load(corr_path)
    labels = np.load(labels_path)
    reps = select_central_representatives(corr, labels)

    out_dir = Path(args.out_dir) if args.out_dir else cluster_dir / "representatives"
    summary = save_representatives(
        reps,
        out_dir,
        extra_meta={
            "cluster_dir": str(cluster_dir),
            "corr_abs": str(corr_path),
            "distance_threshold": cluster_summary.get("distance_threshold"),
        },
    )
    # preview a few multi-member picks
    multi = [r for r in reps.to_dict(orient="records") if r["size"] > 1][:5]
    summary["preview_multi"] = [
        {
            "cluster_id": m["cluster_id"],
            "size": m["size"],
            "representative": m["representative"],
            "mean_abs_r_to_others": m["mean_abs_r_to_others"],
            "members": m["members"],
        }
        for m in multi
    ]
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
