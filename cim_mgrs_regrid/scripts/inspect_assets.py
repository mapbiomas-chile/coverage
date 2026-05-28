#!/usr/bin/env python3
"""Print CIM / MGRS asset metadata from Earth Engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cim_mgrs_regrid.config import ASSET_LEGACY_MOSAICS, DEFAULT_EE_PROJECT  # noqa: E402
from cim_mgrs_regrid.gee import inspect_assets, initialize  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect GEE grid assets.")
    parser.add_argument("--project", default=DEFAULT_EE_PROJECT)
    parser.add_argument(
        "--legacy-mosaics",
        action="store_true",
        help=f"Also print image count in {ASSET_LEGACY_MOSAICS}",
    )
    args = parser.parse_args()

    initialize(args.project)
    info = inspect_assets()
    print(json.dumps(info, indent=2))

    if args.legacy_mosaics:
        import ee

        coll = ee.ImageCollection(ASSET_LEGACY_MOSAICS)
        print(f"\nLegacy mosaics ({ASSET_LEGACY_MOSAICS}):")
        print(f"  images: {coll.size().getInfo()}")


if __name__ == "__main__":
    main()
