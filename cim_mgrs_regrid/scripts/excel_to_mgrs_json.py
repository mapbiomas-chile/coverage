#!/usr/bin/env python3
"""
Excel + crosswalk CSV -> output/input_params.json with MGRS grid_name.

Preserves per-row black_list and dates from each CIM source row; expands
geographically via cim_mgrs_xwalk.csv.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cim_mgrs_regrid.config import (  # noqa: E402
    DEFAULT_MIN_OVERLAP_FRAC_OF_CIM,
    DEFAULT_PARAMS_JSON,
    DEFAULT_PARAMS_XLSX,
    DEFAULT_XWALK_CSV,
)
from cim_mgrs_regrid.params import (  # noqa: E402
    convert_excel_to_mgrs_json,
    read_params_excel,
    summarize_params,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build input_params.json with MGRS grid_name from Excel + xwalk."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_PARAMS_XLSX)
    parser.add_argument("--output", type=Path, default=DEFAULT_PARAMS_JSON)
    parser.add_argument("--xwalk-csv", type=Path, default=DEFAULT_XWALK_CSV)
    parser.add_argument("--country", default="CHILE")
    parser.add_argument(
        "--min-overlap-frac",
        type=float,
        default=DEFAULT_MIN_OVERLAP_FRAC_OF_CIM,
        help="Min overlap_frac_of_cim to link an MGRS tile (default: 0 = any intersection)",
    )
    parser.add_argument(
        "--no-cim-name",
        action="store_true",
        help="Omit cim_name traceability field from output rows",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")

    summary = summarize_params(read_params_excel(args.input))
    _, stats, skipped = convert_excel_to_mgrs_json(
        args.input,
        args.output,
        args.xwalk_csv,
        country=args.country,
        min_overlap_frac_of_cim=args.min_overlap_frac,
        keep_cim_name=not args.no_cim_name,
    )

    print(f"Excel summary: {summary}")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"Wrote {stats['mgrs_rows_out']} rows -> {args.output}")
    if skipped:
        print(f"Skipped {skipped} rows with invalid satellite code")
    if stats["cim_grids_no_mgrs"]:
        print(
            f"WARNING: {len(stats['cim_grids_no_mgrs'])} CIM grids have no MGRS match in xwalk"
        )


if __name__ == "__main__":
    main()
