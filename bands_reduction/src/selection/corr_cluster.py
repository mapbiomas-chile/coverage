"""Correlation-based band clustering (PE-compatible: distance = 1-|r|, threshold 0.1 ≡ |r|≥0.9)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform


@dataclass
class ClusterResult:
    corr_abs: np.ndarray
    distance_matrix: np.ndarray
    labels: np.ndarray  # cluster id per band (1..K)
    representatives: list[int]  # band indices
    clusters: dict[int, list[int]]  # cluster_id -> member band indices
    distance_threshold: float
    corr_threshold: float


def absolute_corr(X: np.ndarray) -> np.ndarray:
    """Pearson |r| across columns (bands). NaNs handled via pairwise complete columns."""
    X = np.asarray(X, dtype=np.float64)
    # replace non-finite with nan then use np.corrcoef after column-wise nanmean fill? better:
    # drop rows with any nan for simplicity if rare; else column standardize with nan
    finite_rows = np.isfinite(X).all(axis=1)
    Xc = X[finite_rows]
    if Xc.shape[0] < 3:
        raise ValueError(f"Too few finite rows for correlation: {Xc.shape[0]}")
    c = np.corrcoef(Xc, rowvar=False)
    c = np.nan_to_num(c, nan=0.0)
    np.fill_diagonal(c, 1.0)
    return np.abs(c)


def cluster_bands_corr(
    X: np.ndarray,
    *,
    corr_threshold: float = 0.9,
    linkage_method: str = "average",
) -> ClusterResult:
    """Hierarchical clustering on distance = 1 - |r|, cut at (1 - corr_threshold)."""
    corr_abs = absolute_corr(X)
    dist = 1.0 - corr_abs
    np.fill_diagonal(dist, 0.0)
    # numerical symmetry
    dist = (dist + dist.T) * 0.5
    condensed = squareform(dist, checks=False)
    Z = linkage(condensed, method=linkage_method)
    d_thresh = 1.0 - float(corr_threshold)
    labels = fcluster(Z, t=d_thresh, criterion="distance")

    clusters: dict[int, list[int]] = {}
    for band_i, lab in enumerate(labels):
        clusters.setdefault(int(lab), []).append(int(band_i))

    # representative = band with highest mean |r| to other members (central)
    representatives: list[int] = []
    for lab, members in sorted(clusters.items()):
        if len(members) == 1:
            representatives.append(members[0])
            continue
        sub = corr_abs[np.ix_(members, members)]
        # mean abs corr to others (exclude self)
        scores = []
        for i, _b in enumerate(members):
            row = sub[i].copy()
            row[i] = np.nan
            scores.append(np.nanmean(row))
        representatives.append(members[int(np.nanargmax(scores))])

    representatives = sorted(set(representatives))
    return ClusterResult(
        corr_abs=corr_abs,
        distance_matrix=dist,
        labels=labels.astype(np.int32),
        representatives=representatives,
        clusters=clusters,
        distance_threshold=d_thresh,
        corr_threshold=float(corr_threshold),
    )
