#!/usr/bin/env python3
"""Compare PE JM rankings vs JM_test_ME reference (and optional PE official)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
ME_ROOT = Path("/home/lserey/mapbiomas_land/tmp/JM_test_ME/184bands_ecorregion/by_ecoregion")
PE_OFFICIAL = ROOT / "results" / "JM_test_PE" / "184bands_ecorregion"
PE_STRAT = ROOT / "results" / "JM_test_PE" / "184bands_ecorregion_stratified"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare JM rankings PE vs ME")
    p.add_argument("--eco-id", type=int, required=True)
    p.add_argument(
        "--pe-root",
        default=None,
        help="PE JM output root (default: stratified if exists else official)",
    )
    p.add_argument("--top-n", type=int, default=30)
    p.add_argument(
        "--out",
        default=None,
        help="Comparison JSON path (default: results/JM_test_PE/comparisons/E{id}_jm_compare.json)",
    )
    return p.parse_args()


def load_ranking(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.sort_values("band_index").reset_index(drop=True)
    return df


def spearman_on_mean_jm(a: pd.DataFrame, b: pd.DataFrame) -> float:
    merged = a[["band_index", "mean_jm"]].merge(
        b[["band_index", "mean_jm"]],
        on="band_index",
        suffixes=("_a", "_b"),
    )
    if len(merged) < 3:
        return float("nan")
    r, _ = spearmanr(merged["mean_jm_a"], merged["mean_jm_b"])
    return float(r)


def top_overlap(a: pd.DataFrame, b: pd.DataFrame, n: int) -> dict:
    ta = set(a.sort_values("mean_jm", ascending=False).head(n)["band_name"])
    tb = set(b.sort_values("mean_jm", ascending=False).head(n)["band_name"])
    inter = ta & tb
    return {
        "n": n,
        "overlap": len(inter),
        "jaccard": len(inter) / len(ta | tb) if ta | tb else 0.0,
        "bands": sorted(inter),
    }


def main() -> None:
    args = parse_args()
    eco_id = args.eco_id
    eco_tag = f"E{eco_id:02d}"

    me_path = ME_ROOT / eco_tag / "jm_ranking.csv"
    if not me_path.is_file():
        raise FileNotFoundError(f"ME ranking not found: {me_path}")

    if args.pe_root:
        pe_root = Path(args.pe_root)
    elif (PE_STRAT / eco_tag / "jm_ranking.csv").is_file():
        pe_root = PE_STRAT
    else:
        pe_root = PE_OFFICIAL
    pe_path = pe_root / eco_tag / "jm_ranking.csv"
    if not pe_path.is_file():
        raise FileNotFoundError(f"PE ranking not found: {pe_path}")

    me = load_ranking(me_path)
    pe = load_ranking(pe_path)

    me_summary_path = ME_ROOT / eco_tag / "jm_summary.json"
    pe_summary_path = pe_root / eco_tag / "jm_summary.json"
    me_s = json.loads(me_summary_path.read_text()) if me_summary_path.is_file() else {}
    pe_s = json.loads(pe_summary_path.read_text()) if pe_summary_path.is_file() else {}

    official_path = PE_OFFICIAL / eco_tag / "jm_ranking.csv"
    official_overlap = None
    if official_path.is_file() and pe_path != official_path:
        official = load_ranking(official_path)
        official_overlap = top_overlap(pe, official, args.top_n)

    payload = {
        "eco_id": eco_id,
        "me_path": str(me_path),
        "pe_path": str(pe_path),
        "me_n_samples": me_s.get("n_samples"),
        "pe_n_samples": pe_s.get("n_samples_after_exclude"),
        "pe_sample_set": pe_s.get("sample_set"),
        "spearman_mean_jm_pe_vs_me": spearman_on_mean_jm(pe, me),
        "n_bands_ge_1.0": {
            "me": int((me["mean_jm"] >= 1.0).sum()),
            "pe": int((pe["mean_jm"] >= 1.0).sum()),
        },
        f"top{args.top_n}_overlap_pe_vs_me": top_overlap(pe, me, args.top_n),
        "top10_me": me.sort_values("mean_jm", ascending=False).head(10)[
            ["band_name", "mean_jm"]
        ].to_dict(orient="records"),
        "top10_pe": pe.sort_values("mean_jm", ascending=False).head(10)[
            ["band_name", "mean_jm"]
        ].to_dict(orient="records"),
    }
    if official_overlap:
        payload[f"top{args.top_n}_overlap_stratified_vs_official_pe"] = official_overlap

    out_path = (
        Path(args.out)
        if args.out
        else ROOT / "results" / "JM_test_PE" / "comparisons" / f"E{eco_id:02d}_jm_compare.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    print(f"=== E{eco_id} JM compare (PE vs ME) ===")
    print(f"PE samples: {payload['pe_n_samples']} ({payload.get('pe_sample_set', '?')})")
    print(f"ME samples: {payload['me_n_samples']}")
    print(f"Spearman mean_jm: {payload['spearman_mean_jm_pe_vs_me']:.3f}")
    ov = payload[f"top{args.top_n}_overlap_pe_vs_me"]
    print(f"Top-{args.top_n} overlap: {ov['overlap']}/{args.top_n} (Jaccard {ov['jaccard']:.2f})")
    print(f"Bands @ mean_jm>=1.0: PE {payload['n_bands_ge_1.0']['pe']} | ME {payload['n_bands_ge_1.0']['me']}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
