#!/usr/bin/env python3
"""Extract Col2 val (or train) sample reflectances @ 184 bands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.col2_extract import extract_col2_layer, save_col2_npz
from src.io.mosaic import mosaic_layout_from_paths
from src.utils.config import load_yaml, resolve_results_dir

DEFAULT_SAMPLES_DIR = Path("/home/lserey/mapbiomas_land/Muestras_Col2/particion_tv_col2")
DEFAULT_TILES_GPKG = Path("/home/lserey/mapbiomas_land/ancillary_data/Tiles_Chile_Sentinel.gpkg")
DEFAULT_OUT = ROOT / "results" / "CIM2015" / "QA" / "samples"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract Col2 layer samples @ 184 bands")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--layer", choices=("train", "val"), default="val")
    p.add_argument("--eco-id", type=int, action="append", default=None)
    p.add_argument("--samples-dir", default=str(DEFAULT_SAMPLES_DIR))
    p.add_argument("--tiles-gpkg", default=str(DEFAULT_TILES_GPKG))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    p.add_argument("--exclude-classes", type=int, nargs="*", default=[33, 34])
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    paths = cfg.get("paths") or {}
    year = int(cfg["project"]["mosaic_year"])
    mosaics_dir = Path(paths["mosaics_dir"])
    template = paths.get("mosaic_filename_template", "TMP-CHILE-{tile}-{year}-SBAND-184B.tif")
    layout = mosaic_layout_from_paths(paths)
    eco_ids = args.eco_id or list(range(1, 16))

    X, y, idx, band_names = extract_col2_layer(
        samples_dir=Path(args.samples_dir),
        mosaics_dir=mosaics_dir,
        tiles_gpkg=Path(args.tiles_gpkg),
        year=year,
        filename_template=template,
        layer=args.layer,
        eco_ids=eco_ids,
        exclude_classes=tuple(args.exclude_classes),
        mosaic_layout=layout,
    )

    scope = f"col2_{args.layer}_E{'_'.join(str(i) for i in eco_ids)}"
    out = save_col2_npz(
        Path(args.out_dir),
        scope=scope,
        layer=args.layer,
        year=year,
        X=X,
        y=y,
        index=idx,
        band_names=band_names,
        meta_extra={
            "eco_ids": eco_ids,
            "samples_dir": str(args.samples_dir),
            "mosaics_dir": str(mosaics_dir),
            "exclude_classes": list(args.exclude_classes),
        },
    )
    print(f"Extracted {X.shape[0]} samples ({args.layer}), {X.shape[1]} bands")
    print(f"  npz:   {out['npz']}")
    print(f"  index: {out['index']}")


if __name__ == "__main__":
    main()
