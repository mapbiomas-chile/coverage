"""Boruta feature selection wrapper (Random Forest + shadow features)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from boruta import BorutaPy
from sklearn.ensemble import RandomForestClassifier

from src.evaluation.jm import class_counts, load_train_samples


ECO_NAMES = {
    1: "E1_Puna_seca_andina",
    2: "E2_Desierto_Atacama",
    3: "E3_Matorral_norte_1",
    4: "E4_Estepa_andina",
    5: "E5_Matorral_norte_2",
    6: "E6_Andes_norte",
    7: "E7_Andes_central",
    8: "E8_Matorral_sur",
    9: "E9_Costa_norte",
    10: "E10_Andes_sur",
    11: "E11_Costa_sur_1",
    12: "E12_Costa_sur_2",
    13: "E13_Andes_sur_costa",
    14: "E14_Estepa_patagonica",
    15: "E15_Bosque_subpolar",
}


@dataclass(frozen=True)
class BorutaParams:
    max_iter: int = 50
    n_estimators: int = 200
    perc: float = 95.0
    alpha: float = 0.05
    tentative_min_hit_rate: float = 0.40
    random_state: int = 42
    n_jobs: int = 8


class TrackedBorutaPy(BorutaPy):
    """BorutaPy that records per-iteration importances and shadow thresholds."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._imp_per_iter: list[np.ndarray] = []
        self._sha_max_per_iter: list[float] = []

    def _add_shadows_get_imps(self, X: np.ndarray, y: np.ndarray, dec_reg: np.ndarray) -> tuple:
        cur_imp = super()._add_shadows_get_imps(X, y, dec_reg)
        self._imp_per_iter.append(cur_imp[0].copy())
        self._sha_max_per_iter.append(float(np.percentile(cur_imp[1], self.perc)))
        return cur_imp

    def hit_reg(self) -> np.ndarray:
        if not self._imp_per_iter:
            raise ValueError("TrackedBorutaPy has not been fit yet")
        n_feat = self._imp_per_iter[0].size
        hits = np.zeros(n_feat, dtype=int)
        for imp_row, sha_max in zip(self._imp_per_iter, self._sha_max_per_iter):
            imp_row = np.nan_to_num(imp_row, nan=0.0)
            hits[np.where(imp_row > sha_max)[0]] += 1
        return hits

    @property
    def n_iters_run(self) -> int:
        return len(self._imp_per_iter)

    @property
    def mean_shadow_max(self) -> float:
        if not self._sha_max_per_iter:
            return float("nan")
        return float(np.mean(self._sha_max_per_iter))


def load_representatives(representatives_json: str | Path) -> list[int]:
    payload = json.loads(Path(representatives_json).read_text())
    reps = payload.get("representatives") or payload.get("bands")
    if reps is None:
        raise ValueError(f"No representatives list in {representatives_json}")
    return [int(i) for i in reps]


def stratified_subsample(
    X: np.ndarray,
    y: np.ndarray,
    *,
    max_samples: int,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Cap sample count with per-class proportional subsampling."""
    n = X.shape[0]
    if n <= max_samples:
        return X, y
    rng = np.random.default_rng(random_state)
    classes, counts = np.unique(y, return_counts=True)
    frac = max_samples / n
    picked: list[np.ndarray] = []
    for cls, cnt in zip(classes, counts):
        idx = np.where(y == cls)[0]
        k = max(1, int(round(cnt * frac)))
        k = min(k, idx.size)
        picked.append(rng.choice(idx, size=k, replace=False))
    sel = np.sort(np.concatenate(picked))
    if sel.size > max_samples:
        sel = np.sort(rng.choice(sel, size=max_samples, replace=False))
    return X[sel], y[sel]


def run_boruta_selection(
    X: np.ndarray,
    y: np.ndarray,
    band_indices: list[int],
    band_names: list[str],
    *,
    params: BorutaParams | None = None,
) -> tuple[TrackedBorutaPy, pd.DataFrame]:
    """Run Boruta and return selector + per-band decision table."""
    if len(band_indices) != len(band_names):
        raise ValueError("band_indices and band_names length mismatch")
    if X.shape[1] != len(band_indices):
        raise ValueError(f"X has {X.shape[1]} columns but {len(band_indices)} bands")

    params = params or BorutaParams()
    rf = RandomForestClassifier(
        n_estimators=params.n_estimators,
        n_jobs=params.n_jobs,
        random_state=params.random_state,
        class_weight="balanced",
    )
    selector = TrackedBorutaPy(
        rf,
        n_estimators=params.n_estimators,
        max_iter=params.max_iter,
        perc=params.perc,
        alpha=params.alpha,
        random_state=params.random_state,
        verbose=0,
    )
    selector.fit(X, y)

    hits = selector.hit_reg()
    n_iters = selector.n_iters_run
    mean_shadow = selector.mean_shadow_max
    imp_hist = selector.importance_history_[1:]
    mean_imp = imp_hist.mean(axis=0) if imp_hist.size else np.zeros(X.shape[1])

    rows: list[dict[str, Any]] = []
    for j, (bi, name) in enumerate(zip(band_indices, band_names)):
        if selector.support_[j]:
            decision = "confirmed"
        elif selector.support_weak_[j]:
            decision = "tentative"
        else:
            decision = "rejected"
        hit_rate = float(hits[j] / n_iters) if n_iters else 0.0
        kept = int(
            decision == "confirmed"
            or (decision == "tentative" and hit_rate >= params.tentative_min_hit_rate)
        )
        rows.append(
            {
                "band_index": int(bi),
                "band_name": name,
                "decision": decision,
                "kept_in_band_list": kept,
                "n_hits": int(hits[j]),
                "n_iters": int(n_iters),
                "hit_rate": hit_rate,
                "mean_importance": float(mean_imp[j]),
                "mean_shadow_max": mean_shadow,
            }
        )

    df = pd.DataFrame(rows).sort_values(
        ["kept_in_band_list", "hit_rate", "mean_importance", "band_index"],
        ascending=[False, False, False, True],
    )
    return selector, df


def build_band_list_boruta(
    decisions: pd.DataFrame,
    *,
    eco_id: int,
    year: int,
    params: BorutaParams,
    parent_source: str,
    parent_n_bands: int,
    exclude_classes: list[int],
    selector: TrackedBorutaPy,
) -> dict[str, Any]:
    kept = decisions.loc[decisions["kept_in_band_list"] == 1].sort_values(
        ["hit_rate", "mean_importance", "band_index"], ascending=[False, False, True]
    )
    n_conf = int((decisions["decision"] == "confirmed").sum())
    n_tent = int((decisions["decision"] == "tentative").sum())
    n_rej = int((decisions["decision"] == "rejected").sum())
    n_tent_kept = int(
        (
            (decisions["decision"] == "tentative")
            & (decisions["hit_rate"] >= params.tentative_min_hit_rate)
        ).sum()
    )
    return {
        "source": "boruta",
        "bands": kept["band_index"].astype(int).tolist(),
        "ecoregion": eco_id,
        "year": year,
        "band_names": kept["band_name"].tolist(),
        "parent_source": parent_source,
        "parent_n_bands": parent_n_bands,
        "split": "train",
        "exclude_classes": exclude_classes,
        "tentative_min_hit_rate": params.tentative_min_hit_rate,
        "boruta": {
            "n_iters": selector.n_iters_run,
            "perc": params.perc,
            "alpha": params.alpha,
            "n_estimators": params.n_estimators,
            "random_state": params.random_state,
            "n_confirmed": n_conf,
            "n_tentative": n_tent,
            "n_rejected": n_rej,
            "n_tentative_kept": n_tent_kept,
            "n_tentative_dropped_weak": n_tent - n_tent_kept,
            "n_kept_total": int(len(kept)),
        },
    }


def build_boruta_summary(
    *,
    eco_id: int,
    n_samples: int,
    y: np.ndarray,
    exclude_classes: list[int],
    band_indices: list[int],
    corr_threshold_parent: float | None,
    params: BorutaParams,
    decisions: pd.DataFrame,
    selector: TrackedBorutaPy,
    samples_npz: str,
    samples_index: str,
    sample_set: str,
    representatives_json: str | None,
    parent_source: str,
    out_dir: Path,
) -> dict[str, Any]:
    kept = decisions.loc[decisions["kept_in_band_list"] == 1]
    return {
        "eco_id": eco_id,
        "eco_name": ECO_NAMES.get(eco_id, f"E{eco_id}"),
        "status": "OK",
        "n_samples": int(n_samples),
        "n_classes": int(np.unique(y).size),
        "class_counts": class_counts(y),
        "n_input_bands": len(band_indices),
        "corr_threshold_parent": corr_threshold_parent,
        "exclude_classes": exclude_classes,
        "split": "train",
        "n_confirmed": int((decisions["decision"] == "confirmed").sum()),
        "n_tentative": int((decisions["decision"] == "tentative").sum()),
        "n_rejected": int((decisions["decision"] == "rejected").sum()),
        "n_tentative_kept_hitrate_ge": int(len(kept) - (decisions["decision"] == "confirmed").sum()),
        "tentative_min_hit_rate": params.tentative_min_hit_rate,
        "n_kept_total": int(len(kept)),
        "n_iters": selector.n_iters_run,
        "params": {
            "max_iter": params.max_iter,
            "n_estimators": params.n_estimators,
            "perc": params.perc,
            "alpha": params.alpha,
            "n_jobs": params.n_jobs,
            "random_state": params.random_state,
        },
        "parent_source": parent_source,
        "representatives_json": representatives_json,
        "samples_npz": samples_npz,
        "samples_index": samples_index,
        "sample_set": sample_set,
        "decisions_csv": str(out_dir / "boruta_decisions.csv"),
        "band_list_boruta": str(out_dir / "band_list_boruta.json"),
        "note": (
            "Confirmed always kept. Tentative kept only if hit_rate >= "
            f"{params.tentative_min_hit_rate} (strict). Weak tentatives listed in CSV only."
        ),
    }


def prepare_eco_matrix(
    samples_npz: str,
    samples_index: str,
    eco_id: int,
    *,
    exclude_classes: tuple[int, ...],
    max_samples: int | None,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    X, y, _idx = load_train_samples(samples_npz, samples_index, eco_id)
    keep = ~np.isin(y, list(exclude_classes))
    X = X[keep]
    y = y[keep]
    if max_samples is not None:
        X, y = stratified_subsample(X, y, max_samples=max_samples, random_state=random_state)
    if np.unique(y).size < 2:
        raise ValueError(f"Need >=2 classes for eco_id={eco_id} after exclusions")
    return X, y
