#!/usr/bin/env python3
"""Run JM independently for each ecoregion using Chile train matrix (184 bands)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.band_list import band_list_from_indices, load_band_list, save_band_list
from src.io.samples import load_samples, select_bands
from src.selection.jm import rank_bands_by_jm

CLASS_NAMES = {
    11: "Humedal",
    12: "Pastizal",
    15: "Pastura",
    18: "Agricultura",
    23: "Arena, Playa y Duna",
    24: "Infraestructura",
    25: "Otra área sin vegetación",
    29: "Afloramiento Rocoso",
    33: "Río, lago u océano",
    34: "Hielo y nieve",
    59: "Bosque Primario",
    60: "Bosque Secundario",
    61: "Salar",
    62: "Sin nombre en leyenda",
    63: "Estepa",
    66: "Matorral",
    67: "Bosque Achaparrado",
    79: "Coníferas",
    80: "Latifoliadas",
}


def _plot_top15(rank: pd.DataFrame, title: str, out: Path) -> None:
    t15 = rank.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(t15["band_name"].astype(str), t15["mean_jm"], color="#2a6f7a")
    ax.set_xlim(0, 2)
    ax.set_xlabel("Mean pairwise JM (0-2)")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--samples",
        type=Path,
        default=Path(
            "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_all/samples/chile_train_184.npz"
        ),
    )
    parser.add_argument(
        "--index-csv",
        type=Path,
        default=Path(
            "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_all/samples/chile_train_184_index.csv"
        ),
    )
    parser.add_argument(
        "--band-list",
        type=Path,
        default=Path(
            "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_all/band_lists/band_list_full_184.json"
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/home/lserey/mapbiomas_land/tmp/JM_test_ME/184bands_ecorregion"),
    )
    parser.add_argument("--min-count", type=int, default=10)
    parser.add_argument("--min-samples-eco", type=int, default=50)
    args = parser.parse_args()

    data = load_samples(args.samples)
    if "y" not in data:
        raise SystemExit("samples NPZ missing y")
    X_full, y_full = data["X"], data["y"]
    idx = pd.read_csv(args.index_csv)
    if len(idx) != len(y_full):
        raise SystemExit(f"index rows {len(idx)} != samples {len(y_full)}")

    band_list = load_band_list(args.band_list)
    bands = band_list["bands"]
    band_names = band_list.get("band_names")

    out = args.out_dir
    (out / "by_ecoregion").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)
    (out / "summaries").mkdir(exist_ok=True)

    eco_ids = sorted(idx["eco_id"].dropna().unique().astype(int))
    overview = []

    for eco_id in eco_ids:
        mask = (idx["eco_id"].to_numpy() == eco_id) & (y_full >= 0)
        n = int(mask.sum())
        eco_name = str(idx.loc[idx["eco_id"] == eco_id, "eco_name"].iloc[0])
        eco_dir = out / "by_ecoregion" / f"E{eco_id:02d}"
        eco_dir.mkdir(exist_ok=True)

        if n < args.min_samples_eco:
            overview.append(
                {
                    "eco_id": eco_id,
                    "eco_name": eco_name,
                    "n_samples": n,
                    "status": "SKIP_TOO_FEW_SAMPLES",
                }
            )
            continue

        X = select_bands(X_full[mask], bands)
        y = y_full[mask]
        scores = rank_bands_by_jm(
            X, y, band_indices=bands, band_names=band_names, min_count=args.min_count
        )
        rank = pd.DataFrame(
            [
                {
                    "rank": i,
                    "band_index": s.band_index,
                    "band_name": s.band_name or "",
                    "mean_jm": s.mean_jm,
                    "min_jm": s.min_jm,
                    "n_pairs": s.n_pairs,
                    "n_classes_used": s.n_classes_used,
                }
                for i, s in enumerate(scores, start=1)
            ]
        )
        rank.to_csv(eco_dir / "jm_ranking.csv", index=False)
        selected = [s.band_index for s in scores]
        names = [s.band_name for s in scores if s.band_name]
        bl = band_list_from_indices(
            selected,
            source="jm_refine_ecoregion",
            ecoregion=eco_id,
            year=2015,
            band_names=names if len(names) == len(selected) else None,
        )
        save_band_list(eco_dir / "band_list_jm.json", bl)

        classes, counts = np.unique(y, return_counts=True)
        summary = {
            "eco_id": int(eco_id),
            "eco_name": eco_name,
            "n_samples": int(n),
            "n_bands": int(len(bands)),
            "n_classes": int(len(classes)),
            "class_counts": {
                str(int(c)): {
                    "n": int(k),
                    "name": CLASS_NAMES.get(int(c), "Sin nombre en leyenda"),
                }
                for c, k in zip(classes.tolist(), counts.tolist())
            },
            "top10": [
                {
                    "rank": int(r["rank"]),
                    "band_index": int(r["band_index"]),
                    "band_name": str(r["band_name"]),
                    "mean_jm": float(r["mean_jm"]),
                }
                for _, r in rank.head(10).iterrows()
            ],
            "status": "OK",
        }
        (eco_dir / "jm_summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        _plot_top15(
            rank,
            f"JM E{eco_id} {eco_name}\nn={n} train · 184 bands",
            eco_dir / "jm_top15.png",
        )
        # copy top fig to figures/
        _plot_top15(
            rank,
            f"JM E{eco_id} {eco_name}\nn={n} train · 184 bands",
            out / "figures" / f"E{eco_id:02d}_jm_top15.png",
        )
        overview.append(
            {
                "eco_id": int(eco_id),
                "eco_name": eco_name,
                "n_samples": int(n),
                "n_classes": int(len(classes)),
                "top1_band": str(rank.iloc[0]["band_name"]),
                "top1_mean_jm": float(rank.iloc[0]["mean_jm"]),
                "status": "OK",
            }
        )
        print(f"OK E{eco_id} n={n} top1={rank.iloc[0]['band_name']}")

    ov = pd.DataFrame(overview)
    ov.to_csv(out / "summaries" / "ecoregion_overview.csv", index=False)
    (out / "summaries" / "ecoregion_overview.json").write_text(
        json.dumps(overview, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    # overview figure: top1 JM per eco
    ok = ov[ov["status"] == "OK"].copy()
    if len(ok):
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar([f"E{i}" for i in ok["eco_id"]], ok["top1_mean_jm"], color="#2a6f7a")
        ax.set_ylabel("Top-1 mean JM")
        ax.set_title("Per-ecoregion JM — best band score (184 bands, train)")
        ax.set_ylim(0, 2)
        fig.tight_layout()
        fig.savefig(out / "figures" / "overview_top1_jm_by_eco.png", dpi=140)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar([f"E{i}" for i in ok["eco_id"]], ok["n_samples"], color="#6b5b4a")
        ax.set_ylabel("N train samples")
        ax.set_title("Samples per ecoregion used in JM")
        fig.tight_layout()
        fig.savefig(out / "figures" / "overview_nsamples_by_eco.png", dpi=140)
        plt.close(fig)

    readme = f"""# 184bands_ecorregion — JM por ecorregión (184 bandas)

JM **sin clustering**, una corrida por ecorregión, muestras `train` Col2.

- Matriz: `{args.samples}`
- Salida: `{out}`
- Ecorregiones OK: {int((ov['status']=='OK').sum())} / {len(ov)}

Ver `summaries/ecoregion_overview.csv` y `by_ecoregion/E*/`.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps({"n_eco": len(ov), "n_ok": int((ov["status"] == "OK").sum())}, indent=2))


if __name__ == "__main__":
    main()
