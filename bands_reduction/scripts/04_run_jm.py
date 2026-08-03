#!/usr/bin/env python3
"""Run Jeffries-Matusita band ranking (stage 3) on labeled samples + band-list.

Same CLI contract for:
  - full 184 bands (--band-list from 02_export_band_list.py --source full)
  - clustering output (--band-list from representatives / waludi_bandclust)
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
from src.selection.jm import filter_bands_by_jm, rank_bands_by_jm
from src.utils.config import load_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/global.yaml")
    parser.add_argument(
        "--samples",
        type=Path,
        required=True,
        help="Labeled NPZ with keys X, rows, cols, y",
    )
    parser.add_argument(
        "--band-list",
        type=Path,
        required=True,
        help="JSON band-list (indices into the original 184-band mosaic)",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--min-mean-jm", type=float, default=None)
    parser.add_argument("--min-count", type=int, default=20)
    args = parser.parse_args()

    cfg_path = Path(args.config)
    _ = load_yaml(ROOT / cfg_path if not cfg_path.is_absolute() else cfg_path)

    band_list = load_band_list(args.band_list)
    bands = band_list["bands"]
    band_names = band_list.get("band_names")

    data = load_samples(args.samples)
    if "y" not in data:
        raise SystemExit(
            f"{args.samples} has no 'y'. Run scripts/03_attach_labels.py first."
        )

    X_full, y = data["X"], data["y"]
    valid = y >= 0
    X_full = X_full[valid]
    y = y[valid]
    X = select_bands(X_full, bands)

    print(
        f"JM ranking: n={X.shape[0]} samples, n_bands={X.shape[1]}, "
        f"source={band_list.get('source')}"
    )
    scores = rank_bands_by_jm(
        X,
        y,
        band_indices=bands,
        band_names=band_names,
        min_count=args.min_count,
    )
    selected = filter_bands_by_jm(
        scores, top_k=args.top_k, min_mean_jm=args.min_mean_jm
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    ranking_csv = args.out_dir / "jm_ranking.csv"
    with ranking_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rank",
                "band_index",
                "band_name",
                "mean_jm",
                "min_jm",
                "n_pairs",
                "n_classes_used",
            ],
        )
        writer.writeheader()
        for i, s in enumerate(scores, start=1):
            writer.writerow(
                {
                    "rank": i,
                    "band_index": s.band_index,
                    "band_name": s.band_name or "",
                    "mean_jm": f"{s.mean_jm:.6f}",
                    "min_jm": f"{s.min_jm:.6f}",
                    "n_pairs": s.n_pairs,
                    "n_classes_used": s.n_classes_used,
                }
            )

    selected_bands = [s.band_index for s in selected]
    selected_names = [s.band_name for s in selected if s.band_name is not None]
    if len(selected_names) != len(selected_bands):
        selected_names = None

    out_band_list = band_list_from_indices(
        selected_bands,
        source="jm_refine",
        ecoregion=band_list.get("ecoregion"),
        tile=band_list.get("tile"),
        year=band_list.get("year"),
        band_names=selected_names,
    )
    out_band_list["parent_source"] = band_list.get("source")
    out_band_list["parent_n_bands"] = len(bands)
    out_band_list["filters"] = {
        "top_k": args.top_k,
        "min_mean_jm": args.min_mean_jm,
        "min_count": args.min_count,
    }
    band_list_path = save_band_list(args.out_dir / "band_list_jm.json", out_band_list)

    summary = {
        "n_samples": int(X.shape[0]),
        "n_input_bands": len(bands),
        "n_selected_bands": len(selected_bands),
        "input_source": band_list.get("source"),
        "top5": [
            {
                "band_index": s.band_index,
                "band_name": s.band_name,
                "mean_jm": s.mean_jm,
            }
            for s in scores[:5]
        ],
        "class_counts": {
            str(int(c)): int(n)
            for c, n in zip(*np.unique(y, return_counts=True))
        },
        "ranking_csv": str(ranking_csv),
        "band_list_jm": str(band_list_path),
    }
    summary_path = args.out_dir / "jm_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {ranking_csv}")
    print(f"Wrote {band_list_path}")


if __name__ == "__main__":
    main()
