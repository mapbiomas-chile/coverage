"""Tests for CIM -> MGRS parameter expansion (no GEE)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cim_mgrs_regrid.remap import (  # noqa: E402
    expand_cim_records_to_mgrs,
    mapping_from_crosswalk,
)


def test_mapping_from_crosswalk_filters_frac():
    rows = [
        {"cim_name": "A", "mgrs_tile": "T1", "overlap_frac_of_cim": "0.8"},
        {"cim_name": "A", "mgrs_tile": "T2", "overlap_frac_of_cim": "0.001"},
    ]
    m = mapping_from_crosswalk(rows, min_overlap_frac_of_cim=0.01)
    assert m["A"] == ["T1"]


def test_expand_one_cim_to_many_mgrs():
    cim_records = [
        {
            "country": "CHILE",
            "grid_name": "CIM-1",
            "year": 2020,
            "satellite": "l5",
            "t0_s": "2020-01-01",
            "t1_s": "2020-12-31",
            "cloud_cover": 80,
            "black_list": ["SCENE_A"],
            "use_tile_mask": True,
        }
    ]
    mapping = {"CIM-1": ["18GXN", "18GXM"]}
    out, stats = expand_cim_records_to_mgrs(cim_records, mapping)
    assert stats["mgrs_rows_out"] == 2
    assert {r["grid_name"] for r in out} == {"18GXN", "18GXM"}
    assert all(r["black_list"] == ["SCENE_A"] for r in out)
    assert all(r["cim_name"] == "CIM-1" for r in out)


def test_merge_black_list_when_two_cims_share_mgrs():
    cim_records = [
        {
            "country": "CHILE",
            "grid_name": "CIM-A",
            "year": 2020,
            "satellite": "l5",
            "t0_s": "2020-01-01",
            "t1_s": "2020-12-31",
            "cloud_cover": 80,
            "black_list": ["SCENE_A"],
            "use_tile_mask": True,
        },
        {
            "country": "CHILE",
            "grid_name": "CIM-B",
            "year": 2020,
            "satellite": "l5",
            "t0_s": "2020-01-01",
            "t1_s": "2020-12-31",
            "cloud_cover": 80,
            "black_list": ["SCENE_B"],
            "use_tile_mask": True,
        },
    ]
    mapping = {"CIM-A": ["18GXN"], "CIM-B": ["18GXN"]}
    out, stats = expand_cim_records_to_mgrs(cim_records, mapping)
    assert len(out) == 1
    assert set(out[0]["black_list"]) == {"SCENE_A", "SCENE_B"}
    assert stats["merged_duplicate_keys"] == 1
