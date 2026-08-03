"""Band-list contract shared across pipeline stages.

Format (JSON):
{
  "source": "full" | "fcbf" | "waludi_bandclust" | ...,
  "ecoregion": 2,
  "tile": "19KCQ",
  "year": 2015,
  "bands": [0, 8, 9, ...]          # 0-based indices into the 184-band mosaic
  "band_names": ["aspect", ...]    # optional, parallel to bands
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_band_list(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "bands" not in data:
        raise ValueError(f"band-list missing 'bands': {path}")
    bands = list(data["bands"])
    if not bands:
        raise ValueError(f"band-list 'bands' is empty: {path}")
    if not all(isinstance(b, int) for b in bands):
        raise ValueError(f"band-list 'bands' must be integer indices: {path}")
    data["bands"] = bands
    return data


def save_band_list(path: str | Path, payload: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def band_list_from_indices(
    bands: list[int],
    *,
    source: str,
    ecoregion: int | None = None,
    tile: str | None = None,
    year: int | None = None,
    band_names: list[str] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"source": source, "bands": [int(b) for b in bands]}
    if ecoregion is not None:
        out["ecoregion"] = int(ecoregion)
    if tile is not None:
        out["tile"] = tile
    if year is not None:
        out["year"] = int(year)
    if band_names is not None:
        if len(band_names) != len(bands):
            raise ValueError("band_names length must match bands")
        out["band_names"] = list(band_names)
    return out
