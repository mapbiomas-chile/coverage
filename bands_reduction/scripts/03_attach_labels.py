#!/usr/bin/env python3
"""Attach LULC labels (y) to an existing sample NPZ using mosaic rows/cols."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.labels import attach_labels_from_raster
from src.io.mosaic import find_mosaic_tile
from src.io.samples import load_meta, load_samples, save_samples
from src.utils.config import load_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/global.yaml")
    parser.add_argument(
        "--samples",
        type=Path,
        default=None,
        help="Input NPZ (default: paths.samples_file from config)",
    )
    parser.add_argument("--tile", default="19KCQ")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output NPZ with y (write outside git, e.g. /tmp or shared tmp)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Optional subsample for smoke tests",
    )
    args = parser.parse_args()

    cfg_path = Path(args.config)
    cfg = load_yaml(ROOT / cfg_path if not cfg_path.is_absolute() else cfg_path)
    year = args.year or int(cfg.get("project", {}).get("year", 2015))
    samples_path = args.samples or Path(cfg["paths"]["samples_file"])
    labels_path = Path(cfg["paths"]["labels"])
    mosaic_path = find_mosaic_tile(cfg["paths"]["mosaic"], args.tile, year)

    data = load_samples(samples_path)
    meta: dict = {}
    meta_path = samples_path.with_suffix(".meta.json")
    if meta_path.is_file():
        meta = load_meta(meta_path)

    X, rows, cols = data["X"], data["rows"], data["cols"]
    if args.max_samples is not None and args.max_samples < X.shape[0]:
        rng = np.random.default_rng(42)
        idx = rng.choice(X.shape[0], size=args.max_samples, replace=False)
        idx.sort()
        X, rows, cols = X[idx], rows[idx], cols[idx]

    print(f"Attaching labels for n={X.shape[0]} from {labels_path} …")
    y = attach_labels_from_raster(
        mosaic_path=mosaic_path,
        labels_path=labels_path,
        rows=rows,
        cols=cols,
    )
    n_valid = int((y >= 0).sum())
    classes, counts = np.unique(y[y >= 0], return_counts=True)
    print(f"Labeled {n_valid}/{y.size} pixels; n_classes={classes.size}")
    print("class counts:", dict(zip(classes.tolist(), counts.tolist())))

    meta_out = {
        **meta,
        "tile": args.tile,
        "year": year,
        "mosaic_path": str(mosaic_path),
        "labels_path": str(labels_path),
        "source_samples": str(samples_path),
        "n_valid_labels": n_valid,
        "class_counts": {str(int(c)): int(n) for c, n in zip(classes, counts)},
    }
    out = save_samples(args.out, X=X, rows=rows, cols=cols, y=y, meta=meta_out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
