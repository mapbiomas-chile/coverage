#!/usr/bin/env python3
"""QA hold-out: train RF on Col2 train, evaluate on Col2 val."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.qa import build_method_band_sets, evaluate_holdout_band_sets, load_col2_eco
from src.utils.config import load_yaml, resolve_results_dir


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Col2 train→val RF QA for band lists")
    p.add_argument("--eco-id", type=int, required=True)
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--train-npz", default=None)
    p.add_argument("--train-index", default=None)
    p.add_argument("--val-npz", default=None)
    p.add_argument("--val-index", default=None)
    p.add_argument("--out-root", default=None)
    p.add_argument(
        "--corr-threshold",
        default="0.95",
        help="Unsup cluster cut for N reps (JM/Boruta top-N use same N)",
    )
    p.add_argument("--exclude-classes", type=int, nargs="*", default=[33, 34])
    p.add_argument("--n-estimators", type=int, default=None)
    p.add_argument("--n-jobs", type=int, default=8)
    p.add_argument("--random-state", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    qa_cfg = cfg.get("qa") or {}
    n_estimators = args.n_estimators or int(qa_cfg.get("n_estimators", 200))
    exclude = tuple(args.exclude_classes)
    results_dir = resolve_results_dir(cfg, ROOT)

    samples_dir = results_dir / "QA" / "samples"
    train_npz = args.train_npz or str(samples_dir / "chile_train_184.npz")
    train_index = args.train_index or str(samples_dir / "chile_train_184_index.csv")
    val_npz = args.val_npz or str(samples_dir / "chile_val_184.npz")
    val_index = args.val_index or str(samples_dir / "chile_val_184_index.csv")
    out_root = Path(args.out_root or results_dir / "QA" / "col2_val")

    X_tr, y_tr = load_col2_eco(train_npz, train_index, args.eco_id, exclude_classes=exclude)
    X_va, y_va = load_col2_eco(val_npz, val_index, args.eco_id, exclude_classes=exclude)

    band_sets = build_method_band_sets(results_dir, args.eco_id, corr_threshold=args.corr_threshold)

    rows = evaluate_holdout_band_sets(
        X_tr,
        y_tr,
        X_va,
        y_va,
        band_sets,
        n_estimators=n_estimators,
        n_jobs=args.n_jobs,
        random_state=args.random_state,
    )

    out_root.mkdir(parents=True, exist_ok=True)
    eco_tag = f"E{args.eco_id:02d}"

    df = pd.DataFrame(rows)
    csv_path = out_root / f"{eco_tag}_qa_col2_val_compare.csv"
    df.to_csv(csv_path, index=False)

    summary = {
        "eco_id": args.eco_id,
        "protocol": "col2_train_to_val_holdout",
        "n_train": int(X_tr.shape[0]),
        "n_val": int(X_va.shape[0]),
        "n_estimators": n_estimators,
        "corr_threshold": args.corr_threshold,
        "train_npz": train_npz,
        "val_npz": val_npz,
        "exclude_classes": list(args.exclude_classes),
        "results": rows,
    }
    json_path = out_root / f"{eco_tag}_qa_col2_val_summary.json"
    json_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"=== Col2 val QA E{args.eco_id} (train {X_tr.shape[0]} → val {X_va.shape[0]}) ===")
    for r in rows:
        print(
            f"  {r['list_name']:20s} n={r['n_bands']:3d}  "
            f"OA={r['oa_val']:.4f}  K={r['kappa_val']:.4f}  "
            f"dOA={r['delta_oa_vs_184']:+.4f}  dK={r['delta_kappa_vs_184']:+.4f}"
        )
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
