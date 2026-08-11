#!/usr/bin/env python3
"""Confusion matrices for Col2 val hold-out QA (PNG + CSV for informe)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.qa import build_pilot_band_sets, load_col2_eco, save_holdout_confusion
from src.utils.config import load_yaml, resolve_results_dir

DEFAULT_TRAIN_NPZ = "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_JM/samples/chile_train_184.npz"
DEFAULT_TRAIN_INDEX = "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_JM/samples/chile_train_184_index.csv"
DEFAULT_VAL_NPZ = ROOT / "results" / "QA" / "samples" / "chile_val_184.npz"
DEFAULT_VAL_INDEX = ROOT / "results" / "QA" / "samples" / "chile_val_184_index.csv"
DEFAULT_FIGURES = ROOT / "docs" / "figures"

# baseline + best reduction per eco (from val QA summary)
DEFAULT_LISTS_BY_ECO: dict[int, list[str]] = {
    2: ["baseline_184", "jm_topN"],
    3: ["baseline_184", "boruta_topN"],
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Col2 val confusion matrices for band lists")
    p.add_argument("--eco-id", type=int, action="append", default=None)
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--train-npz", default=DEFAULT_TRAIN_NPZ)
    p.add_argument("--train-index", default=DEFAULT_TRAIN_INDEX)
    p.add_argument("--val-npz", default=str(DEFAULT_VAL_NPZ))
    p.add_argument("--val-index", default=str(DEFAULT_VAL_INDEX))
    p.add_argument("--figures-dir", default=str(DEFAULT_FIGURES))
    p.add_argument("--list-name", action="append", default=None, help="Override band list keys")
    p.add_argument("--exclude-classes", type=int, nargs="*", default=[33, 34])
    p.add_argument("--n-estimators", type=int, default=None)
    p.add_argument("--n-jobs", type=int, default=4)
    p.add_argument("--random-state", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    qa_cfg = cfg.get("qa") or {}
    n_estimators = args.n_estimators or int(qa_cfg.get("n_estimators", 200))
    exclude = tuple(args.exclude_classes)
    eco_ids = args.eco_id or [2, 3]
    figures_dir = Path(args.figures_dir)

    results_dir = resolve_results_dir(cfg, ROOT)

    for eco_id in eco_ids:
        list_names = args.list_name or DEFAULT_LISTS_BY_ECO.get(eco_id, ["baseline_184"])
        X_tr, y_tr = load_col2_eco(args.train_npz, args.train_index, eco_id, exclude_classes=exclude)
        X_va, y_va = load_col2_eco(args.val_npz, args.val_index, eco_id, exclude_classes=exclude)
        band_sets = build_pilot_band_sets(results_dir, eco_id)

        print(f"=== Confusion matrices E{eco_id} (train {X_tr.shape[0]} → val {X_va.shape[0]}) ===")
        for list_name in list_names:
            if list_name not in band_sets:
                raise KeyError(f"Unknown list {list_name!r} for eco {eco_id}")
            stem = figures_dir / f"E{eco_id:02d}_col2_val_cm_{list_name}"
            meta = save_holdout_confusion(
                X_tr,
                y_tr,
                X_va,
                y_va,
                band_sets[list_name],
                stem,
                list_name=list_name,
                eco_id=eco_id,
                n_estimators=n_estimators,
                n_jobs=args.n_jobs,
                random_state=args.random_state,
            )
            print(
                f"  {list_name:20s} OA={meta['oa']:.4f}  K={meta['kappa']:.4f}  "
                f"→ {stem.with_suffix('.png').name}"
            )


if __name__ == "__main__":
    main()
