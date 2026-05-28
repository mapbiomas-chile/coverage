"""Expand CIM parameter rows to MGRS grid_name using a spatial crosswalk."""

from __future__ import annotations

import csv
from pathlib import Path


def load_crosswalk_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def mapping_from_crosswalk(
    rows: list[dict],
    *,
    min_overlap_frac_of_cim: float = 0.0,
) -> dict[str, list[str]]:
    """cim_name -> ordered list of mgrs_tile (highest overlap_frac_of_cim first)."""
    mapping: dict[str, list[str]] = {}
    ranked: dict[str, list[tuple[float, str]]] = {}

    for row in rows:
        frac = float(row.get("overlap_frac_of_cim") or 0)
        if frac < min_overlap_frac_of_cim:
            continue
        cim = str(row["cim_name"]).strip()
        mgrs = str(row["mgrs_tile"]).strip()
        if not cim or not mgrs:
            continue
        ranked.setdefault(cim, []).append((frac, mgrs))

    for cim, pairs in ranked.items():
        pairs.sort(key=lambda x: x[0], reverse=True)
        seen: set[str] = set()
        ordered: list[str] = []
        for _, mgrs in pairs:
            if mgrs in seen:
                continue
            seen.add(mgrs)
            ordered.append(mgrs)
        mapping[cim] = ordered

    return mapping


def expand_cim_records_to_mgrs(
    cim_records: list[dict],
    mapping: dict[str, list[str]],
    *,
    keep_cim_name: bool = True,
) -> tuple[list[dict], dict]:
    """
    One CIM row becomes one row per overlapping MGRS tile.

    Duplicate (mgrs_tile, year, satellite) from different CIM cells merge
    black_list by union (stricter exclusion).
    """
    by_key: dict[tuple[str, int, str], dict] = {}
    cim_no_match: set[str] = set()
    merged_keys = 0

    for rec in cim_records:
        cim_name = str(rec["grid_name"]).strip()
        mgrs_tiles = mapping.get(cim_name, [])
        if not mgrs_tiles:
            cim_no_match.add(cim_name)
            continue

        for mgrs_tile in mgrs_tiles:
            out = dict(rec)
            out["grid_name"] = mgrs_tile
            if keep_cim_name:
                out["cim_name"] = cim_name

            key = (mgrs_tile, int(rec["year"]), str(rec["satellite"]))
            if key not in by_key:
                by_key[key] = out
                continue

            existing = by_key[key]
            merged_bl = sorted(set(existing.get("black_list") or []) | set(out.get("black_list") or []))
            if merged_bl != (existing.get("black_list") or []):
                merged_keys += 1
            existing["black_list"] = merged_bl
            if keep_cim_name:
                prev = existing.get("cim_name", "")
                if cim_name not in prev.split(","):
                    existing["cim_name"] = f"{prev},{cim_name}" if prev else cim_name

    mgrs_records = list(by_key.values())
    mgrs_records.sort(key=lambda r: (r["grid_name"], r["year"], r["satellite"]))

    stats = {
        "cim_rows_in": len(cim_records),
        "mgrs_rows_out": len(mgrs_records),
        "cim_grids_in": len({r["grid_name"] for r in cim_records}),
        "mgrs_grids_out": len({r["grid_name"] for r in mgrs_records}),
        "cim_grids_no_mgrs": sorted(cim_no_match),
        "merged_duplicate_keys": merged_keys,
    }
    return mgrs_records, stats
