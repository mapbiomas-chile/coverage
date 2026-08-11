"""RF cross-validation QA for band subset lists."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, cohen_kappa_score, confusion_matrix
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
    return_pred: bool = False,
) -> dict[str, Any]:
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
    out: dict[str, Any] = {
        "oa": float(accuracy_score(y_val, pred)),
        "kappa": float(cohen_kappa_score(y_val, pred)),
        "n_train": int(X_tr.shape[0]),
        "n_val": int(X_va.shape[0]),
    }
    if return_pred:
        out["y_true"] = y_val
        out["y_pred"] = pred
    return out


def confusion_matrix_frame(y_true: np.ndarray, y_pred: np.ndarray) -> pd.DataFrame:
    labels = sorted({int(v) for v in np.unique(y_true)} | {int(v) for v in np.unique(y_pred)})
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    index = [f"true_{c}" for c in labels]
    columns = [f"pred_{c}" for c in labels]
    return pd.DataFrame(cm, index=index, columns=columns)


def classification_report_dict(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    labels = sorted({int(v) for v in np.unique(y_true)} | {int(v) for v in np.unique(y_pred)})
    report = classification_report(
        y_true,
        y_pred,
        labels=labels,
        output_dict=True,
        zero_division=0,
    )
    return {"labels": labels, "report": report}


def plot_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    out_png: Path,
    *,
    title: str,
    normalize: str = "true",
) -> pd.DataFrame:
    """Save row-normalized confusion heatmap (counts annotated)."""
    labels = sorted({int(v) for v in np.unique(y_true)} | {int(v) for v in np.unique(y_pred)})
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    if normalize == "true":
        denom = cm.sum(axis=1, keepdims=True)
        display = np.divide(cm, denom, where=denom > 0, out=np.zeros_like(cm, dtype=float))
        cbar_label = "Fracción por fila (referencia)"
    else:
        display = cm.astype(float)
        cbar_label = "Conteo"

    label_str = [str(c) for c in labels]
    fig_w = max(6.0, 0.55 * len(labels) + 2.5)
    fig_h = max(5.0, 0.55 * len(labels) + 2.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(display, cmap="Blues", vmin=0.0, vmax=1.0 if normalize == "true" else None)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(label_str, rotation=45, ha="right")
    ax.set_yticklabels(label_str)
    ax.set_xlabel("Predicción (clase MapBiomas)")
    ax.set_ylabel("Referencia (gpkg val)")
    ax.set_title(title)

    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            count = int(cm[i, j])
            frac = display[i, j]
            if normalize == "true":
                text = f"{count}\n({frac:.0%})" if count else ""
            else:
                text = str(count) if count else ""
            if text:
                color = "white" if display[i, j] > 0.55 else "black"
                ax.text(j, i, text, ha="center", va="center", color=color, fontsize=8)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=cbar_label)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return confusion_matrix_frame(y_true, y_pred)


def save_holdout_confusion(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    band_indices: list[int],
    out_stem: Path,
    *,
    list_name: str,
    eco_id: int,
    n_estimators: int = 200,
    n_jobs: int = 8,
    random_state: int = 42,
) -> dict[str, Any]:
    """Train RF hold-out, write CM csv/png + classification report json."""
    metrics = run_rf_holdout(
        X_train,
        y_train,
        X_val,
        y_val,
        band_indices,
        n_estimators=n_estimators,
        n_jobs=n_jobs,
        random_state=random_state,
        return_pred=True,
    )
    y_true = metrics.pop("y_true")
    y_pred = metrics.pop("y_pred")
    out_stem.parent.mkdir(parents=True, exist_ok=True)

    plot_confusion_matrix(
        y_true,
        y_pred,
        out_stem.with_suffix(".png"),
        title=f"E{eco_id} val Col2 — {list_name} (n={len(band_indices)} bandas, OA={metrics['oa']:.3f})",
        normalize="true",
    )
    confusion_matrix_frame(y_true, y_pred).to_csv(out_stem.with_suffix(".csv"))

    meta = {
        "eco_id": eco_id,
        "list_name": list_name,
        "n_bands": len(band_indices),
        **metrics,
        "classification_report": classification_report_dict(y_true, y_pred),
    }
    out_stem.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


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
        if not indices:
            rows.append(
                {
                    "list_name": name,
                    "n_bands": 0,
                    "oa_val": float("nan"),
                    "kappa_val": float("nan"),
                    "n_train": int(X_train.shape[0]),
                    "n_val": int(X_val.shape[0]),
                    "delta_oa_vs_184": float("nan"),
                    "delta_kappa_vs_184": float("nan"),
                }
            )
            continue
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


def representatives_path(results_dir: Path, eco_id: int, corr_threshold: str) -> Path:
    return (
        results_dir
        / f"E{eco_id}"
        / "2015"
        / "eco_merged"
        / corr_threshold
        / "representatives"
        / "representatives.json"
    )


def resolve_jm_ranking_csv(results_dir: Path, eco_id: int) -> Path:
    candidates = [
        results_dir / "JM" / "184bands_ecorregion" / f"E{eco_id:02d}" / "jm_ranking.csv",
        results_dir / "JM_test_PE" / "184bands_ecorregion_stratified" / f"E{eco_id:02d}" / "jm_ranking.csv",
        results_dir / "JM_test_PE" / "184bands_ecorregion" / f"E{eco_id:02d}" / "jm_ranking.csv",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"JM ranking not found for E{eco_id:02d} under {results_dir}")


def resolve_boruta_decisions_csv(results_dir: Path, eco_id: int) -> Path:
    candidates = [
        results_dir / "Boruta" / f"E{eco_id:02d}_all184" / "boruta_decisions.csv",
        results_dir / "Boruta_PE" / f"E{eco_id:02d}_all184" / "boruta_decisions.csv",
        results_dir / "Boruta_PE" / f"E{eco_id:02d}_reps095" / "boruta_decisions.csv",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"Boruta decisions not found for E{eco_id:02d} under {results_dir}")


def build_method_band_sets(
    results_dir: Path,
    eco_id: int,
    *,
    corr_threshold: str = "0.95",
) -> dict[str, list[int]]:
    """Per-method band lists: baseline + unsup @corr_threshold + JM/Boruta top-N (N = |unsup|)."""
    rep_path = representatives_path(results_dir, eco_id, corr_threshold)
    unsup = load_representatives(rep_path)
    n = len(unsup)
    jm = jm_top_indices(resolve_jm_ranking_csv(results_dir, eco_id), n)
    bor = boruta_top_indices(resolve_boruta_decisions_csv(results_dir, eco_id), n)
    unsup_key = f"unsup_{corr_threshold.replace('.', '')}"

    return {
        "baseline_184": list(range(184)),
        unsup_key: unsup,
        "jm_topN": jm,
        "boruta_topN": bor,
        "nucleo_triple": triple_indices(unsup, jm, bor),
        "pool_union": sorted(set(unsup) | set(jm) | set(bor)),
    }


def nucleo_union_indices(
    results_dir: Path,
    eco_ids: tuple[int, ...] = (2, 3),
    *,
    corr_threshold: str = "0.90",
) -> list[int]:
    triples: list[set[int]] = []
    for eco_id in eco_ids:
        unsup = load_representatives(representatives_path(results_dir, eco_id, corr_threshold))
        n = len(unsup)
        jm = jm_top_indices(resolve_jm_ranking_csv(results_dir, eco_id), n)
        bor = boruta_top_indices(resolve_boruta_decisions_csv(results_dir, eco_id), n)
        triples.append(set(triple_indices(unsup, jm, bor)))
    return sorted(set.union(*triples))


def build_pilot_band_sets(results_dir: Path, eco_id: int) -> dict[str, list[int]]:
    """Band lists for QA pilot: baseline, unsup, jm/boruta top-N, nucleo, nucleo_union."""
    corr_threshold = "0.90"
    rep_path = representatives_path(results_dir, eco_id, corr_threshold)
    unsup = load_representatives(rep_path)
    n = len(unsup)
    jm = jm_top_indices(resolve_jm_ranking_csv(results_dir, eco_id), n)
    bor = boruta_top_indices(resolve_boruta_decisions_csv(results_dir, eco_id), n)
    union67 = nucleo_union_indices(results_dir, eco_ids=(2, 3), corr_threshold=corr_threshold)

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
