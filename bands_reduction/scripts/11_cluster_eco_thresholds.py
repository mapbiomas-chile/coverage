#!/usr/bin/env python3
"""Cluster bands on eco-merged sample at several |r| thresholds.

Example:
  python scripts/11_cluster_eco_thresholds.py --eco-id 2
  # → results/E2/2015/eco_merged/{0.95,0.90,0.85}/
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

from src.evaluation.correlation import abs_corrcoef
from src.selection import cluster_bands_from_corr_abs, save_band_clusters
from src.utils import (
    corr_threshold_dirname,
    eco_merged_dir,
    load_configs,
    resolve_results_dir,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eco-level band clustering (multi threshold)")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--eco-id", type=int, default=2)
    p.add_argument("--year", type=int, default=None)
    p.add_argument("--corr-thresholds", default=None)
    p.add_argument(
        "--sample-dir",
        default=None,
        help="Dir with sample.npz + sample_meta.json (default: eco_merged/)",
    )
    p.add_argument("--out-root", default=None)
    p.add_argument("--save-corr", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_configs(ROOT / args.config)
    clustering = cfg.get("clustering", {})
    year = args.year or int(cfg["project"].get("mosaic_year") or 2015)
    results_dir = resolve_results_dir(cfg, ROOT)
    sample_dir = Path(args.sample_dir or eco_merged_dir(results_dir, args.eco_id, year))
    out_root = Path(args.out_root or sample_dir)

    npz_path = sample_dir / "sample.npz"
    meta_path = sample_dir / "sample_meta.json"
    if not npz_path.is_file() or not meta_path.is_file():
        print(
            f"Sample not found under {sample_dir}\n"
            f"Run: python scripts/10_sample_eco_merged.py --eco-id {args.eco_id}",
            file=sys.stderr,
        )
        return 1

    meta = json.loads(meta_path.read_text())
    X = np.load(npz_path)["X"]
    band_names = meta.get("band_names") or [f"band_{i}" for i in range(X.shape[1])]
    linkage = clustering.get("linkage", "average")

    if args.corr_thresholds:
        corr_thrs = [float(x.strip()) for x in args.corr_thresholds.split(",") if x.strip()]
    else:
        corr_thrs = [float(x) for x in clustering.get("corr_thresholds", [0.95, 0.90, 0.85])]

    corr = abs_corrcoef(X)
    if args.save_corr:
        np.save(out_root / "corr_abs.npy", corr)

    briefs = []
    for thr in corr_thrs:
        d_cut = 1.0 - thr
        result = cluster_bands_from_corr_abs(
            corr,
            distance_threshold=d_cut,
            linkage_method=linkage,
        )
        result["assignment"]["band_name"] = result["assignment"]["band_index"].map(
            {i: band_names[i] for i in range(len(band_names))}
        )
        thr_dir = out_root / corr_threshold_dirname(thr)
        summary = save_band_clusters(
            result,
            thr_dir,
            extra_meta={
                "eco_id": args.eco_id,
                "year": year,
                "corr_threshold": thr,
                "n_finite_samples": int(X.shape[0]),
                "sample_dir": str(sample_dir),
                "method": "eco_merged_correlation_cluster",
            },
        )
        # also save labels path already done; keep corr for reps step
        np.save(thr_dir / "corr_abs.npy", corr)
        brief = {
            "corr_threshold": thr,
            "n_clusters": summary["n_clusters"],
            "n_singletons": summary["n_singletons"],
            "n_multi": summary["n_multi"],
            "out_dir": str(thr_dir),
            "status": "PASS",
        }
        briefs.append(brief)
        print(json.dumps(brief))

    master = {
        "eco_id": args.eco_id,
        "year": year,
        "n_finite": int(X.shape[0]),
        "n_bands": int(X.shape[1]),
        "linkage": linkage,
        "thresholds": briefs,
        "sample_dir": str(sample_dir),
    }
    (out_root / "cluster_all_thresholds.json").write_text(
        json.dumps(master, indent=2) + "\n"
    )
    print(f"wrote {out_root / 'cluster_all_thresholds.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
