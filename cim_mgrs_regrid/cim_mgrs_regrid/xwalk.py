"""Spatial crosswalk: CIM grid cells ↔ MGRS Sentinel tiles."""

from __future__ import annotations

import csv
from pathlib import Path

import ee

from cim_mgrs_regrid.config import CIM_GRID_NAME_PROP
from cim_mgrs_regrid.gee import (
    cim_feature,
    detect_mgrs_tile_id_field,
    initialize,
    mgrs_tile_id,
    mgrs_tiles_fc,
)


def _overlap_row(
    cim_name: str,
    mgrs_id: str,
    overlap_m2: float,
    cim_area_m2: float,
    mgrs_area_m2: float,
) -> dict:
    frac_cim = overlap_m2 / cim_area_m2 if cim_area_m2 else 0.0
    frac_mgrs = overlap_m2 / mgrs_area_m2 if mgrs_area_m2 else 0.0
    return {
        "cim_name": cim_name,
        "mgrs_tile": mgrs_id,
        "overlap_m2": round(overlap_m2, 2),
        "cim_area_m2": round(cim_area_m2, 2),
        "mgrs_area_m2": round(mgrs_area_m2, 2),
        "overlap_frac_of_cim": round(frac_cim, 6),
        "overlap_frac_of_mgrs": round(frac_mgrs, 6),
    }


def crosswalk_for_cim(
    cim_name: str,
    mgrs_id_field: str,
    error_margin_m: float = 1.0,
) -> list[dict]:
    """All MGRS tiles intersecting one CIM cell, with overlap areas."""
    cim = cim_feature(cim_name)
    cim_geom = cim.geometry()
    cim_area_m2 = float(cim_geom.area(error_margin_m).getInfo())

    hits = mgrs_tiles_fc().filterBounds(cim_geom)
    hit_list = hits.toList(hits.size())
    n = hits.size().getInfo()
    rows: list[dict] = []

    for i in range(n):
        mgrs = ee.Feature(hit_list.get(i))
        mgrs_geom = mgrs.geometry()
        inter = cim_geom.intersection(mgrs_geom, error_margin_m)
        overlap_m2 = float(inter.area(error_margin_m).getInfo())
        if overlap_m2 <= 0:
            continue
        mgrs_area_m2 = float(mgrs_geom.area(error_margin_m).getInfo())
        rows.append(
            _overlap_row(
                cim_name=cim_name,
                mgrs_id=mgrs_tile_id(mgrs, mgrs_id_field),
                overlap_m2=overlap_m2,
                cim_area_m2=cim_area_m2,
                mgrs_area_m2=mgrs_area_m2,
            )
        )

    rows.sort(key=lambda r: r["overlap_frac_of_cim"], reverse=True)
    return rows


def classify_cim_relation(rows: list[dict], primary_threshold: float = 0.95) -> str:
    if not rows:
        return "no_mgrs_match"
    top = rows[0]["overlap_frac_of_cim"]
    if len(rows) == 1 and top >= primary_threshold:
        return "1:1"
    if len(rows) == 1:
        return "1:1_partial"
    if top >= primary_threshold:
        return "1:N"
    return "N:N"


def build_crosswalk(
    cim_names: list[str],
    project: str | None = None,
) -> list[dict]:
    if project:
        initialize(project)
    else:
        initialize()

    mgrs_id_field = detect_mgrs_tile_id_field()
    all_rows: list[dict] = []

    for name in cim_names:
        pairs = crosswalk_for_cim(name, mgrs_id_field)
        relation = classify_cim_relation(pairs)
        for rank, row in enumerate(pairs, start=1):
            row["mgrs_rank_by_cim_overlap"] = rank
            row["cim_mgrs_relation"] = relation if rank == 1 else ""
            all_rows.append(row)

    return all_rows


def write_crosswalk_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
