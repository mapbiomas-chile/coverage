"""Cross-tile band cluster consensus via co-association."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform


def accumulate_coassociation(label_rows: list[np.ndarray]) -> np.ndarray:
    """
    Build co-association matrix C[i,j] = fraction of tiles where bands i,j
    share the same local cluster_id.

    ``label_rows``: list of length-n_bands int arrays (one per tile).
    """
    if not label_rows:
        raise ValueError("label_rows is empty")
    n = int(label_rows[0].shape[0])
    for lab in label_rows:
        if lab.shape != (n,):
            raise ValueError(f"label length mismatch: expected {n}, got {lab.shape}")
    C = np.zeros((n, n), dtype=np.float64)
    for lab in label_rows:
        for cid in np.unique(lab):
            members = np.flatnonzero(lab == cid)
            C[np.ix_(members, members)] += 1.0
    C /= float(len(label_rows))
    np.fill_diagonal(C, 1.0)
    C = (C + C.T) / 2.0
    return C


def cluster_from_coassociation(
    coassoc: np.ndarray,
    *,
    coassoc_threshold: float = 0.70,
    linkage_method: str = "average",
) -> dict[str, Any]:
    """
    Hierarchical clustering with distance d = 1 - C, cut at 1 - coassoc_threshold.

    Bands with co-association ≥ threshold tend to land in the same eco-cluster.
    """
    if coassoc.ndim != 2 or coassoc.shape[0] != coassoc.shape[1]:
        raise ValueError(f"coassoc must be square, got {coassoc.shape}")
    n = coassoc.shape[0]
    thr = float(coassoc_threshold)
    if not (0.0 < thr <= 1.0):
        raise ValueError(f"coassoc_threshold must be in (0,1], got {thr}")

    D = 1.0 - np.asarray(coassoc, dtype=np.float64)
    np.fill_diagonal(D, 0.0)
    D = np.clip(D, 0.0, None)
    D = (D + D.T) / 2.0

    distance_threshold = 1.0 - thr
    condensed = squareform(D, checks=False)
    Z = linkage(condensed, method=linkage_method)
    labels_1 = fcluster(Z, t=distance_threshold, criterion="distance")
    labels = (labels_1 - 1).astype(np.int32)

    n_clusters = int(labels.max()) + 1
    sizes = np.bincount(labels, minlength=n_clusters)

    assignment = pd.DataFrame(
        {
            "band_index": np.arange(n, dtype=np.int32),
            "cluster_id": labels,
        }
    )
    clusters = (
        assignment.groupby("cluster_id")["band_index"]
        .apply(lambda s: sorted(int(x) for x in s))
        .reset_index()
    )
    clusters["size"] = clusters["band_index"].apply(len)
    clusters = clusters.rename(columns={"band_index": "bands"})

    # mean pairwise co-association within each multi-member cluster
    mean_c = []
    for bands in clusters["bands"]:
        if len(bands) < 2:
            mean_c.append(1.0)
            continue
        sub = coassoc[np.ix_(bands, bands)]
        iu = np.triu_indices(len(bands), k=1)
        mean_c.append(float(sub[iu].mean()) if iu[0].size else 1.0)
    clusters["mean_coassoc"] = mean_c
    clusters = clusters.sort_values(
        ["size", "mean_coassoc", "cluster_id"], ascending=[False, False, True]
    )

    summary = {
        "n_bands": n,
        "n_clusters": n_clusters,
        "n_singletons": int((sizes == 1).sum()),
        "n_multi": int((sizes > 1).sum()),
        "max_cluster_size": int(sizes.max()) if n_clusters else 0,
        "coassoc_threshold": thr,
        "distance_threshold": float(distance_threshold),
        "linkage": linkage_method,
        "distance": "1 - coassociation",
        "status": "PASS",
    }
    return {
        "labels": labels,
        "linkage_matrix": Z,
        "assignment": assignment,
        "clusters": clusters,
        "summary": summary,
    }


def save_clusters_united(
    result: dict[str, Any],
    coassoc: np.ndarray,
    out_dir: str | Path,
    *,
    band_names: list[str] | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write co-association + eco-level clusters under out_dir."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    assignment: pd.DataFrame = result["assignment"].copy()
    if band_names is not None:
        if len(band_names) != len(assignment):
            raise ValueError("band_names length must match n_bands")
        assignment["band_name"] = band_names

    clusters: pd.DataFrame = result["clusters"]
    summary: dict[str, Any] = dict(result["summary"])
    if extra_meta:
        summary["source"] = extra_meta

    coassoc_path = out_dir / "coassociation.npy"
    assignment_path = out_dir / "band_cluster_assignment.csv"
    clusters_path = out_dir / "eco_clusters.json"
    labels_path = out_dir / "band_cluster_labels.npy"
    summary_path = out_dir / "summary.json"

    np.save(coassoc_path, coassoc)
    np.save(labels_path, result["labels"])
    assignment.to_csv(assignment_path, index=False)

    clusters_payload = []
    for r in clusters.itertuples(index=False):
        bands = list(r.bands)
        names = (
            [band_names[i] if band_names[i] else f"band_{i}" for i in bands]
            if band_names is not None
            else None
        )
        item: dict[str, Any] = {
            "cluster_id": int(r.cluster_id),
            "size": int(r.size),
            "mean_coassoc": float(r.mean_coassoc),
            "bands": bands,
        }
        if names is not None:
            item["band_names"] = names
        clusters_payload.append(item)
    clusters_path.write_text(json.dumps(clusters_payload, indent=2) + "\n")

    summary["out_dir"] = str(out_dir)
    summary["coassociation_npy"] = str(coassoc_path)
    summary["assignment_csv"] = str(assignment_path)
    summary["eco_clusters_json"] = str(clusters_path)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    summary["summary_json"] = str(summary_path)
    return summary
