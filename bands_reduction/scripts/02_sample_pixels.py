#!/usr/bin/env python3
"""T6: sample unsupervised pixels inside an ecoregion mask.

Example:
  python scripts/02_sample_pixels.py \\
    --config configs/global.yaml \\
    --ecoregion configs/ecoregions/eco_02_desierto.yaml \\
    --n-pixels 50000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io import (
    read_mosaic_info,
    resolve_mosaic_path,
    sample_pixels_from_mask,
    save_pixel_sample,
    warp_eco_mask_to_mosaic,
)
from src.utils import load_configs


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sample mosaic pixels inside ecoregion (unsupervised T6)"
    )
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument(
        "--ecoregion",
        default="configs/ecoregions/eco_02_desierto.yaml",
    )
    p.add_argument("--tile", default=None)
    p.add_argument("--year", type=int, default=None)
    p.add_argument(
        "--n-pixels",
        type=int,
        default=None,
        help="Override sampling.n_pixels (default from config or 50000)",
    )
    p.add_argument(
        "--random-state",
        type=int,
        default=None,
        help="Override sampling.random_state (default from config or 42)",
    )
    p.add_argument(
        "--out-dir",
        default=None,
        help="Default: {results_dir}/samples",
    )
    return p.parse_args()


def _mosaics_dir(paths: dict) -> str:
    if paths.get("mosaics_dir"):
        return paths["mosaics_dir"]
    if paths.get("mosaic"):
        return paths["mosaic"]
    raise KeyError("paths.mosaics_dir or paths.mosaic required")


def main() -> int:
    args = parse_args()
    cfg = load_configs(ROOT / args.config, ROOT / args.ecoregion)

    paths = cfg["paths"]
    eco = cfg["ecoregion"]
    pilot = cfg.get("pilot", {})
    project = cfg.get("project", {})
    sampling = cfg.get("sampling", {})

    tile = args.tile or pilot["tiles"][0]
    year = args.year or pilot.get("year") or project.get("mosaic_year") or project.get("year")
    eco_id = int(eco["id"])
    n_pixels = args.n_pixels or sampling.get("n_pixels", 50_000)
    random_state = args.random_state or sampling.get("random_state", 42)

    template = paths.get(
        "mosaic_filename_template",
        "TMP-CHILE-{tile}-{year}-SBAND-184B.tif",
    )
    mosaic_path = resolve_mosaic_path(
        _mosaics_dir(paths),
        tile=tile,
        year=int(year),
        filename_template=template,
    )
    info = read_mosaic_info(mosaic_path)

    stats = warp_eco_mask_to_mosaic(
        ecoregions_path=paths["ecoregions"],
        mosaic_crs=info.crs,
        mosaic_transform=info.transform,
        mosaic_width=info.width,
        mosaic_height=info.height,
        ecoregion_id=eco_id,
    )

    sample = sample_pixels_from_mask(
        mosaic_path=mosaic_path,
        mask=stats.mask,
        n_pixels=int(n_pixels),
        random_state=int(random_state),
    )

    out_dir = Path(args.out_dir) if args.out_dir else Path(paths["results_dir"]) / "samples"
    meta = save_pixel_sample(
        out_dir,
        sample,
        tile=tile,
        year=int(year),
        ecoregion_id=eco_id,
        mosaic_path=mosaic_path,
    )
    meta["eco_mask_pct"] = round(stats.pct_eco, 4)
    meta["status"] = "PASS" if sample.n_finite > 0 else "FAIL"

    print(json.dumps(meta, indent=2))
    return 0 if meta["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
