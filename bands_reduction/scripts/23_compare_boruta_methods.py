#!/usr/bin/env python3
"""Compare Boruta_PE vs JM_test_PE vs ME reference (and optional unsup reps)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ME_BORUTA_ROOT = Path("/home/lserey/mapbiomas_land/tmp/JM_test_ME/boruta_3")
DEFAULT_BORUTA_ROOT = ROOT / "results" / "Boruta_PE"
DEFAULT_JM_ROOT = ROOT / "results" / "JM_test_PE" / "184bands_ecorregion_stratified"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Compare Boruta with JM / ME / unsupervised")
    p.add_argument("--eco-id", type=int, required=True)
    p.add_argument("--boruta-root", default=str(DEFAULT_BORUTA_ROOT))
    p.add_argument("--boruta-run", choices=("all184", "reps095"), default="reps095")
    p.add_argument("--jm-root", default=str(DEFAULT_JM_ROOT))
    p.add_argument("--me-root", default=str(ME_BORUTA_ROOT))
    p.add_argument("--unsup-reps-json", default=None, help="representatives.json @ 0.90 etc.")
    p.add_argument(
        "--out",
        default=None,
        help="Default: results/Boruta_PE/comparisons/E{id}_methods_compare.json",
    )
    return p.parse_args()


def load_band_set(path: Path, *, key: str = "bands") -> set[int]:
    payload = json.loads(path.read_text())
    for k in (key, "representatives", "bands"):
        if k in payload:
            return set(int(x) for x in payload[k])
    raise KeyError(f"{path} has no band index list (tried {key}, representatives, bands)")


def load_jm_top_bands(jm_ranking_csv: Path, *, mean_jm_min: float = 1.0) -> set[int]:
    import pandas as pd

    df = pd.read_csv(jm_ranking_csv)
    return set(df.loc[df["mean_jm"] >= mean_jm_min, "band_index"].astype(int).tolist())


def jaccard(a: set[int], b: set[int]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap_payload(a: set[int], b: set[int], label_a: str, label_b: str) -> dict:
    inter = sorted(a & b)
    return {
        "a": label_a,
        "b": label_b,
        "n_a": len(a),
        "n_b": len(b),
        "n_overlap": len(inter),
        "jaccard": jaccard(a, b),
        "bands_overlap": inter,
    }


def main() -> None:
    args = parse_args()
    eco_id = args.eco_id
    eco_tag = f"E{eco_id:02d}"
    boruta_dir = Path(args.boruta_root) / f"{eco_tag}_{args.boruta_run}"
    band_list_path = boruta_dir / "band_list_boruta.json"
    if not band_list_path.is_file():
        raise FileNotFoundError(f"Boruta output not found: {band_list_path}")

    boruta_bands = load_band_set(band_list_path)
    boruta_summary = json.loads((boruta_dir / "boruta_summary.json").read_text())

    jm_path = Path(args.jm_root) / eco_tag / "jm_ranking.csv"
    jm_bands: set[int] = set()
    if jm_path.is_file():
        jm_bands = load_jm_top_bands(jm_path)

    me_path = Path(args.me_root) / eco_tag / "0.95" / "band_list_boruta.json"
    me_bands: set[int] = set()
    me_summary: dict = {}
    if me_path.is_file():
        me_bands = load_band_set(me_path)
        me_summary_path = me_path.parent / "boruta_summary.json"
        if me_summary_path.is_file():
            me_summary = json.loads(me_summary_path.read_text())

    unsup_bands: set[int] = set()
    unsup_path = args.unsup_reps_json
    if unsup_path:
        unsup_bands = load_band_set(Path(unsup_path))

    payload: dict = {
        "eco_id": eco_id,
        "boruta_pe_path": str(band_list_path),
        "boruta_pe_run": args.boruta_run,
        "boruta_pe_n_kept": len(boruta_bands),
        "boruta_pe_n_samples": boruta_summary.get("n_samples"),
        "boruta_pe_sample_set": boruta_summary.get("sample_set"),
        "boruta_pe_bands": sorted(boruta_bands),
        "overlaps": [],
    }

    if jm_bands:
        payload["jm_pe_n_bands"] = len(jm_bands)
        payload["overlaps"].append(overlap_payload(boruta_bands, jm_bands, "boruta_pe", "jm_pe"))
    if me_bands:
        payload["me_n_kept"] = len(me_bands)
        payload["me_n_samples"] = me_summary.get("n_samples")
        payload["overlaps"].append(overlap_payload(boruta_bands, me_bands, "boruta_pe", "me_boruta_3"))
    if unsup_bands:
        payload["unsup_n_reps"] = len(unsup_bands)
        payload["overlaps"].append(
            overlap_payload(boruta_bands, unsup_bands, "boruta_pe", "unsup_reps")
        )

    out_path = (
        Path(args.out)
        if args.out
        else Path(args.boruta_root) / "comparisons" / f"{eco_tag}_{args.boruta_run}_methods_compare.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    print(f"=== E{eco_id} methods compare ({args.boruta_run}) ===")
    print(f"Boruta PE kept: {len(boruta_bands)} bands ({boruta_summary.get('n_samples')} samples)")
    for ov in payload["overlaps"]:
        print(
            f"  {ov['a']} vs {ov['b']}: overlap {ov['n_overlap']} "
            f"(Jaccard {ov['jaccard']:.2f})"
        )
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
