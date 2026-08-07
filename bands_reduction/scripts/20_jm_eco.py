#!/usr/bin/env python3
"""Jeffries-Matusita ranking @ 184 bands for one ecorregión (Col2 train)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.jm import (
    build_band_list,
    class_counts,
    jm_results_to_frame,
    load_train_samples,
    rank_bands_jm,
)
from src.utils.config import load_yaml

ECO_NAMES = {
    1: "E1_Puna_seca_andina",
    2: "E2_Desierto_Atacama",
    3: "E3_Matorral_norte_1",
    4: "E4_Estepa_andina",
    5: "E5_Matorral_norte_2",
    6: "E6_Andes_norte",
    7: "E7_Andes_central",
    8: "E8_Matorral_sur",
    9: "E9_Costa_norte",
    10: "E10_Andes_sur",
    11: "E11_Costa_sur_1",
    12: "E12_Costa_sur_2",
    13: "E13_Andes_sur_costa",
    14: "E14_Estepa_patagonica",
    15: "E15_Bosque_subpolar",
}

DEFAULT_SAMPLES_NPZ = (
    "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_JM/samples/chile_train_184.npz"
)
DEFAULT_SAMPLES_INDEX = (
    "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_JM/samples/chile_train_184_index.csv"
)
STRATIFIED_SAMPLES_NPZ = (
    "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_stratified_train "
    "(de boruta final)/samples/chile_train_184_stratified.npz"
)
STRATIFIED_SAMPLES_INDEX = (
    "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_stratified_train "
    "(de boruta final)/samples/chile_train_184_stratified_index.csv"
)
DEFAULT_OUT_ROOT = str(ROOT / "results" / "JM_test_PE" / "184bands_ecorregion")
ME_JM_ROOT = Path("/home/lserey/mapbiomas_land/tmp/JM_test_ME/184bands_ecorregion/by_ecoregion")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="JM ranking @ 184B for one ecorregión")
    p.add_argument("--eco-id", type=int, required=True)
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--samples-npz", default=None)
    p.add_argument("--samples-index", default=None)
    p.add_argument(
        "--sample-set",
        choices=("official", "stratified"),
        default="official",
        help="official=1 pt/polígono Col2; stratified=~GEE stratifiedSample",
    )
    p.add_argument("--out-root", default=None)
    p.add_argument("--mean-jm-min", type=float, default=1.0, help="Cut for band_list_jm.json")
    p.add_argument("--exclude-classes", type=int, nargs="*", default=[33, 34])
    p.add_argument(
        "--band-names-json",
        default=None,
        help="JSON with band_names list (default: results/E{id}/2015/eco_merged/sample_meta.json)",
    )
    return p.parse_args()


def load_band_names(cfg: dict, eco_id: int, band_names_json: str | None) -> list[str]:
    if band_names_json:
        payload = json.loads(Path(band_names_json).read_text())
        if "band_names" in payload:
            return list(payload["band_names"])
        return list(payload)
    from src.utils.config import resolve_results_dir

    meta = resolve_results_dir(cfg, ROOT) / f"E{eco_id}" / "2015" / "eco_merged" / "sample_meta.json"
    payload = json.loads(meta.read_text())
    return list(payload["band_names"])


def resolve_sample_paths(args: argparse.Namespace) -> tuple[str, str, Path]:
    if args.sample_set == "stratified":
        npz = args.samples_npz or STRATIFIED_SAMPLES_NPZ
        index = args.samples_index or STRATIFIED_SAMPLES_INDEX
        out_root = Path(args.out_root or ROOT / "results" / "JM_test_PE" / "184bands_ecorregion_stratified")
    else:
        npz = args.samples_npz or DEFAULT_SAMPLES_NPZ
        index = args.samples_index or DEFAULT_SAMPLES_INDEX
        out_root = Path(args.out_root or DEFAULT_OUT_ROOT)
    return npz, index, out_root


def main() -> None:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    eco_id = args.eco_id
    band_names = load_band_names(cfg, eco_id, args.band_names_json)
    samples_npz, samples_index, out_root = resolve_sample_paths(args)

    X, y, _idx = load_train_samples(samples_npz, samples_index, eco_id)
    excl = tuple(args.exclude_classes)
    keep = ~np.isin(y, list(excl))
    results = rank_bands_jm(
        X,
        y,
        band_names,
        exclude_classes=excl,
    )
    ranking = jm_results_to_frame(results)

    out_dir = out_root / f"E{eco_id:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    ranking_path = out_dir / "jm_ranking.csv"
    ranking.to_csv(ranking_path, index=False)

    band_list = build_band_list(ranking, mean_jm_min=args.mean_jm_min)
    band_list["ecoregion"] = eco_id
    band_list["year"] = int(cfg["project"]["mosaic_year"])
    band_list_path = out_dir / "band_list_jm.json"
    band_list_path.write_text(json.dumps(band_list, indent=2) + "\n")

    y_eval = y[keep]
    cc_excl = class_counts(y_eval)
    top10 = ranking.head(10).to_dict(orient="records")
    summary = {
        "eco_id": eco_id,
        "eco_name": ECO_NAMES.get(eco_id, f"E{eco_id}"),
        "n_samples": int(len(y)),
        "n_samples_after_exclude": int(y_eval.size),
        "exclude_classes": list(args.exclude_classes),
        "n_bands": len(band_names),
        "n_classes": len(cc_excl),
        "class_counts": cc_excl,
        "mean_jm_min": args.mean_jm_min,
        "n_bands_ge_cut": int((ranking["mean_jm"] >= args.mean_jm_min).sum()),
        "top10": top10,
        "samples_npz": str(samples_npz),
        "samples_index": str(samples_index),
        "sample_set": args.sample_set,
        "formula": "JM = sqrt(2 * (1 - BC)), BC Gaussian Bhattacharyya",
        "status": "OK",
    }
    summary_path = out_dir / "jm_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"E{eco_id} JM: {summary['n_samples_after_exclude']} samples, {summary['n_classes']} classes")
    print(f"  top: {top10[0]['band_name']} (mean_jm={top10[0]['mean_jm']:.4f})")
    print(f"  bands @ mean_jm>={args.mean_jm_min}: {summary['n_bands_ge_cut']}")
    print(f"  wrote {ranking_path}")


if __name__ == "__main__":
    main()
