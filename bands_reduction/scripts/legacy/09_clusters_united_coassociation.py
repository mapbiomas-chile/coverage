#!/usr/bin/env python3
"""Unite per-tile band clusters via co-association (ecoregion-level).

For each |r| threshold folder under 02_clusters_by_tile/tiles/*/{thr}/:
  - build C[i,j] = fraction of tiles where bands i,j share a local cluster
  - hierarchical cluster with d=1-C, cut at 1-coassoc_threshold (default 0.70)
  - write results/E{eco}/{year}/clusters_united/{thr}/

Example:
  python scripts/legacy/09_clusters_united_coassociation.py --eco-id 2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.selection.coassociation import (
    accumulate_coassociation,
    cluster_from_coassociation,
    save_clusters_united,
)
from src.utils import (
    clusters_by_tile_dir,
    clusters_united_dir,
    corr_threshold_dirname,
    load_yaml,
    resolve_results_dir,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ecoregion clusters via co-association")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument("--eco-id", type=int, default=2)
    p.add_argument("--year", type=int, default=None)
    p.add_argument(
        "--corr-thresholds",
        default=None,
        help="Comma list (default: clustering.corr_thresholds from config)",
    )
    p.add_argument(
        "--coassoc-threshold",
        type=float,
        default=None,
        help="Min co-association to merge (default: clustering.coassoc_threshold)",
    )
    p.add_argument(
        "--tiles-root",
        default=None,
        help="Override .../02_clusters_by_tile/tiles",
    )
    p.add_argument(
        "--out-root",
        default=None,
        help="Override .../clusters_united",
    )
    return p.parse_args()


def load_tile_labels(assign_csv: Path) -> tuple[np.ndarray, list[str] | None]:
    df = pd.read_csv(assign_csv)
    if "band_index" not in df.columns or "cluster_id" not in df.columns:
        raise ValueError(f"bad assignment columns in {assign_csv}")
    df = df.sort_values("band_index")
    labels = df["cluster_id"].to_numpy(dtype=np.int32)
    names = (
        df["band_name"].astype(str).tolist() if "band_name" in df.columns else None
    )
    return labels, names


def process_threshold(
    *,
    tiles_root: Path,
    out_dir: Path,
    thr_name: str,
    coassoc_threshold: float,
    linkage: str,
    eco_id: int,
    year: int,
) -> dict:
    label_rows: list[np.ndarray] = []
    tiles_used: list[str] = []
    band_names: list[str] | None = None
    n_bands: int | None = None

    for tile_dir in sorted(p for p in tiles_root.iterdir() if p.is_dir()):
        assign = tile_dir / thr_name / "band_cluster_assignment.csv"
        if not assign.is_file():
            continue
        labels, names = load_tile_labels(assign)
        if n_bands is None:
            n_bands = int(labels.shape[0])
            band_names = names
        elif labels.shape[0] != n_bands:
            raise ValueError(
                f"{tile_dir.name}: n_bands {labels.shape[0]} != {n_bands}"
            )
        label_rows.append(labels)
        tiles_used.append(tile_dir.name)

    if not label_rows:
        return {
            "corr_threshold": thr_name,
            "status": "SKIP",
            "reason": "no_tile_assignments",
            "out_dir": str(out_dir),
        }

    C = accumulate_coassociation(label_rows)
    result = cluster_from_coassociation(
        C,
        coassoc_threshold=coassoc_threshold,
        linkage_method=linkage,
    )
    summary = save_clusters_united(
        result,
        C,
        out_dir,
        band_names=band_names,
        extra_meta={
            "eco_id": eco_id,
            "year": year,
            "corr_threshold": float(thr_name),
            "n_tiles": len(tiles_used),
            "tiles": tiles_used,
            "method": "coassociation_hierarchical",
        },
    )
    iu = np.triu_indices(C.shape[0], k=1)
    vals = C[iu]
    brief = {
        "corr_threshold": float(thr_name),
        "status": "PASS",
        "n_tiles": len(tiles_used),
        "n_bands": summary["n_bands"],
        "n_clusters": summary["n_clusters"],
        "n_singletons": summary["n_singletons"],
        "n_multi": summary["n_multi"],
        "max_cluster_size": summary["max_cluster_size"],
        "coassoc_threshold": coassoc_threshold,
        "pair_coassoc_mean": float(vals.mean()),
        "pair_coassoc_median": float(np.median(vals)),
        "out_dir": str(out_dir),
    }
    (out_dir / "run_brief.json").write_text(json.dumps(brief, indent=2) + "\n")
    return brief


def main() -> int:
    args = parse_args()
    cfg = load_yaml(ROOT / args.config)
    clustering = cfg.get("clustering", {})
    year = args.year or int(cfg["project"].get("mosaic_year") or cfg["project"].get("year"))
    results_dir = resolve_results_dir(cfg, ROOT)

    if args.corr_thresholds:
        corr_thrs = [float(x.strip()) for x in args.corr_thresholds.split(",") if x.strip()]
    else:
        corr_thrs = [float(x) for x in clustering.get("corr_thresholds", [0.95, 0.90, 0.85])]

    coassoc_thr = (
        args.coassoc_threshold
        if args.coassoc_threshold is not None
        else float(clustering.get("coassoc_threshold", 0.70))
    )
    linkage = clustering.get("coassoc_linkage") or clustering.get("linkage", "average")

    tiles_root = Path(
        args.tiles_root or (clusters_by_tile_dir(results_dir, args.eco_id, year) / "tiles")
    )
    out_root = Path(
        args.out_root or clusters_united_dir(results_dir, args.eco_id, year)
    )

    if not tiles_root.is_dir():
        print(f"tiles root not found: {tiles_root}", file=sys.stderr)
        return 1

    briefs = []
    for thr in corr_thrs:
        thr_name = corr_threshold_dirname(thr)
        out_dir = out_root / thr_name
        brief = process_threshold(
            tiles_root=tiles_root,
            out_dir=out_dir,
            thr_name=thr_name,
            coassoc_threshold=coassoc_thr,
            linkage=linkage,
            eco_id=args.eco_id,
            year=year,
        )
        briefs.append(brief)
        print(json.dumps(brief))

    master = {
        "eco_id": args.eco_id,
        "year": year,
        "coassoc_threshold": coassoc_thr,
        "linkage": linkage,
        "tiles_root": str(tiles_root),
        "out_root": str(out_root),
        "thresholds": briefs,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "summary_all_thresholds.json").write_text(
        json.dumps(master, indent=2) + "\n"
    )
    print(f"wrote {out_root / 'summary_all_thresholds.json'}")
    return 0 if all(b.get("status") == "PASS" for b in briefs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
