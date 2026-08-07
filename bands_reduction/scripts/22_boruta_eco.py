#!/usr/bin/env python3
"""Boruta feature selection for one ecorregión (Col2 train samples)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.boruta import (
    BorutaParams,
    build_band_list_boruta,
    build_boruta_summary,
    load_representatives,
    prepare_eco_matrix,
    run_boruta_selection,
)
from src.utils.config import load_yaml, resolve_results_dir

STRATIFIED_SAMPLES_NPZ = (
    "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_stratified_train "
    "(de boruta final)/samples/chile_train_184_stratified.npz"
)
STRATIFIED_SAMPLES_INDEX = (
    "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_stratified_train "
    "(de boruta final)/samples/chile_train_184_stratified_index.csv"
)
DEFAULT_OUT_ROOT = ROOT / "results" / "Boruta_PE"
DEFAULT_CORR_THRESHOLD = 0.95


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Boruta selection for one ecorregión")
    p.add_argument("--eco-id", type=int, required=True)
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument(
        "--input-bands",
        choices=("all184", "reps095"),
        default="all184",
        help="all184=full stack; reps095=PE representatives @ |r|>=0.95",
    )
    p.add_argument("--sample-set", choices=("stratified", "official"), default="stratified")
    p.add_argument("--samples-npz", default=None)
    p.add_argument("--samples-index", default=None)
    p.add_argument("--out-root", default=None, help="Default: results/Boruta_PE")
    p.add_argument("--representatives-json", default=None)
    p.add_argument("--corr-threshold", type=float, default=DEFAULT_CORR_THRESHOLD)
    p.add_argument("--exclude-classes", type=int, nargs="*", default=[33, 34])
    p.add_argument("--max-samples", type=int, default=None, help="Optional stratified cap")
    p.add_argument("--max-iter", type=int, default=50)
    p.add_argument("--n-estimators", type=int, default=200)
    p.add_argument("--perc", type=float, default=95.0)
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--tentative-min-hit-rate", type=float, default=0.40)
    p.add_argument("--random-state", type=int, default=42)
    p.add_argument("--n-jobs", type=int, default=8)
    p.add_argument("--band-names-json", default=None)
    return p.parse_args()


def load_band_names(cfg: dict, eco_id: int, band_names_json: str | None) -> list[str]:
    if band_names_json:
        payload = json.loads(Path(band_names_json).read_text())
        if "band_names" in payload:
            return list(payload["band_names"])
        return list(payload)
    results_dir = resolve_results_dir(cfg, ROOT)
    meta = results_dir / f"E{eco_id}" / "2015" / "eco_merged" / "sample_meta.json"
    payload = json.loads(meta.read_text())
    return list(payload["band_names"])


def resolve_sample_paths(args: argparse.Namespace) -> tuple[str, str]:
    if args.sample_set == "stratified":
        return (
            args.samples_npz or STRATIFIED_SAMPLES_NPZ,
            args.samples_index or STRATIFIED_SAMPLES_INDEX,
        )
    npz = (
        args.samples_npz
        or "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_JM/samples/chile_train_184.npz"
    )
    index = (
        args.samples_index
        or "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_JM/samples/chile_train_184_index.csv"
    )
    return npz, index


def resolve_representatives_json(
    cfg: dict,
    eco_id: int,
    corr_threshold: float,
    representatives_json: str | None,
) -> Path:
    if representatives_json:
        return Path(representatives_json)
    results_dir = resolve_results_dir(cfg, ROOT)
    thr = f"{corr_threshold:.2f}"
    path = (
        results_dir
        / f"E{eco_id}"
        / "2015"
        / "eco_merged"
        / thr
        / "representatives"
        / "representatives.json"
    )
    if not path.is_file():
        raise FileNotFoundError(f"Representatives not found: {path}")
    return path


def main() -> None:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    eco_id = args.eco_id
    year = int(cfg["project"]["mosaic_year"])
    band_names_full = load_band_names(cfg, eco_id, args.band_names_json)
    samples_npz, samples_index = resolve_sample_paths(args)

    params = BorutaParams(
        max_iter=args.max_iter,
        n_estimators=args.n_estimators,
        perc=args.perc,
        alpha=args.alpha,
        tentative_min_hit_rate=args.tentative_min_hit_rate,
        random_state=args.random_state,
        n_jobs=args.n_jobs,
    )
    exclude = tuple(args.exclude_classes)

    X, y = prepare_eco_matrix(
        samples_npz,
        samples_index,
        eco_id,
        exclude_classes=exclude,
        max_samples=args.max_samples,
        random_state=args.random_state,
    )

    reps_json: str | None = None
    corr_thr: float | None = None
    if args.input_bands == "all184":
        band_indices = list(range(len(band_names_full)))
        band_names = band_names_full
        parent_source = "all184bands"
    else:
        reps_path = resolve_representatives_json(
            cfg, eco_id, args.corr_threshold, args.representatives_json
        )
        reps_json = str(reps_path)
        band_indices = load_representatives(reps_path)
        band_names = [band_names_full[i] for i in band_indices]
        parent_source = f"pe_eco_merged_{args.corr_threshold:.2f}_reps"
        corr_thr = args.corr_threshold

    X_sel = X[:, band_indices]

    selector, decisions = run_boruta_selection(
        X_sel,
        y,
        band_indices,
        band_names,
        params=params,
    )

    run_tag = "all184" if args.input_bands == "all184" else "reps095"
    out_root = Path(args.out_root or DEFAULT_OUT_ROOT)
    out_dir = out_root / f"E{eco_id:02d}_{run_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    decisions_path = out_dir / "boruta_decisions.csv"
    decisions.to_csv(decisions_path, index=False)

    band_list = build_band_list_boruta(
        decisions,
        eco_id=eco_id,
        year=year,
        params=params,
        parent_source=parent_source,
        parent_n_bands=len(band_indices),
        exclude_classes=list(args.exclude_classes),
        selector=selector,
    )
    band_list_path = out_dir / "band_list_boruta.json"
    band_list_path.write_text(json.dumps(band_list, indent=2) + "\n")

    summary = build_boruta_summary(
        eco_id=eco_id,
        n_samples=X_sel.shape[0],
        y=y,
        exclude_classes=list(args.exclude_classes),
        band_indices=band_indices,
        corr_threshold_parent=corr_thr,
        params=params,
        decisions=decisions,
        selector=selector,
        samples_npz=samples_npz,
        samples_index=samples_index,
        sample_set=args.sample_set,
        representatives_json=reps_json,
        parent_source=parent_source,
        out_dir=out_dir,
    )
    summary_path = out_dir / "boruta_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    kept = decisions.loc[decisions["kept_in_band_list"] == 1]
    print(
        f"E{eco_id} Boruta ({run_tag}): {summary['n_samples']} samples, "
        f"{summary['n_classes']} classes, {len(band_indices)} input bands"
    )
    print(
        f"  confirmed={summary['n_confirmed']} tentative={summary['n_tentative']} "
        f"kept={summary['n_kept_total']} iters={summary['n_iters']}"
    )
    if not kept.empty:
        top = kept.iloc[0]
        print(f"  top kept: {top['band_name']} (hit_rate={top['hit_rate']:.3f})")
    print(f"  wrote {decisions_path}")


if __name__ == "__main__":
    main()
