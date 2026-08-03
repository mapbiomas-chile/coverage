#!/usr/bin/env python3
"""All-Chile correlation clustering (|r|>=0.9) on 184 bands, then JM on representatives.

Does NOT require HPC cluster for n≈7k x 184 — runs locally with modest RAM.
"""
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
from src.selection.corr_cluster import cluster_bands_corr
from src.selection.jm import rank_bands_by_jm


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
        "--band-list",
        type=Path,
        default=Path(
            "/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_all/band_lists/band_list_full_184.json"
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/home/lserey/mapbiomas_land/tmp/JM_test_ME/all_chile_184bands"),
    )
    parser.add_argument(
        "--corr-threshold",
        type=float,
        default=0.9,
        help="|r| threshold equivalent to PE d=0.1 (90%)",
    )
    parser.add_argument("--min-count", type=int, default=20)
    parser.add_argument("--top-k-jm", type=int, default=None)
    args = parser.parse_args()

    out = args.out_dir
    clu_dir = out / "clustering"
    jm_dir = out / "jm_from_clustering"
    fig_dir = out / "figures"
    for d in (clu_dir, jm_dir, fig_dir):
        d.mkdir(parents=True, exist_ok=True)

    data = load_samples(args.samples)
    X, y = data["X"], data["y"]
    valid = y >= 0
    X, y = X[valid], y[valid]

    band_list = load_band_list(args.band_list)
    full_bands = band_list["bands"]
    band_names = band_list.get("band_names") or [f"band_{i}" for i in full_bands]
    X184 = select_bands(X, full_bands)

    print(
        f"Clustering Chile train n={X184.shape[0]} bands={X184.shape[1]} "
        f"|r|>={args.corr_threshold} …"
    )
    result = cluster_bands_corr(X184, corr_threshold=args.corr_threshold)

    # ordered assignment table
    rows = []
    for band_i, lab in enumerate(result.labels):
        rows.append(
            {
                "band_index": int(full_bands[band_i]),
                "band_name": band_names[band_i],
                "cluster_id": int(lab),
                "is_representative": int(full_bands[band_i])
                in {full_bands[r] for r in result.representatives},
                "cluster_size": len(result.clusters[int(lab)]),
            }
        )
    assign = pd.DataFrame(rows).sort_values(["cluster_id", "band_index"])
    assign.to_csv(clu_dir / "band_cluster_assignment.csv", index=False)

    clusters_payload = {
        str(cid): {
            "members": [
                {"band_index": int(full_bands[b]), "band_name": band_names[b]}
                for b in members
            ],
            "representative": {
                "band_index": int(
                    full_bands[
                        next(
                            r
                            for r in result.representatives
                            if r in members
                        )
                    ]
                ),
                "band_name": band_names[
                    next(r for r in result.representatives if r in members)
                ],
            },
            "size": len(members),
        }
        for cid, members in sorted(result.clusters.items())
    }
    (clu_dir / "clusters.json").write_text(
        json.dumps(clusters_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    rep_local = result.representatives  # indices into 184 columns
    rep_global = [int(full_bands[i]) for i in rep_local]
    rep_names = [band_names[i] for i in rep_local]
    reps_df = pd.DataFrame(
        {
            "band_index": rep_global,
            "band_name": rep_names,
            "cluster_id": [int(result.labels[i]) for i in rep_local],
            "cluster_size": [
                len(result.clusters[int(result.labels[i])]) for i in rep_local
            ],
        }
    ).sort_values("band_index")
    reps_df.to_csv(clu_dir / "representatives.csv", index=False)

    bl_clu = band_list_from_indices(
        rep_global,
        source="corr_cluster_r90",
        year=2015,
        band_names=rep_names,
    )
    bl_clu["corr_threshold"] = args.corr_threshold
    bl_clu["distance_threshold"] = result.distance_threshold
    bl_clu["n_clusters"] = len(result.clusters)
    bl_clu["parent_n_bands"] = len(full_bands)
    save_band_list(clu_dir / "band_list_clustering.json", bl_clu)

    summary_clu = {
        "n_samples": int(X184.shape[0]),
        "n_bands_in": len(full_bands),
        "n_clusters": len(result.clusters),
        "n_representatives": len(rep_global),
        "corr_threshold": args.corr_threshold,
        "distance_threshold": result.distance_threshold,
        "distance": "1 - |r|",
        "linkage": "average",
        "n_singletons": int(sum(1 for m in result.clusters.values() if len(m) == 1)),
        "max_cluster_size": int(max(len(m) for m in result.clusters.values())),
        "status": "PASS",
    }
    (clu_dir / "cluster_summary.json").write_text(
        json.dumps(summary_clu, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary_clu, indent=2))

    # cluster size hist
    sizes = [len(m) for m in result.clusters.values()]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(sizes, bins=range(1, max(sizes) + 2), color="#6b5b4a", edgecolor="white", align="left")
    ax.set_xlabel("Cluster size")
    ax.set_ylabel("N clusters")
    ax.set_title(
        f"Band clustering Chile train · |r|>={args.corr_threshold}\n"
        f"{len(result.clusters)} clusters / {len(full_bands)} bands"
    )
    fig.tight_layout()
    fig.savefig(fig_dir / "cluster_size_hist.png", dpi=140)
    plt.close(fig)

    # --- JM on representatives ---
    print(f"JM on {len(rep_global)} clustering representatives …")
    Xrep = select_bands(X, rep_global)
    scores = rank_bands_by_jm(
        Xrep,
        y,
        band_indices=rep_global,
        band_names=rep_names,
        min_count=args.min_count,
    )
    if args.top_k_jm is not None:
        scores_keep = scores[: args.top_k_jm]
    else:
        scores_keep = scores

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
    rank.to_csv(jm_dir / "jm_ranking.csv", index=False)

    sel_idx = [s.band_index for s in scores_keep]
    sel_names = [s.band_name for s in scores_keep]
    bl_jm = band_list_from_indices(
        sel_idx,
        source="jm_after_corr_cluster_r90",
        year=2015,
        band_names=sel_names,
    )
    bl_jm["parent_source"] = "corr_cluster_r90"
    bl_jm["parent_n_bands"] = len(rep_global)
    save_band_list(jm_dir / "band_list_jm.json", bl_jm)

    jm_summary = {
        "n_samples": int(Xrep.shape[0]),
        "n_input_bands": len(rep_global),
        "n_ranked": len(scores),
        "input_source": "corr_cluster_r90",
        "top10": rank.head(10).to_dict(orient="records"),
        "class_counts": {
            str(int(c)): int(n) for c, n in zip(*np.unique(y, return_counts=True))
        },
    }
    (jm_dir / "jm_summary.json").write_text(
        json.dumps(jm_summary, indent=2) + "\n", encoding="utf-8"
    )

    t15 = rank.head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(t15["band_name"], t15["mean_jm"], color="#b86b3d")
    ax.set_xlim(0, 2)
    ax.set_xlabel("Mean pairwise JM (0-2)")
    ax.set_title(
        f"JM after clustering (|r|>={args.corr_threshold})\n"
        f"{len(rep_global)} reps from 184 · Chile train n={Xrep.shape[0]}"
    )
    fig.tight_layout()
    fig.savefig(fig_dir / "jm_top15_after_clustering.png", dpi=140)
    fig.savefig(jm_dir / "jm_top15.png", dpi=140)
    plt.close(fig)

    # compare reduction
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(
        ["Full 184", f"Cluster reps\n(|r|>={args.corr_threshold})"],
        [len(full_bands), len(rep_global)],
        color=["#2a6f7a", "#b86b3d"],
    )
    ax.set_ylabel("N bands")
    ax.set_title("Band reduction via correlation clustering")
    fig.tight_layout()
    fig.savefig(fig_dir / "band_reduction_bar.png", dpi=140)
    plt.close(fig)

    readme = f"""# all_chile_184bands — clustering (|r|≥{args.corr_threshold}) + JM

Pipeline nacional (todas las ecorregiones juntas), muestras `train` Col2.

## Carpetas
- `clustering/` — asignación banda→cluster, representantes, `band_list_clustering.json`
- `jm_from_clustering/` — ranking JM sobre los representantes
- `figures/` — gráficos

## Método clustering (alineado a PE)
- distancia = `1 - |r|`
- umbral distancia = `{result.distance_threshold}` ≡ `|r| ≥ {args.corr_threshold}` (90%)
- linkage = average
- representante = banda más central del cluster (mayor mean |r| a miembros)

## Resultado
- bandas in: {len(full_bands)}
- clusters / representantes: {len(result.clusters)} / {len(rep_global)}
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
