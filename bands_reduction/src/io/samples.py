"""Sample NPZ I/O (Pedro / shared bands_reduction contract).

Expected keys:
  X      (n, n_bands) float32 — spectra
  rows   (n,) int32 — pixel row in mosaic grid
  cols   (n,) int32 — pixel col in mosaic grid
  y      (n,) int32 — optional class labels (LULC)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


REQUIRED_KEYS = ("X", "rows", "cols")


def load_samples(npz_path: str | Path) -> dict[str, np.ndarray]:
    npz_path = Path(npz_path)
    with np.load(npz_path) as z:
        missing = [k for k in REQUIRED_KEYS if k not in z.files]
        if missing:
            raise KeyError(f"{npz_path} missing keys {missing}; has {z.files}")
        out = {k: z[k] for k in z.files}
    if out["X"].ndim != 2:
        raise ValueError(f"X must be 2D, got {out['X'].shape}")
    n = out["X"].shape[0]
    for key in ("rows", "cols"):
        if out[key].shape[0] != n:
            raise ValueError(f"{key} length {out[key].shape[0]} != n={n}")
    if "y" in out and out["y"].shape[0] != n:
        raise ValueError(f"y length {out['y'].shape[0]} != n={n}")
    return out


def save_samples(
    npz_path: str | Path,
    *,
    X: np.ndarray,
    rows: np.ndarray,
    cols: np.ndarray,
    y: np.ndarray | None = None,
    meta: dict[str, Any] | None = None,
) -> Path:
    npz_path = Path(npz_path)
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, np.ndarray] = {
        "X": np.asarray(X),
        "rows": np.asarray(rows),
        "cols": np.asarray(cols),
    }
    if y is not None:
        payload["y"] = np.asarray(y)
    np.savez_compressed(npz_path, **payload)
    if meta is not None:
        meta_path = npz_path.with_suffix(".meta.json")
        meta = dict(meta)
        meta["npz_path"] = str(npz_path)
        meta["meta_path"] = str(meta_path)
        meta["has_y"] = y is not None
        meta["n"] = int(X.shape[0])
        meta["n_bands"] = int(X.shape[1])
        with meta_path.open("w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return npz_path


def load_meta(meta_path: str | Path) -> dict[str, Any]:
    with Path(meta_path).open("r", encoding="utf-8") as f:
        return json.load(f)


def select_bands(X: np.ndarray, band_indices: list[int]) -> np.ndarray:
    idx = np.asarray(band_indices, dtype=np.int64)
    if idx.min() < 0 or idx.max() >= X.shape[1]:
        raise IndexError(
            f"band indices out of range for X with {X.shape[1]} bands: "
            f"min={idx.min()} max={idx.max()}"
        )
    return X[:, idx]
