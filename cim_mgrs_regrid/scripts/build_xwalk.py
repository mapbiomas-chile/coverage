#!/usr/bin/env python3
"""Build CIM ↔ MGRS crosswalk CSV (local output/, not committed)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cim_mgrs_regrid.config import (  # noqa: E402
    DEFAULT_EE_PROJECT,
    DEFAULT_PARAMS_XLSX,
    DEFAULT_XWALK_CSV,
)
from cim_mgrs_regrid.params import EXCEL_COLUMNS, read_params_excel  # noqa: E402
from cim_mgrs_regrid.xwalk import build_crosswalk, write_crosswalk_csv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CIM ↔ MGRS spatial crosswalk.")
    parser.add_argument(
        "--params-xlsx",
        type=Path,
        default=DEFAULT_PARAMS_XLSX,
        help="Excel with GRID_NAME column (default: data/03-parametros-....xlsx)",
    )
    parser.add_argument(
        "--cim",
        action="append",
        dest="cim_names",
        help="Process only these CIM names (repeatable). Default: all grids in Excel.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_XWALK_CSV,
        help=f"Output CSV (default: {DEFAULT_XWALK_CSV})",
    )
    parser.add_argument("--project", default=DEFAULT_EE_PROJECT)
    args = parser.parse_args()

    if args.cim_names:
        cim_names = sorted(set(args.cim_names))
    else:
        if not args.params_xlsx.exists():
            raise SystemExit(f"Params Excel not found: {args.params_xlsx}")
        df = read_params_excel(args.params_xlsx)
        cim_names = sorted(df[EXCEL_COLUMNS["grid_name"]].astype(str).str.strip().unique())

    print(f"Building crosswalk for {len(cim_names)} CIM cells...")
    rows = build_crosswalk(cim_names, project=args.project)
    write_crosswalk_csv(rows, args.output)
    print(f"Wrote {len(rows)} overlap rows -> {args.output}")


if __name__ == "__main__":
    main()
