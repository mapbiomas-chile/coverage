#!/usr/bin/env python3
"""F1: unsupervised spectral EDA (absolute correlation) on a pixel sample.

Example:
  python scripts/03_spectral_eda.py \\
    --npz /home/lserey/mapbiomas_land/tmp/bands_reduction_pe/samples/E2_19KCQ_2015_n50000.npz
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

from src.evaluation import run_correlation_eda
from src.utils import load_yaml


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="F1 spectral EDA (|r| between bands)")
    p.add_argument(
        "--npz",
        default=None,
        help="Pixel sample .npz with array X (default: E2 pilot under results_dir)",
    )
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument(
        "--out-dir",
        default=None,
        help="Default: {results_dir}/eda/{stem}",
    )
    p.add_argument(
        "--pair-threshold",
        type=float,
        default=0.9,
        help="Export pairs with |r| >= this value",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    results_dir = Path(cfg["paths"]["results_dir"])

    npz_path = Path(
        args.npz
        or results_dir / "samples" / "E2_19KCQ_2015_n50000.npz"
    )
    if not npz_path.is_file():
        print(f"Sample not found: {npz_path}", file=sys.stderr)
        return 1

    data = np.load(npz_path)
    X = data["X"]
    stem = npz_path.stem  # e.g. E2_19KCQ_2015_n50000
    out_dir = Path(args.out_dir) if args.out_dir else results_dir / "eda" / stem

    meta_path = npz_path.with_name(npz_path.name.replace(".npz", ".meta.json"))
    extra = {"npz_path": str(npz_path)}
    if meta_path.is_file():
        extra["sample_meta"] = json.loads(meta_path.read_text())

    summary = run_correlation_eda(
        X,
        out_dir,
        label=stem,
        pair_threshold=args.pair_threshold,
        extra_meta=extra,
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
