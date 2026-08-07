#!/usr/bin/env python3
"""RF-CV QA: compare band lists vs 184-band baseline for one ecorregión."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.boruta import prepare_eco_matrix
from src.evaluation.qa import build_pilot_band_sets, evaluate_band_sets
from src.utils.config import load_yaml, resolve_results_dir

STRATIFIED_SAMPLES_NPZ = (
    "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_stratified_train "
    "(de boruta final)/samples/chile_train_184_stratified.npz"
)
STRATIFIED_SAMPLES_INDEX = (
    "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_stratified_train "
    "(de boruta final)/samples/chile_train_184_stratified_index.csv"
)
DEFAULT_OUT_ROOT = ROOT / "results" / "QA"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RF-CV QA for band lists vs 184B baseline")
    p.add_argument("--eco-id", type=int, required=True)
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--samples-npz", default=STRATIFIED_SAMPLES_NPZ)
    p.add_argument("--samples-index", default=STRATIFIED_SAMPLES_INDEX)
    p.add_argument("--out-root", default=None)
    p.add_argument("--exclude-classes", type=int, nargs="*", default=[33, 34])
    p.add_argument("--max-samples", type=int, default=None)
    p.add_argument("--n-estimators", type=int, default=None)
    p.add_argument("--n-jobs", type=int, default=8)
    p.add_argument("--random-state", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    qa_cfg = cfg.get("qa") or {}
    n_folds = int(qa_cfg.get("cv_folds", 5))
    n_estimators = args.n_estimators or int(qa_cfg.get("n_estimators", 200))

    results_dir = resolve_results_dir(cfg, ROOT)
    band_sets = build_pilot_band_sets(results_dir, args.eco_id)

    X, y = prepare_eco_matrix(
        args.samples_npz,
        args.samples_index,
        args.eco_id,
        exclude_classes=tuple(args.exclude_classes),
        max_samples=args.max_samples,
        random_state=args.random_state,
    )

    rows = evaluate_band_sets(
        X,
        y,
        band_sets,
        n_folds=n_folds,
        n_estimators=n_estimators,
        n_jobs=args.n_jobs,
        random_state=args.random_state,
    )

    out_root = Path(args.out_root or DEFAULT_OUT_ROOT)
    out_root.mkdir(parents=True, exist_ok=True)
    eco_tag = f"E{args.eco_id:02d}"

    df = pd.DataFrame(rows)
    csv_path = out_root / f"{eco_tag}_qa_compare.csv"
    df.to_csv(csv_path, index=False)

    summary = {
        "eco_id": args.eco_id,
        "n_samples": int(X.shape[0]),
        "n_classes": int(len(set(y.tolist()))),
        "cv_folds": n_folds,
        "n_estimators": n_estimators,
        "max_oa_drop": qa_cfg.get("max_oa_drop", 0.02),
        "max_kappa_drop": qa_cfg.get("max_kappa_drop", 0.02),
        "results": rows,
    }
    json_path = out_root / f"{eco_tag}_qa_summary.json"
    json_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"=== QA E{args.eco_id} ({X.shape[0]} samples, {n_folds}-fold CV) ===")
    for r in rows:
        print(
            f"  {r['list_name']:20s} n={r['n_bands']:3d}  "
            f"OA={r['oa_mean']:.4f}  K={r['kappa_mean']:.4f}  "
            f"dOA={r['delta_oa_vs_184']:+.4f}  dK={r['delta_kappa_vs_184']:+.4f}"
        )
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
