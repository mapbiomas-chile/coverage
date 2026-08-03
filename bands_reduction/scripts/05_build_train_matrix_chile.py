#!/usr/bin/env python3
"""Build Chile-wide train matrix (184 bands) from Col2 train GPKGs — no model training.

Loads layer 'train' from every ecoregion GPKG, samples mosaic spectra at each
polygon representative point, writes NPZ for JM ranking.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.band_list import band_list_from_indices, save_band_list
from src.io.extract_spectra import (
    assign_tiles,
    extract_spectra_by_tile,
    list_mosaic_tiles,
    load_all_train_samples,
)
from src.io.samples import save_samples
from src.utils.config import load_yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/global.yaml")
    parser.add_argument(
        "--samples-dir",
        default="/home/lserey/mapbiomas_land/Muestras_Col2/particion_tv_col2",
    )
    parser.add_argument(
        "--tiles-gpkg",
        default="/home/lserey/mapbiomas_land/ancillary_data/Tiles_Chile_Sentinel.gpkg",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_all"),
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Tile-parallel workers (keep low for RAM)",
    )
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args()

    cfg_path = Path(args.config)
    cfg = load_yaml(ROOT / cfg_path if not cfg_path.is_absolute() else cfg_path)
    year = args.year or int(cfg.get("project", {}).get("year", 2015))
    n_bands = int(cfg.get("project", {}).get("n_bands_full", 184))
    mosaic_dir = cfg["paths"]["mosaic"]

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "samples").mkdir(exist_ok=True)
    (out_dir / "band_lists").mkdir(exist_ok=True)
    (out_dir / "logs").mkdir(exist_ok=True)

    t0 = time.time()
    print("Loading train layers…")
    samples = load_all_train_samples(args.samples_dir)
    print(f"  n_train={len(samples)} ecoregions={samples['eco_id'].nunique()}")

    mosaic_tiles = list_mosaic_tiles(mosaic_dir)
    print(f"Assigning tiles ({len(mosaic_tiles)} mosaics available)…")
    samples = assign_tiles(samples, args.tiles_gpkg, mosaic_tiles)
    n_no_tile = int(samples["tile"].isna().sum())
    print(f"  without tile: {n_no_tile}")

    print(f"Extracting spectra (workers={args.max_workers})…")
    X, ok, band_names = extract_spectra_by_tile(
        samples,
        mosaic_dir,
        year=year,
        n_bands=n_bands,
        max_workers=args.max_workers,
    )
    print(f"  ok={ok.sum()}/{len(ok)} in {time.time()-t0:.1f}s")

    y = samples["class"].to_numpy(dtype=np.int32)
    rows = np.full(len(samples), -1, dtype=np.int32)
    cols = np.full(len(samples), -1, dtype=np.int32)

    keep = ok & (samples["tile"].notna().to_numpy())
    Xk, yk, rowsk, colsk = X[keep], y[keep], rows[keep], cols[keep]
    meta_df = samples.loc[
        keep, ["sample_id", "eco_id", "eco_name", "class", "tile", "source_gpkg"]
    ].copy()

    npz_path = out_dir / "samples" / "chile_train_184.npz"
    meta = {
        "scope": "chile_all_ecoregions_train",
        "year": year,
        "n_bands": n_bands,
        "n_input": int(len(samples)),
        "n_ok": int(keep.sum()),
        "n_ecoregions": int(samples["eco_id"].nunique()),
        "samples_dir": str(args.samples_dir),
        "mosaic_dir": str(mosaic_dir),
        "extraction": "representative_point + rasterio.sample",
        "note": "JM does not train; train= layer split name only",
        "class_counts": {
            str(int(c)): int(n) for c, n in zip(*np.unique(yk, return_counts=True))
        },
        "eco_counts": meta_df["eco_id"].value_counts().sort_index().astype(int).to_dict(),
    }
    save_samples(npz_path, X=Xk, rows=rowsk, cols=colsk, y=yk, meta=meta)
    meta_csv = out_dir / "samples" / "chile_train_184_index.csv"
    meta_df.to_csv(meta_csv, index=False)

    bl = band_list_from_indices(
        list(range(n_bands)),
        source="full",
        year=year,
        band_names=band_names,
    )
    bl["scope"] = "chile_184"
    save_band_list(out_dir / "band_lists" / "band_list_full_184.json", bl)

    summary = {
        **meta,
        "npz": str(npz_path),
        "index_csv": str(meta_csv),
        "band_list": str(out_dir / "band_lists" / "band_list_full_184.json"),
        "elapsed_s": round(time.time() - t0, 2),
        "max_workers": args.max_workers,
    }
    (out_dir / "logs" / "05_extract_summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
