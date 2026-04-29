#!/usr/bin/env python3
"""
Run modular mosaic pipeline:
1) Validate GPKG vs tile overlap
2) Execute mosaic script only when overlap is True

Default usage (from mosaico_reduce directory):
    python run_pipeline.py
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from check_gpkg_tile_overlap import check_overlap


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate overlap and run mapbiomas mosaic script."
    )
    parser.add_argument(
        "--gpkg",
        default="../../inputs/gpk/Muestra_Lagogpk.gpkg",
        help="Path to input GPKG (default: ../../inputs/gpk/Muestra_Lagogpk.gpkg)",
    )
    parser.add_argument(
        "--tile",
        default="SJ-18-X-B",
        help="CIM tile name to validate (default: SJ-18-X-B)",
    )
    parser.add_argument(
        "--project",
        default="mapbiomas-chile",
        help="Earth Engine project ID (default: mapbiomas-chile)",
    )
    parser.add_argument(
        "--mosaic-script",
        default="mapbiomas_Chile_mosaics_landsat_v1.py",
        help="Mosaic script path (default: mapbiomas_Chile_mosaics_landsat_v1.py)",
    )
    parser.add_argument(
        "--reduced",
        default="1",
        choices=("0", "1"),
        help="MOSAIC_REDUCED_MODE for the mosaic script: 1=reduced NDVI/NDWI, 0=full pipeline (default: 1)",
    )
    parser.add_argument(
        "--export-tag",
        default="",
        help="Optional tag appended to export suffix to keep GEE asset names unique (sets MOSAIC_EXPORT_TAG)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="If set, only first N JSON rows per territory (sets MOSAIC_MAX_JOBS, for smoke tests)",
    )
    parser.add_argument(
        "--skip-task-guard",
        action="store_true",
        help="Skip slow ee.batch.Task.list() in mosaic script (sets MOSAIC_SKIP_ACTIVE_TASK_GUARD=1)",
    )
    args = parser.parse_args()

    result = check_overlap(Path(args.gpkg), args.tile, args.project)
    print(f"[check] gpkg_path: {result['gpkg_path']}")
    print(f"[check] tile_name: {result['tile_name']}")
    print(f"[check] intersects_bbox: {result['intersects_bbox']}")

    if not result["intersects_bbox"]:
        print("[stop] No intersection. Mosaic process aborted.")
        sys.exit(2)

    script_path = Path(args.mosaic_script)
    if not script_path.exists():
        raise FileNotFoundError(f"Mosaic script not found: {script_path}")

    env = os.environ.copy()
    env["MOSAIC_REDUCED_MODE"] = args.reduced
    env["PYTHONUNBUFFERED"] = "1"
    if args.export_tag.strip():
        env["MOSAIC_EXPORT_TAG"] = args.export_tag.strip()
    if args.max_jobs is not None and args.max_jobs > 0:
        env["MOSAIC_MAX_JOBS"] = str(args.max_jobs)
    if args.skip_task_guard:
        env["MOSAIC_SKIP_ACTIVE_TASK_GUARD"] = "1"

    print(f"[run] Executing: {script_path}  (MOSAIC_REDUCED_MODE={args.reduced})")
    if args.export_tag.strip():
        print(f"[run] MOSAIC_EXPORT_TAG={args.export_tag.strip()!r}")
    if args.max_jobs is not None:
        print(f"[run] MOSAIC_MAX_JOBS={args.max_jobs}")
    if args.skip_task_guard:
        print("[run] MOSAIC_SKIP_ACTIVE_TASK_GUARD=1")
    completed = subprocess.run(
        [sys.executable, "-u", str(script_path)], env=env, check=False
    )
    sys.exit(completed.returncode)


if __name__ == "__main__":
    main()
