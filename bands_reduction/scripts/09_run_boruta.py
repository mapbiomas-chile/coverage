#!/usr/bin/env python3
"""Run Boruta band confirmation (pipeline stage 3).

Consumes the same contract as JM:
  --samples  NPZ with X,y (Chile train matrix)
  --band-list JSON (full 184, clustering reps, or JM-filtered list)

Writes confirmed / tentative / rejected tables and a band_list of confirmed
(+ optional tentative) for the next consolidation step.

Does not require the PyPI `boruta` package (self-contained RF + shadows).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.band_list import band_list_from_indices, load_band_list, save_band_list
from src.io.samples import load_samples, select_bands
from src.selection.boruta_select import run_boruta
from src.utils.config import load_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/global.yaml")
    parser.add_argument(
        "--samples",
        type=Path,
        required=True,
        help="Labeled NPZ with keys X, y (rows/cols optional)",
    )
    parser.add_argument(
        "--band-list",
        type=Path,
        required=True,
        help="Candidate bands JSON (usually JM or clustering output)",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-iter", type=int, default=None)
    parser.add_argument("--n-estimators", type=int, default=None)
    parser.add_argument("--perc", type=float, default=None, help="Shadow percentile (100=max)")
    parser.add_argument("--alpha", type=float, default=None)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-jobs", type=int, default=4, help="RF parallel jobs (keep modest)")
    parser.add_argument(
        "--include-tentative",
        action="store_true",
        help="Also keep tentative bands in band_list_boruta.json",
    )
    args = parser.parse_args()

    cfg_path = Path(args.config)
    cfg = load_yaml(ROOT / cfg_path if not cfg_path.is_absolute() else cfg_path)
    boruta_cfg = cfg.get("boruta", {}) if isinstance(cfg.get("boruta"), dict) else {}

    max_iter = args.max_iter if args.max_iter is not None else int(boruta_cfg.get("max_iter", 50))
    n_estimators = (
        args.n_estimators
        if args.n_estimators is not None
        else int(boruta_cfg.get("n_estimators", 200))
    )
    perc = args.perc if args.perc is not None else float(boruta_cfg.get("perc", 100.0))
    alpha = args.alpha if args.alpha is not None else float(boruta_cfg.get("alpha", 0.05))

    band_list = load_band_list(args.band_list)
    bands = band_list["bands"]
    band_names = band_list.get("band_names")

    data = load_samples(args.samples)
    if "y" not in data:
        raise SystemExit(f"{args.samples} has no 'y'")
    X_full, y = data["X"], data["y"]
    valid = y >= 0
    X_full, y = X_full[valid], y[valid]
    X = select_bands(X_full, bands)

    print(
        f"Boruta: n={X.shape[0]} samples, n_bands={X.shape[1]}, "
        f"source={band_list.get('source')}, max_iter={max_iter}, n_jobs={args.n_jobs}"
    )
    result = run_boruta(
        X,
        y,
        band_indices=bands,
        band_names=band_names,
        n_estimators=n_estimators,
        max_iter=max_iter,
        perc=perc,
        alpha=alpha,
        random_state=args.random_state,
        n_jobs=args.n_jobs,
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    table_path = args.out_dir / "boruta_decisions.csv"
    with table_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "band_index",
                "band_name",
                "decision",
                "n_hits",
                "n_iters",
                "hit_rate",
                "mean_importance",
                "mean_shadow_max",
            ],
        )
        writer.writeheader()
        for b in result.band_results:
            writer.writerow(
                {
                    "band_index": b.band_index,
                    "band_name": b.band_name or "",
                    "decision": b.decision,
                    "n_hits": b.n_hits,
                    "n_iters": b.n_iters,
                    "hit_rate": f"{b.hit_rate:.6f}",
                    "mean_importance": f"{b.mean_importance:.8f}",
                    "mean_shadow_max": f"{b.mean_shadow_max:.8f}",
                }
            )

    keep = result.confirmed
    if args.include_tentative:
        keep = result.confirmed + result.tentative

    keep_bands = [b.band_index for b in keep]
    keep_names = [b.band_name for b in keep if b.band_name is not None]
    if len(keep_names) != len(keep_bands):
        keep_names = None

    out_bl = band_list_from_indices(
        keep_bands,
        source="boruta",
        ecoregion=band_list.get("ecoregion"),
        tile=band_list.get("tile"),
        year=band_list.get("year"),
        band_names=keep_names,
    )
    out_bl["parent_source"] = band_list.get("source")
    out_bl["parent_n_bands"] = len(bands)
    out_bl["include_tentative"] = bool(args.include_tentative)
    out_bl["boruta"] = {
        "n_iters": result.n_iters,
        "perc": result.perc,
        "alpha": result.alpha,
        "n_estimators": result.n_estimators,
        "random_state": result.random_state,
        "n_confirmed": len(result.confirmed),
        "n_tentative": len(result.tentative),
        "n_rejected": len(result.rejected),
    }
    bl_path = save_band_list(args.out_dir / "band_list_boruta.json", out_bl)

    summary = {
        "n_samples": int(X.shape[0]),
        "n_input_bands": len(bands),
        "input_source": band_list.get("source"),
        "n_confirmed": len(result.confirmed),
        "n_tentative": len(result.tentative),
        "n_rejected": len(result.rejected),
        "n_iters": result.n_iters,
        "params": {
            "max_iter": max_iter,
            "n_estimators": n_estimators,
            "perc": perc,
            "alpha": alpha,
            "n_jobs": args.n_jobs,
            "random_state": args.random_state,
            "include_tentative": bool(args.include_tentative),
        },
        "confirmed_top": [
            {
                "band_index": b.band_index,
                "band_name": b.band_name,
                "hit_rate": b.hit_rate,
                "mean_importance": b.mean_importance,
            }
            for b in result.confirmed[:15]
        ],
        "decisions_csv": str(table_path),
        "band_list_boruta": str(bl_path),
        "note": (
            "Boruta verifies relevance vs shadow features; use after JM/clustering. "
            "Does not train the final LULC map model."
        ),
    }
    summary_path = args.out_dir / "boruta_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {table_path}")
    print(f"Wrote {bl_path}")


if __name__ == "__main__":
    main()
