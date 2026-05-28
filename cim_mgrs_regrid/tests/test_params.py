"""Unit tests that do not call Earth Engine."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cim_mgrs_regrid.params import (  # noqa: E402
    excel_to_records,
    normalize_satellite,
    split_black_list,
)


def test_normalize_satellite():
    assert normalize_satellite("L5") == "l5"
    assert normalize_satellite("5") == "l5"


def test_split_black_list():
    assert split_black_list(None) == []
    assert split_black_list("A,B; C") == ["A", "B", "C"]


def test_excel_to_records_minimal():
    df = pd.DataFrame(
        {
            "YEAR": [2020],
            "GRID_NAME": ["SE-19-V-D"],
            "SATELLITE": ["L5"],
            "BLACK LIST": [None],
            "USETILEMASK": [True],
            "SATELLITE_COMMENT": [None],
        }
    )
    records, skipped = excel_to_records(df)
    assert skipped == 0
    assert len(records) == 1
    assert records[0]["grid_name"] == "SE-19-V-D"
    assert records[0]["black_list"] == []
