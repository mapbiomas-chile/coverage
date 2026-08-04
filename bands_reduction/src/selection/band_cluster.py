"""Hierarchical clustering of bands from absolute correlation (unsupervised)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform


def cluster_bands_from_corr_abs(
    corr_abs: np.ndarray,
    *,
    distance_threshold: float = 0.10,
    linkage_method: str = "average",
) -> dict[str, Any]:
    """
    Cluster bands with distance d = 1 - |r|, cut at ``distance_threshold``.

    Returns labels (cluster id per band, 0-based contiguous) and summary tables.
    Does not pick representatives.
    """
    if corr_abs.ndim != 2 or corr_abs.shape[0] != corr_abs.shape[1]:
        raise ValueError(f"corr_abs must be square, got {corr_abs.shape}")

    n = corr_abs.shape[0]
    D = 1.0 - np.asarray(corr_abs, dtype=np.float64)
    np.fill_diagonal(D, 0.0)
    D = np.clip(D, 0.0, None)
    D = (D + D.T) / 2.0

    condensed = squareform(D, checks=False)
    Z = linkage(condensed, method=linkage_method)
    # scipy fcluster labels are 1..K
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
    clusters = clusters.sort_values(["size", "cluster_id"], ascending=[False, True])

    summary = {
        "n_bands": n,
        "n_clusters": n_clusters,
        "n_singletons": int((sizes == 1).sum()),
        "n_multi": int((sizes > 1).sum()),
        "max_cluster_size": int(sizes.max()) if n_clusters else 0,
        "distance_threshold": float(distance_threshold),
        "corr_threshold_equiv": float(1.0 - distance_threshold),
        "linkage": linkage_method,
        "distance": "1 - |r|",
        "status": "PASS",
    }
    return {
        "labels": labels,
        "linkage_matrix": Z,
        "assignment": assignment,
        "clusters": clusters,
        "summary": summary,
    }


def save_band_clusters(
    result: dict[str, Any],
    out_dir: str | Path,
    *,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write assignment CSV, clusters JSON, summary JSON (no representatives)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    assignment: pd.DataFrame = result["assignment"]
    clusters: pd.DataFrame = result["clusters"]
    summary: dict[str, Any] = dict(result["summary"])
    if extra_meta:
        summary["source"] = extra_meta

    assignment_path = out_dir / "band_cluster_assignment.csv"
    clusters_path = out_dir / "clusters.json"
    summary_path = out_dir / "cluster_summary.json"
    labels_path = out_dir / "band_cluster_labels.npy"

    assignment.to_csv(assignment_path, index=False)
    np.save(labels_path, result["labels"])

    clusters_payload = [
        {"cluster_id": int(r.cluster_id), "size": int(r.size), "bands": r.bands}
        for r in clusters.itertuples(index=False)
    ]
    clusters_path.write_text(json.dumps(clusters_payload, indent=2) + "\n")

    summary["out_dir"] = str(out_dir)
    summary["assignment_csv"] = str(assignment_path)
    summary["clusters_json"] = str(clusters_path)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    summary["summary_json"] = str(summary_path)
    return summary
