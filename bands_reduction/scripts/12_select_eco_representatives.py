#!/usr/bin/env python3
"""Select central representatives (+ optional family rescue) per eco threshold.

Example:
  python scripts/12_select_eco_representatives.py --eco-id 2
  # → results/E2/2015/eco_merged/{0.95,0.90,0.85}/representatives/
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
import pandas as pd

from src.selection import (
    band_family,
    rescue_missing_families,
    save_representatives,
    select_central_representatives,
)
from src.utils import (
    corr_threshold_dirname,
    eco_merged_dir,
    load_configs,
    resolve_results_dir,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Eco representatives: central + family rescue")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--eco-id", type=int, default=2)
    p.add_argument("--year", type=int, default=None)
    p.add_argument("--corr-thresholds", default=None)
    p.add_argument("--eco-merged-dir", default=None)
    p.add_argument(
        "--no-family-rescue",
        action="store_true",
        help="Disable family rescue even if enabled in config",
    )
    return p.parse_args()


def process_threshold(
    thr_dir: Path,
    band_names: list[str],
    *,
    family_rescue: bool,
    eco_id: int,
    year: int,
    thr: float,
) -> dict:
    labels_path = thr_dir / "band_cluster_labels.npy"
    corr_path = thr_dir / "corr_abs.npy"
    if not labels_path.is_file() or not corr_path.is_file():
        return {"corr_threshold": thr, "status": "SKIP", "reason": "missing_cluster_artifacts"}

    labels = np.load(labels_path)
    corr = np.load(corr_path)
    reps = select_central_representatives(corr, labels)
    reps["band_name"] = reps["representative"].map(
        lambda i: band_names[int(i)] if int(i) < len(band_names) else f"band_{i}"
    )

    rep_idx = [int(x) for x in reps["representative"].tolist()]
    rescue_df = pd.DataFrame()
    if family_rescue:
        rep_idx, rescue_df = rescue_missing_families(rep_idx, band_names)

    out_dir = thr_dir / "representatives"
    rows = []
    for _, r in reps.iterrows():
        rows.append(
            {
                "cluster_id": int(r.cluster_id),
                "size": int(r.size),
                "representative": int(r.representative),
                "band_name": band_names[int(r.representative)],
                "mean_abs_r_to_others": float(r.mean_abs_r_to_others),
                "members": list(r.members),
                "source": "central",
            }
        )
    central_set = {int(x) for x in reps["representative"].tolist()}
    for _, rr in rescue_df.iterrows():
        bi = int(rr.rescued_band_index)
        if bi in central_set:
            continue
        rows.append(
            {
                "cluster_id": -1,
                "size": 1,
                "representative": bi,
                "band_name": rr.rescued_band_name,
                "mean_abs_r_to_others": 1.0,
                "members": [bi],
                "source": "family_rescue",
            }
        )
    detail = pd.DataFrame(rows)
    # save via helper for central-only summary, then overwrite enriched artifacts
    summary = save_representatives(
        reps,
        out_dir,
        extra_meta={
            "eco_id": eco_id,
            "year": year,
            "corr_threshold": thr,
            "family_rescue": family_rescue,
            "n_rescued": int(len(rescue_df)),
        },
    )

    # enriched outputs
    named = detail[["representative", "band_name", "cluster_id", "size", "source"]].copy()
    named["family"] = named["band_name"].map(band_family)
    named = named.sort_values(["source", "family", "representative"])
    named.to_csv(out_dir / "representatives_named.csv", index=False)
    (out_dir / "representatives_detail.json").write_text(
        json.dumps(detail.to_dict(orient="records"), indent=2) + "\n"
    )
    if len(rescue_df):
        rescue_df.to_csv(out_dir / "family_rescue.csv", index=False)
    else:
        (out_dir / "family_rescue.csv").write_text(
            "family,rescued_band_index,rescued_band_name,n_family_bands,reason\n"
        )

    final_idx = sorted(set(int(x) for x in named["representative"].tolist()))
    final_names = [band_names[i] for i in final_idx]
    payload = {
        "method": "central_mean_abs_r",
        "family_rescue": family_rescue,
        "n_representatives": len(final_idx),
        "n_central": int((named["source"] == "central").sum()),
        "n_rescued": int((named["source"] == "family_rescue").sum()),
        "representatives": final_idx,
        "band_names": final_names,
    }
    (out_dir / "representatives.json").write_text(json.dumps(payload, indent=2) + "\n")

    # family coverage report
    fam_cov = (
        named.groupby("family")
        .agg(n_reps=("representative", "count"), bands=("band_name", lambda s: ", ".join(s)))
        .reset_index()
    )
    fam_cov.to_csv(out_dir / "family_coverage.csv", index=False)

    summary.update(
        {
            "n_representatives_final": len(final_idx),
            "n_rescued": payload["n_rescued"],
            "status": "PASS",
            "corr_threshold": thr,
            "out_dir": str(out_dir),
        }
    )
    (out_dir / "representatives_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return {
        "corr_threshold": thr,
        "status": "PASS",
        "n_clusters": int(len(reps)),
        "n_representatives": len(final_idx),
        "n_rescued": payload["n_rescued"],
        "out_dir": str(out_dir),
    }


def main() -> int:
    args = parse_args()
    cfg = load_configs(ROOT / args.config)
    clustering = cfg.get("clustering", {})
    rep_cfg = cfg.get("representatives", {})
    year = args.year or int(cfg["project"].get("mosaic_year") or 2015)
    results_dir = resolve_results_dir(cfg, ROOT)
    root = Path(args.eco_merged_dir or eco_merged_dir(results_dir, args.eco_id, year))

    meta_path = root / "sample_meta.json"
    if not meta_path.is_file():
        print(f"sample_meta.json not found: {meta_path}", file=sys.stderr)
        return 1
    meta = json.loads(meta_path.read_text())
    band_names = meta.get("band_names") or []

    if args.corr_thresholds:
        corr_thrs = [float(x.strip()) for x in args.corr_thresholds.split(",") if x.strip()]
    else:
        corr_thrs = [float(x) for x in clustering.get("corr_thresholds", [0.95, 0.90, 0.85])]

    family_rescue = bool(rep_cfg.get("family_rescue", True)) and not args.no_family_rescue

    briefs = []
    for thr in corr_thrs:
        thr_dir = root / corr_threshold_dirname(thr)
        brief = process_threshold(
            thr_dir,
            band_names,
            family_rescue=family_rescue,
            eco_id=args.eco_id,
            year=year,
            thr=thr,
        )
        briefs.append(brief)
        print(json.dumps(brief))

    master = {
        "eco_id": args.eco_id,
        "year": year,
        "family_rescue": family_rescue,
        "thresholds": briefs,
        "eco_merged_dir": str(root),
    }
    (root / "representatives_all_thresholds.json").write_text(
        json.dumps(master, indent=2) + "\n"
    )
    print(f"wrote {root / 'representatives_all_thresholds.json'}")
    ok = all(b.get("status") == "PASS" for b in briefs)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
