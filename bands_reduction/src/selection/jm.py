"""Jeffries-Matusita (JM) separability for band ranking / refinement."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class JMBandScore:
    band_index: int
    band_name: str | None
    mean_jm: float
    min_jm: float
    n_pairs: int
    n_classes_used: int


def bhattacharyya_univariate(mu1: float, var1: float, mu2: float, var2: float) -> float:
    """Bhattacharyya distance for two univariate Gaussians."""
    v1 = max(float(var1), 1e-12)
    v2 = max(float(var2), 1e-12)
    mean_var = 0.5 * (v1 + v2)
    term_mean = 0.125 * ((mu1 - mu2) ** 2) / mean_var
    term_cov = 0.5 * np.log(mean_var / np.sqrt(v1 * v2))
    return float(term_mean + term_cov)


def jeffries_matusita_from_b(b: float) -> float:
    """JM = 2 * (1 - exp(-B)); range [0, 2]."""
    return float(2.0 * (1.0 - np.exp(-b)))


def pairwise_jm_univariate(x: np.ndarray, y: np.ndarray, min_count: int = 20) -> dict:
    """Mean / min JM across class pairs for a single feature column."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y)
    mask = np.isfinite(x) & (y >= 0)
    x = x[mask]
    y = y[mask]

    classes = np.unique(y)
    stats: dict[int, tuple[float, float, int]] = {}
    for c in classes:
        xc = x[y == c]
        if xc.size < min_count:
            continue
        stats[int(c)] = (float(xc.mean()), float(xc.var(ddof=1)), int(xc.size))

    used = sorted(stats.keys())
    if len(used) < 2:
        return {
            "mean_jm": 0.0,
            "min_jm": 0.0,
            "n_pairs": 0,
            "n_classes_used": len(used),
        }

    jms: list[float] = []
    for i, c1 in enumerate(used):
        mu1, v1, _ = stats[c1]
        for c2 in used[i + 1 :]:
            mu2, v2, _ = stats[c2]
            b = bhattacharyya_univariate(mu1, v1, mu2, v2)
            jms.append(jeffries_matusita_from_b(b))

    arr = np.asarray(jms, dtype=np.float64)
    return {
        "mean_jm": float(arr.mean()) if arr.size else 0.0,
        "min_jm": float(arr.min()) if arr.size else 0.0,
        "n_pairs": int(arr.size),
        "n_classes_used": len(used),
    }


def rank_bands_by_jm(
    X: np.ndarray,
    y: np.ndarray,
    band_indices: list[int] | None = None,
    band_names: list[str] | None = None,
    min_count: int = 20,
) -> list[JMBandScore]:
    """Rank candidate bands by mean pairwise univariate JM.

    If band_indices is None, all columns of X are ranked as 0..n-1.
    If band_indices is provided, X is assumed to already be subset to those
    columns in the same order (len(band_indices) == X.shape[1]).
    """
    X = np.asarray(X)
    y = np.asarray(y)
    n_feat = X.shape[1]
    if band_indices is None:
        band_indices = list(range(n_feat))
    if len(band_indices) != n_feat:
        raise ValueError(
            f"band_indices length {len(band_indices)} != X columns {n_feat}"
        )

    scores: list[JMBandScore] = []
    for j, bidx in enumerate(band_indices):
        name = None
        if band_names is not None:
            name = band_names[j]
        stats = pairwise_jm_univariate(X[:, j], y, min_count=min_count)
        scores.append(
            JMBandScore(
                band_index=int(bidx),
                band_name=name,
                mean_jm=stats["mean_jm"],
                min_jm=stats["min_jm"],
                n_pairs=stats["n_pairs"],
                n_classes_used=stats["n_classes_used"],
            )
        )
    scores.sort(key=lambda s: (s.mean_jm, s.min_jm), reverse=True)
    return scores


def filter_bands_by_jm(
    scores: list[JMBandScore],
    *,
    top_k: int | None = None,
    min_mean_jm: float | None = None,
) -> list[JMBandScore]:
    out = list(scores)
    if min_mean_jm is not None:
        out = [s for s in out if s.mean_jm >= min_mean_jm]
    if top_k is not None:
        out = out[:top_k]
    return out
