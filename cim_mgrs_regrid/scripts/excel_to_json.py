#!/usr/bin/env python3
"""Convert Excel → JSON with CIM grid_name (use excel_to_mgrs_json.py for MGRS output)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cim_mgrs_regrid.config import (  # noqa: E402
    DEFAULT_PARAMS_JSON_CIM,
    DEFAULT_PARAMS_XLSX,
)
from cim_mgrs_regrid.params import (  # noqa: E402
    convert_excel_to_json,
    read_params_excel,
    summarize_params,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert parametros Excel (hoja 'tabla') to mosaic JSON."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_PARAMS_XLSX,
        help=f"Input .xlsx (default: {DEFAULT_PARAMS_XLSX})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PARAMS_JSON_CIM,
        help=f"Output JSON path (default: {DEFAULT_PARAMS_JSON_CIM})",
    )
    parser.add_argument("--country", default="CHILE")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(
            f"Input not found: {args.input}\n"
            "Copy the spreadsheet to data/03-parametros-124grids-19962025.xlsx "
            "(same content as the Google Sheet)."
        )

    summary = summarize_params(read_params_excel(args.input))
    n, skipped = convert_excel_to_json(args.input, args.output, country=args.country)

    print(f"Summary: {summary}")
    print(f"Wrote {n} rows -> {args.output}")
    if skipped:
        print(f"Skipped {skipped} rows with invalid satellite code")


if __name__ == "__main__":
    main()
