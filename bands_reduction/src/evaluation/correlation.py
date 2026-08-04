"""Unsupervised spectral EDA: band–band absolute correlation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def abs_corrcoef(X: np.ndarray) -> np.ndarray:
    """Return |corrcoef| for columns of X (n_samples, n_bands)."""
    if X.ndim != 2:
        raise ValueError(f"X must be 2D, got {X.shape}")
    # Columns with zero variance → nan in corrcoef; treat as 0 off-diag later
    c = np.corrcoef(X, rowvar=False)
    c = np.nan_to_num(c, nan=0.0, posinf=0.0, neginf=0.0)
    return np.abs(c).astype(np.float32)


def summarize_abs_corr(
    corr_abs: np.ndarray,
    thresholds: tuple[float, ...] = (0.9, 0.95, 0.99),
) -> dict[str, Any]:
    n = corr_abs.shape[0]
    # upper triangle off-diagonal
    iu = np.triu_indices(n, k=1)
    vals = corr_abs[iu]
    summary: dict[str, Any] = {
        "n_bands": int(n),
        "n_pairs": int(vals.size),
        "mean_abs_r": float(vals.mean()) if vals.size else 0.0,
        "median_abs_r": float(np.median(vals)) if vals.size else 0.0,
        "std_abs_r": float(vals.std()) if vals.size else 0.0,
        "max_abs_r": float(vals.max()) if vals.size else 0.0,
        "min_abs_r": float(vals.min()) if vals.size else 0.0,
        "thresholds": {},
    }
    for t in thresholds:
        n_hi = int((vals >= t).sum())
        summary["thresholds"][str(t)] = {
            "n_pairs": n_hi,
            "pct_pairs": float(100.0 * n_hi / vals.size) if vals.size else 0.0,
        }
    return summary


def high_corr_pairs(
    corr_abs: np.ndarray,
    threshold: float = 0.9,
) -> pd.DataFrame:
    n = corr_abs.shape[0]
    rows = []
    for i in range(n):
        for j in range(i + 1, n):
            r = float(corr_abs[i, j])
            if r >= threshold:
                rows.append({"band_i": i, "band_j": j, "abs_r": r})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("abs_r", ascending=False).reset_index(drop=True)
    return df


def plot_corr_heatmap(corr_abs: np.ndarray, out_path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(corr_abs, vmin=0.0, vmax=1.0, cmap="viridis", interpolation="nearest")
    ax.set_title(title)
    ax.set_xlabel("band index")
    ax.set_ylabel("band index")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="|r|")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_corr_hist(corr_abs: np.ndarray, out_path: Path, title: str) -> None:
    n = corr_abs.shape[0]
    vals = corr_abs[np.triu_indices(n, k=1)]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(vals, bins=50, range=(0, 1), color="steelblue", edgecolor="white")
    ax.axvline(0.9, color="crimson", linestyle="--", label="|r|=0.9")
    ax.axvline(0.95, color="darkorange", linestyle="--", label="|r|=0.95")
    ax.set_xlabel("|r|")
    ax.set_ylabel("pair count")
    ax.set_title(title)
    ax.legend(frameon=False)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def run_correlation_eda(
    X: np.ndarray,
    out_dir: str | Path,
    *,
    label: str,
    pair_threshold: float = 0.9,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute |r|, write artifacts under out_dir, return summary dict."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    corr = abs_corrcoef(X)
    summary = summarize_abs_corr(corr)
    summary["label"] = label
    summary["n_samples"] = int(X.shape[0])
    summary["pair_threshold_export"] = float(pair_threshold)
    if extra_meta:
        summary["source"] = extra_meta

    np.save(out_dir / "corr_abs.npy", corr)

    pairs = high_corr_pairs(corr, threshold=pair_threshold)
    pairs_path = out_dir / "high_corr_pairs.csv"
    pairs.to_csv(pairs_path, index=False)
    summary["n_high_corr_pairs_exported"] = int(len(pairs))

    plot_corr_heatmap(corr, out_dir / "corr_heatmap.png", f"|r| heatmap — {label}")
    plot_corr_hist(corr, out_dir / "corr_hist.png", f"|r| pair histogram — {label}")

    summary_path = out_dir / "corr_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    summary["out_dir"] = str(out_dir)
    summary["status"] = "PASS"
    return summary
