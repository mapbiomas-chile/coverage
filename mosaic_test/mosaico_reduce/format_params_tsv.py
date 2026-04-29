#!/usr/bin/env python3
"""
Convert params TSV file to JSON format expected by mapbiomas_Chile_mosaics_landsat_v1.py.

Default usage:
    python format_params_tsv.py

This reads `params.tsv` and writes `input_params_2026_SJ-18-X-B.json`.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return default


def split_black_list(value: str | None) -> list[str]:
    if value is None:
        return []
    text = value.strip()
    if not text:
        return []
    # Spreadsheet exports may use comma or semicolon separators.
    raw_parts = text.replace(";", ",").split(",")
    return [part.strip() for part in raw_parts if part.strip()]


def get_value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if key in row and row[key] is not None:
            return str(row[key]).strip()
    return ""


def normalize_satellite(value: str) -> str:
    text = value.strip().lower()
    if text in {"l4", "l5", "l7", "l8", "l9"}:
        return text
    if text in {"4", "5", "7", "8", "9"}:
        return f"l{text}"
    if text.startswith("l") and text[1:].isdigit():
        return text
    raise ValueError(f"Invalid satellite code: {value}")


def convert_tsv_to_records(tsv_path: Path, country: str) -> tuple[list[dict], int]:
    records: list[dict] = []
    skipped_invalid_satellite = 0
    with tsv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader, start=2):  # line 1 is header
            year_text = get_value(row, "YEAR", "year")
            grid_name = get_value(row, "GRID_NAME", "grid_name")
            satellite_text = get_value(row, "SATELLITE", "satellite")

            if not year_text or not grid_name or not satellite_text:
                continue

            try:
                year = int(year_text)
            except ValueError as exc:
                raise ValueError(f"Invalid YEAR at line {i}: {year_text}") from exc

            try:
                satellite = normalize_satellite(satellite_text)
            except ValueError:
                skipped_invalid_satellite += 1
                continue
            t0_s = get_value(row, "t0_s", "T0_S") or f"{year}-01-01"
            t1_s = get_value(row, "t1_s", "T1_S") or f"{year}-12-31"
            cloud_cover_text = get_value(row, "cloud_cover", "CLOUD_COVER")
            cloud_cover = int(cloud_cover_text) if cloud_cover_text else 80

            black_list = split_black_list(get_value(row, "BLACK LIST", "black_list", "BLACK_LIST"))
            use_tile_mask = parse_bool(
                get_value(row, "USETILEMASK", "use_tile_mask", "usetilemask"),
                default=True,
            )

            records.append(
                {
                    "country": country,
                    "grid_name": grid_name,
                    "year": year,
                    "satellite": satellite,
                    "t0_s": t0_s,
                    "t1_s": t1_s,
                    "cloud_cover": cloud_cover,
                    "black_list": black_list,
                    "use_tile_mask": use_tile_mask,
                }
            )
    return records, skipped_invalid_satellite


def main() -> None:
    parser = argparse.ArgumentParser(description="Format params.tsv into m.json for mosaics script")
    parser.add_argument("--input", default="params.tsv", help="Input TSV path (default: params.tsv)")
    parser.add_argument(
        "--output",
        default="input_params_2026_SJ-18-X-B.json",
        help="Output JSON path (default: input_params_2026_SJ-18-X-B.json)",
    )
    parser.add_argument("--country", default="CHILE", help="Country/territory value for JSON rows")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input TSV not found: {input_path}")

    records, skipped_invalid_satellite = convert_tsv_to_records(
        input_path, args.country.strip().upper()
    )

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(records)} rows to {output_path}")
    if skipped_invalid_satellite:
        print(
            f"Skipped {skipped_invalid_satellite} rows with invalid satellite code "
            "(expected L4/L5/L7/L8/L9)"
        )


if __name__ == "__main__":
    main()
