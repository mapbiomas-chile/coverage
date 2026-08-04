"""Ensure each spectral family has at least one representative band."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def band_family(name: str) -> str:
    """Family key from band name (prefix before first ``_``; special cases)."""
    if name.startswith("ndwi"):
        return "ndwi"
    if name.startswith("hallcover") or name.startswith("hallheigth"):
        return "hall"
    return name.split("_")[0] if name else "unknown"


def families_present(band_names: Iterable[str]) -> dict[str, list[int]]:
    """Map family -> sorted band indices."""
    out: dict[str, list[int]] = {}
    for i, name in enumerate(band_names):
        fam = band_family(str(name) if name else f"band_{i}")
        out.setdefault(fam, []).append(i)
    for fam in out:
        out[fam] = sorted(out[fam])
    return out


def _canonical_index(indices: list[int], band_names: list[str]) -> int:
    """Prefer ``*_median`` (not dry/wet); else smallest index."""
    medians = [
        i
        for i in indices
        if str(band_names[i]).endswith("_median")
        and not str(band_names[i]).endswith("_median_dry")
        and not str(band_names[i]).endswith("_median_wet")
    ]
    if medians:
        return int(min(medians))
    return int(min(indices))


def rescue_missing_families(
    rep_indices: Iterable[int],
    band_names: list[str],
) -> tuple[list[int], pd.DataFrame]:
    """
    If a family has zero representatives, add one canonical band from that family.

    Returns (updated sorted unique rep indices, rescue log DataFrame).
    """
    reps = set(int(x) for x in rep_indices)
    fam_map = families_present(band_names)
    log_rows = []

    for fam, members in sorted(fam_map.items()):
        covered = [i for i in members if i in reps]
        if covered:
            continue
        pick = _canonical_index(members, band_names)
        reps.add(pick)
        log_rows.append(
            {
                "family": fam,
                "rescued_band_index": pick,
                "rescued_band_name": band_names[pick] if band_names[pick] else f"band_{pick}",
                "n_family_bands": len(members),
                "reason": "family_had_zero_representatives",
            }
        )

    rescued = pd.DataFrame(log_rows)
    return sorted(reps), rescued
