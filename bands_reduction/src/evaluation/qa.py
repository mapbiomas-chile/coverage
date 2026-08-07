"""RF cross-validation QA for band subset lists."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, cohen_kappa_score
from sklearn.model_selection import StratifiedKFold, cross_validate

from src.evaluation.jm import load_train_samples


def load_col2_eco(
    npz_path: str | Path,
    index_csv: str | Path,
    eco_id: int,
    *,
    exclude_classes: tuple[int, ...] = (33, 34),
) -> tuple[np.ndarray, np.ndarray]:
    """Load Col2 NPZ rows for one ecorregión."""
    X, y, idx = load_train_samples(str(npz_path), str(index_csv), eco_id)
    if exclude_classes:
        keep = ~idx["class"].isin(list(exclude_classes)).to_numpy()
        X = X[keep]
        y = y[keep]
    return X, y


def run_rf_holdout(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    band_indices: list[int],
    *,
    n_estimators: int = 200,
    n_jobs: int = 8,
    random_state: int = 42,
) -> dict[str, float]:
    rf = RandomForestClassifier(
        n_estimators=n_estimators,
        n_jobs=n_jobs,
        random_state=random_state,
        class_weight="balanced",
    )
    X_tr = X_train[:, band_indices]
    X_va = X_val[:, band_indices]
    rf.fit(X_tr, y_train)
    pred = rf.predict(X_va)
    return {
        "oa": float(accuracy_score(y_val, pred)),
        "kappa": float(cohen_kappa_score(y_val, pred)),
        "n_train": int(X_tr.shape[0]),
        "n_val": int(X_va.shape[0]),
    }


def evaluate_holdout_band_sets(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    band_sets: dict[str, list[int]],
    *,
    n_estimators: int,
    n_jobs: int,
    random_state: int,
) -> list[dict[str, Any]]:
    baseline = run_rf_holdout(
        X_train,
        y_train,
        X_val,
        y_val,
        band_sets["baseline_184"],
        n_estimators=n_estimators,
        n_jobs=n_jobs,
        random_state=random_state,
    )
    rows: list[dict[str, Any]] = []
    for name, indices in band_sets.items():
        m = run_rf_holdout(
            X_train,
            y_train,
            X_val,
            y_val,
            indices,
            n_estimators=n_estimators,
            n_jobs=n_jobs,
            random_state=random_state,
        )
        rows.append(
            {
                "list_name": name,
                "n_bands": len(indices),
                "oa_val": m["oa"],
                "kappa_val": m["kappa"],
                "n_train": m["n_train"],
                "n_val": m["n_val"],
                "delta_oa_vs_184": m["oa"] - baseline["oa"],
                "delta_kappa_vs_184": m["kappa"] - baseline["kappa"],
            }
        )
    return rows


def load_representatives(path: Path) -> list[int]:
    payload = json.loads(path.read_text())
    return [int(i) for i in payload["representatives"]]


def jm_top_indices(jm_csv: Path, n: int) -> list[int]:
    df = pd.read_csv(jm_csv).sort_values("mean_jm", ascending=False).head(n)
    return df["band_index"].astype(int).tolist()


def boruta_top_indices(boruta_csv: Path, n: int) -> list[int]:
    df = pd.read_csv(boruta_csv).sort_values(["hit_rate", "mean_importance"], ascending=False).head(n)
    return df["band_index"].astype(int).tolist()


def triple_indices(unsup: list[int], jm: list[int], boruta: list[int]) -> list[int]:
    s = set(unsup) & set(jm) & set(boruta)
    return sorted(s)


def nucleo_union_indices(results_dir: Path, eco_ids: tuple[int, ...] = (2, 3)) -> list[int]:
    triples: list[set[int]] = []
    for eco_id in eco_ids:
        rep_path = (
            results_dir
            / f"E{eco_id}"
            / "2015"
            / "eco_merged"
            / "0.90"
            / "representatives"
            / "representatives.json"
        )
        unsup = load_representatives(rep_path)
        n = len(unsup)
        jm = jm_top_indices(
            results_dir
            / "JM_test_PE"
            / "184bands_ecorregion_stratified"
            / f"E{eco_id:02d}"
            / "jm_ranking.csv",
            n,
        )
        bor = boruta_top_indices(
            results_dir / "Boruta_PE" / f"E{eco_id:02d}_reps095" / "boruta_decisions.csv",
            n,
        )
        triples.append(set(triple_indices(unsup, jm, bor)))
    return sorted(set.union(*triples))


def build_pilot_band_sets(results_dir: Path, eco_id: int) -> dict[str, list[int]]:
    """Band lists for QA pilot: baseline, unsup, jm/boruta top-N, nucleo, nucleo_union."""
    rep_path = (
        results_dir
        / f"E{eco_id}"
        / "2015"
        / "eco_merged"
        / "0.90"
        / "representatives"
        / "representatives.json"
    )
    unsup = load_representatives(rep_path)
    n = len(unsup)
    jm = jm_top_indices(
        results_dir
        / "JM_test_PE"
        / "184bands_ecorregion_stratified"
        / f"E{eco_id:02d}"
        / "jm_ranking.csv",
        n,
    )
    bor = boruta_top_indices(
        results_dir / "Boruta_PE" / f"E{eco_id:02d}_reps095" / "boruta_decisions.csv",
        n,
    )
    union67 = nucleo_union_indices(results_dir, eco_ids=(2, 3))

    return {
        "baseline_184": list(range(184)),
        "unsup_090": unsup,
        "jm_topN": jm,
        "boruta_topN": bor,
        "nucleo_triple": triple_indices(unsup, jm, bor),
        "nucleo_union_E2E3": union67,
    }


def run_rf_cv(
    X: np.ndarray,
    y: np.ndarray,
    band_indices: list[int],
    *,
    n_folds: int = 5,
    n_estimators: int = 200,
    n_jobs: int = 8,
    random_state: int = 42,
) -> dict[str, float]:
    X_sub = X[:, band_indices]
    rf = RandomForestClassifier(
        n_estimators=n_estimators,
        n_jobs=n_jobs,
        random_state=random_state,
        class_weight="balanced",
    )
    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=random_state)
    scores = cross_validate(
        rf,
        X_sub,
        y,
        cv=cv,
        scoring=("accuracy",),
        n_jobs=1,
        return_train_score=False,
    )
    oa_mean = float(np.mean(scores["test_accuracy"]))
    oa_std = float(np.std(scores["test_accuracy"]))

    # Kappa per fold (cross_validate has no built-in kappa with sklearn easily for multiclass - compute manually)
    kappas: list[float] = []
    for train_idx, test_idx in cv.split(X_sub, y):
        rf.fit(X_sub[train_idx], y[train_idx])
        pred = rf.predict(X_sub[test_idx])
        kappas.append(float(cohen_kappa_score(y[test_idx], pred)))

    return {
        "oa_mean": oa_mean,
        "oa_std": oa_std,
        "kappa_mean": float(np.mean(kappas)),
        "kappa_std": float(np.std(kappas)),
    }


def evaluate_band_sets(
    X: np.ndarray,
    y: np.ndarray,
    band_sets: dict[str, list[int]],
    *,
    n_folds: int,
    n_estimators: int,
    n_jobs: int,
    random_state: int,
) -> list[dict[str, Any]]:
    baseline_key = "baseline_184"
    baseline = run_rf_cv(
        X,
        y,
        band_sets[baseline_key],
        n_folds=n_folds,
        n_estimators=n_estimators,
        n_jobs=n_jobs,
        random_state=random_state,
    )
    rows: list[dict[str, Any]] = []
    for name, indices in band_sets.items():
        metrics = run_rf_cv(
            X,
            y,
            indices,
            n_folds=n_folds,
            n_estimators=n_estimators,
            n_jobs=n_jobs,
            random_state=random_state,
        )
        rows.append(
            {
                "list_name": name,
                "n_bands": len(indices),
                "oa_mean": metrics["oa_mean"],
                "oa_std": metrics["oa_std"],
                "kappa_mean": metrics["kappa_mean"],
                "kappa_std": metrics["kappa_std"],
                "delta_oa_vs_184": metrics["oa_mean"] - baseline["oa_mean"],
                "delta_kappa_vs_184": metrics["kappa_mean"] - baseline["kappa_mean"],
            }
        )
    return rows
