"""Boruta wrapper for band relevance confirmation (pipeline stage 3).

Self-contained implementation (no `boruta` PyPI package required): shadow
features + RandomForest importances + binomial hit test.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import binom
from sklearn.ensemble import RandomForestClassifier


@dataclass
class BorutaBandResult:
    band_index: int
    band_name: str | None
    decision: str  # confirmed | tentative | rejected
    n_hits: int
    n_iters: int
    hit_rate: float
    mean_importance: float
    mean_shadow_max: float


@dataclass
class BorutaResult:
    band_results: list[BorutaBandResult]
    n_iters: int
    perc: float
    alpha: float
    n_estimators: int
    random_state: int

    @property
    def confirmed(self) -> list[BorutaBandResult]:
        return [b for b in self.band_results if b.decision == "confirmed"]

    @property
    def tentative(self) -> list[BorutaBandResult]:
        return [b for b in self.band_results if b.decision == "tentative"]

    @property
    def rejected(self) -> list[BorutaBandResult]:
        return [b for b in self.band_results if b.decision == "rejected"]


def run_boruta(
    X: np.ndarray,
    y: np.ndarray,
    band_indices: list[int] | None = None,
    band_names: list[str] | None = None,
    *,
    n_estimators: int = 200,
    max_iter: int = 50,
    perc: float = 100.0,
    alpha: float = 0.05,
    random_state: int = 42,
    n_jobs: int = 4,
    class_weight: str | dict | None = "balanced_subsample",
) -> BorutaResult:
    """Run Boruta feature selection.

    Parameters
    ----------
    X : (n_samples, n_features)
    y : (n_samples,) class labels
    band_indices : original mosaic indices aligned with X columns
    perc : shadow threshold percentile (100 = max shadow importance)
    alpha : binomial test significance level
    """
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y)
    if X.ndim != 2:
        raise ValueError("X must be 2D")
    n, p = X.shape
    if band_indices is None:
        band_indices = list(range(p))
    if len(band_indices) != p:
        raise ValueError("band_indices length must match X columns")
    if band_names is not None and len(band_names) != p:
        raise ValueError("band_names length must match X columns")

    # finite features only
    finite_cols = np.isfinite(X).all(axis=0)
    if not finite_cols.all():
        # fill remaining non-finite with column median of finite rows
        X = X.copy()
        for j in range(p):
            col = X[:, j]
            mask = np.isfinite(col)
            if not mask.any():
                X[:, j] = 0.0
            elif not mask.all():
                X[~mask, j] = np.median(col[mask])

    rng = np.random.default_rng(random_state)
    hits = np.zeros(p, dtype=np.int32)
    imp_sum = np.zeros(p, dtype=np.float64)
    shadow_max_sum = 0.0
    n_done = 0

    undecided = np.ones(p, dtype=bool)

    rf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=None,
        n_jobs=n_jobs,
        class_weight=class_weight,
        random_state=random_state,
    )

    for it in range(max_iter):
        active = np.where(undecided)[0]
        if active.size == 0:
            break

        # shadow copy of active features
        X_act = X[:, active]
        shadows = X_act.copy()
        for j in range(shadows.shape[1]):
            rng.shuffle(shadows[:, j])

        X_aug = np.hstack([X_act, shadows])
        rf.set_params(random_state=random_state + it)
        rf.fit(X_aug, y)
        importances = rf.feature_importances_
        n_act = active.size
        real_imp = importances[:n_act]
        shadow_imp = importances[n_act:]
        shadow_threshold = np.percentile(shadow_imp, perc)

        hit_mask = real_imp > shadow_threshold
        hits[active[hit_mask]] += 1
        imp_sum[active] += real_imp
        shadow_max_sum += float(shadow_threshold)
        n_done += 1

        # early decisions via two-sided binomial against p=0.5
        for j in active:
            # confirmed if P(X >= hits) < alpha under Bin(n_done, 0.5)
            p_conf = 1.0 - binom.cdf(hits[j] - 1, n_done, 0.5)
            p_rej = binom.cdf(hits[j], n_done, 0.5)
            if p_conf < alpha:
                undecided[j] = False
            elif p_rej < alpha:
                undecided[j] = False

    results: list[BorutaBandResult] = []
    for j in range(p):
        if n_done == 0:
            decision = "tentative"
        else:
            p_conf = 1.0 - binom.cdf(hits[j] - 1, n_done, 0.5)
            p_rej = binom.cdf(hits[j], n_done, 0.5)
            if p_conf < alpha:
                decision = "confirmed"
            elif p_rej < alpha:
                decision = "rejected"
            else:
                decision = "tentative"

        name = band_names[j] if band_names is not None else None
        results.append(
            BorutaBandResult(
                band_index=int(band_indices[j]),
                band_name=name,
                decision=decision,
                n_hits=int(hits[j]),
                n_iters=int(n_done),
                hit_rate=float(hits[j] / n_done) if n_done else 0.0,
                mean_importance=float(imp_sum[j] / n_done) if n_done else 0.0,
                mean_shadow_max=float(shadow_max_sum / n_done) if n_done else 0.0,
            )
        )

    # sort: confirmed first by hit_rate, then tentative, then rejected
    order = {"confirmed": 0, "tentative": 1, "rejected": 2}
    results.sort(key=lambda r: (order[r.decision], -r.hit_rate, -r.mean_importance))

    return BorutaResult(
        band_results=results,
        n_iters=int(n_done),
        perc=float(perc),
        alpha=float(alpha),
        n_estimators=int(n_estimators),
        random_state=int(random_state),
    )
