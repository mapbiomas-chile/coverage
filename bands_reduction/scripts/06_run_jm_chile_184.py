#!/usr/bin/env python3
"""Run JM ranking on Chile-wide train matrix (184 bands). No model training."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_JM"),
    )
    parser.add_argument(
        "--out-subdir",
        type=str,
        default="jm_chile_184",
        help="Subfolder under base-dir/results/",
    )
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--min-count", type=int, default=20)
    parser.add_argument("--min-mean-jm", type=float, default=None)
    parser.add_argument(
        "--exclude-classes",
        type=int,
        nargs="*",
        default=[33, 34],
        help="Class ids to drop before JM (default: 33 water, 34 ice/snow)",
    )
    args = parser.parse_args()

    samples = args.base_dir / "samples" / "chile_train_184.npz"
    band_list = args.base_dir / "band_lists" / "band_list_full_184.json"
    out_dir = args.base_dir / "results" / args.out_subdir
    if not samples.is_file():
        raise SystemExit(
            f"Missing {samples}. Run scripts/05_build_train_matrix_chile.py first."
        )
    if not band_list.is_file():
        raise SystemExit(f"Missing {band_list}")

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "04_run_jm.py"),
        "--samples",
        str(samples),
        "--band-list",
        str(band_list),
        "--out-dir",
        str(out_dir),
        "--min-count",
        str(args.min_count),
    ]
    if args.top_k is not None:
        cmd.extend(["--top-k", str(args.top_k)])
    if args.min_mean_jm is not None:
        cmd.extend(["--min-mean-jm", str(args.min_mean_jm)])
    if args.exclude_classes is not None:
        cmd.append("--exclude-classes")
        cmd.extend(str(c) for c in args.exclude_classes)
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    main()
