"""Jeffries-Matusita separability ranking for band reduction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class JmBandResult:
    band_index: int
    band_name: str
    mean_jm: float
    min_jm: float
    n_pairs: int
    n_classes_used: int


def bhattacharyya_coefficient(
    mu_a: float,
    mu_b: float,
    var_a: float,
    var_b: float,
    *,
    var_floor: float = 1e-12,
) -> float:
    """Gaussian Bhattacharyya coefficient in [0, 1]."""
    va = max(float(var_a), var_floor)
    vb = max(float(var_b), var_floor)
    s = va + vb
    bc = np.sqrt(2.0 * va * vb / s) * np.exp(-((mu_a - mu_b) ** 2) / (4.0 * s))
    return float(min(max(bc, 0.0), 1.0))


def jm_distance_from_bc(bc: float) -> float:
    """Jeffries-Matusita distance on scale sqrt(2*(1-BC))."""
    bc = min(max(float(bc), 0.0), 1.0)
    return float(np.sqrt(max(2.0 * (1.0 - bc), 0.0)))


def jm_pair(
    xa: np.ndarray,
    xb: np.ndarray,
    *,
    var_floor: float = 1e-12,
) -> float:
    if xa.size < 2 or xb.size < 2:
        return float("nan")
    va = float(np.var(xa, ddof=1))
    vb = float(np.var(xb, ddof=1))
    if va <= 0.0 or vb <= 0.0:
        return float("nan")
    bc = bhattacharyya_coefficient(
        float(np.mean(xa)),
        float(np.mean(xb)),
        va,
        vb,
        var_floor=var_floor,
    )
    return jm_distance_from_bc(bc)


def rank_bands_jm(
    X: np.ndarray,
    y: np.ndarray,
    band_names: list[str],
    *,
    exclude_classes: tuple[int, ...] = (33, 34),
    min_class_n: int = 2,
    var_floor: float = 1e-12,
) -> list[JmBandResult]:
    """Rank bands by mean pairwise JM over classes present in y."""
    if X.shape[1] != len(band_names):
        raise ValueError(f"X has {X.shape[1]} bands but {len(band_names)} names")

    keep = ~np.isin(y, list(exclude_classes))
    X = X[keep]
    y = y[keep]
    classes = np.unique(y)
    if classes.size < 2:
        raise ValueError("Need at least two classes after exclusions")

    results: list[JmBandResult] = []
    for bi, name in enumerate(band_names):
        col = X[:, bi]
        jms: list[float] = []
        for i, ca in enumerate(classes):
            for cb in classes[i + 1 :]:
                xa = col[y == ca]
                xb = col[y == cb]
                if xa.size < min_class_n or xb.size < min_class_n:
                    continue
                jm = jm_pair(xa, xb, var_floor=var_floor)
                if np.isfinite(jm):
                    jms.append(jm)

        if jms:
            results.append(
                JmBandResult(
                    band_index=bi,
                    band_name=name,
                    mean_jm=float(np.mean(jms)),
                    min_jm=float(np.min(jms)),
                    n_pairs=len(jms),
                    n_classes_used=int(classes.size),
                )
            )
        else:
            results.append(
                JmBandResult(
                    band_index=bi,
                    band_name=name,
                    mean_jm=0.0,
                    min_jm=0.0,
                    n_pairs=0,
                    n_classes_used=int(classes.size),
                )
            )

    results.sort(key=lambda r: (-r.mean_jm, r.band_index))
    return results


def jm_results_to_frame(results: list[JmBandResult]) -> pd.DataFrame:
    rows = [
        {
            "rank": rank,
            "band_index": r.band_index,
            "band_name": r.band_name,
            "mean_jm": r.mean_jm,
            "min_jm": r.min_jm,
            "n_pairs": r.n_pairs,
            "n_classes_used": r.n_classes_used,
        }
        for rank, r in enumerate(results, start=1)
    ]
    return pd.DataFrame(rows)


def load_train_samples(
    npz_path: str,
    index_csv: str,
    eco_id: int,
) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    data = np.load(npz_path)
    X = data["X"].astype(np.float64)
    y = data["y"].astype(np.int32)
    idx = pd.read_csv(index_csv)
    if len(idx) != len(X):
        raise ValueError(f"index rows ({len(idx)}) != npz rows ({len(X)})")
    eco_mask = idx["eco_id"].to_numpy() == eco_id
    if not eco_mask.any():
        raise ValueError(f"No samples for eco_id={eco_id}")
    return X[eco_mask], y[eco_mask], idx.loc[eco_mask].reset_index(drop=True)


def class_counts(y: np.ndarray) -> dict[str, int]:
    values, counts = np.unique(y, return_counts=True)
    return {str(int(v)): int(c) for v, c in zip(values, counts)}


def build_band_list(
    ranking: pd.DataFrame,
    *,
    mean_jm_min: float,
) -> dict[str, Any]:
    sel = ranking.loc[ranking["mean_jm"] >= mean_jm_min].sort_values(
        ["mean_jm", "band_index"], ascending=[False, True]
    )
    return {
        "source": "jm_ecoregion_184bands",
        "mean_jm_min": mean_jm_min,
        "bands": sel["band_index"].astype(int).tolist(),
        "band_names": sel["band_name"].tolist(),
    }
