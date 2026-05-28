"""Convert spreadsheet parameters to JSON for the Landsat mosaic pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

EXCEL_SHEET = "tabla"
EXCEL_COLUMNS = {
    "year": "YEAR",
    "grid_name": "GRID_NAME",
    "satellite": "SATELLITE",
    "black_list": "BLACK LIST",
    "use_tile_mask": "USETILEMASK",
    "satellite_comment": "SATELLITE_COMMENT",
}


def parse_bool(value, default: bool = True) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    text = str(value).strip().lower()
    if not text or text == "nan":
        return default
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return default


def split_black_list(value) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    raw_parts = text.replace(";", ",").split(",")
    return [part.strip() for part in raw_parts if part.strip()]


def normalize_satellite(value: str) -> str:
    text = str(value).strip().lower()
    if text in {"l4", "l5", "l7", "l8", "l9"}:
        return text
    if text in {"4", "5", "7", "8", "9"}:
        return f"l{text}"
    if text.startswith("l") and text[1:].isdigit():
        return text
    raise ValueError(f"Invalid satellite code: {value}")


def read_params_excel(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=EXCEL_SHEET)
    missing = [v for v in EXCEL_COLUMNS.values() if v not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")
    return df


def excel_to_records(df: pd.DataFrame, country: str = "CHILE") -> tuple[list[dict], int]:
    records: list[dict] = []
    skipped_invalid_satellite = 0

    for i, row in df.iterrows():
        year_val = row[EXCEL_COLUMNS["year"]]
        grid_name = str(row[EXCEL_COLUMNS["grid_name"]]).strip()
        satellite_text = str(row[EXCEL_COLUMNS["satellite"]]).strip()

        if pd.isna(year_val) or not grid_name or not satellite_text:
            continue

        try:
            year = int(year_val)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid YEAR at row {i}: {year_val}") from exc

        try:
            satellite = normalize_satellite(satellite_text)
        except ValueError:
            skipped_invalid_satellite += 1
            continue

        black_list = split_black_list(row[EXCEL_COLUMNS["black_list"]])
        use_tile_mask = parse_bool(row[EXCEL_COLUMNS["use_tile_mask"]], default=True)

        records.append(
            {
                "country": country,
                "grid_name": grid_name,
                "year": year,
                "satellite": satellite,
                "t0_s": f"{year}-01-01",
                "t1_s": f"{year}-12-31",
                "cloud_cover": 80,
                "black_list": black_list,
                "use_tile_mask": use_tile_mask,
            }
        )

    return records, skipped_invalid_satellite


def write_params_json(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
        f.write("\n")


def convert_excel_to_json(
    input_path: Path,
    output_path: Path,
    country: str = "CHILE",
) -> tuple[int, int]:
    df = read_params_excel(input_path)
    records, skipped = excel_to_records(df, country=country.upper())
    write_params_json(records, output_path)
    return len(records), skipped


def summarize_params(df: pd.DataFrame) -> dict:
    bl_col = EXCEL_COLUMNS["black_list"]
    return {
        "rows": len(df),
        "grids": int(df[EXCEL_COLUMNS["grid_name"]].nunique()),
        "years_min": int(df[EXCEL_COLUMNS["year"]].min()),
        "years_max": int(df[EXCEL_COLUMNS["year"]].max()),
        "black_list_rows": int(df[bl_col].notna().sum()),
    }


def convert_excel_to_mgrs_json(
    input_path: Path,
    output_path: Path,
    xwalk_csv: Path,
    *,
    country: str = "CHILE",
    min_overlap_frac_of_cim: float = 0.0,
    keep_cim_name: bool = True,
) -> tuple[list[dict], dict, int]:
    """Excel -> CIM records -> MGRS grid_name rows using crosswalk CSV."""
    from cim_mgrs_regrid.remap import (
        expand_cim_records_to_mgrs,
        load_crosswalk_csv,
        mapping_from_crosswalk,
    )

    if not xwalk_csv.exists():
        raise FileNotFoundError(
            f"Crosswalk CSV not found: {xwalk_csv}\n"
            "Run: python scripts/build_xwalk.py"
        )

    df = read_params_excel(input_path)
    records, skipped = excel_to_records(df, country=country.upper())
    mapping = mapping_from_crosswalk(
        load_crosswalk_csv(xwalk_csv),
        min_overlap_frac_of_cim=min_overlap_frac_of_cim,
    )
    mgrs_records, stats = expand_cim_records_to_mgrs(
        records, mapping, keep_cim_name=keep_cim_name
    )
    write_params_json(mgrs_records, output_path)
    stats["skipped_invalid_satellite"] = skipped
    return mgrs_records, stats, skipped
