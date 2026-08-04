#!/usr/bin/env python3
"""F0 inspect: mosaic metadata + ecoregion mask warped to tile grid.

Example:
  python scripts/01_inspect_mosaic.py \\
    --config configs/global.yaml \\
    --ecoregion configs/ecoregions/eco_02_desierto.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as `python scripts/01_inspect_mosaic.py` from bands_reduction/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io import read_mosaic_info, resolve_mosaic_path, warp_eco_mask_to_mosaic
from src.utils import load_configs


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Inspect mosaic ∩ ecoregion mask (F0)")
    p.add_argument("--config", default="configs/global.yaml")
    p.add_argument(
        "--ecoregion",
        default="configs/ecoregions/eco_02_desierto.yaml",
        help="Ecoregion YAML (id + pilot tiles)",
    )
    p.add_argument(
        "--tile",
        default=None,
        help="Override pilot tile (default: first tile in ecoregion YAML)",
    )
    p.add_argument(
        "--year",
        type=int,
        default=None,
        help="Override year (default: pilot.year or project.mosaic_year)",
    )
    p.add_argument(
        "--json-out",
        default=None,
        help="Optional path to write summary JSON (e.g. under results_dir)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_configs(ROOT / args.config, ROOT / args.ecoregion)

    paths = cfg["paths"]
    eco = cfg["ecoregion"]
    pilot = cfg.get("pilot", {})
    project = cfg.get("project", {})

    tile = args.tile or pilot["tiles"][0]
    year = args.year or pilot.get("year") or project["mosaic_year"]
    eco_id = int(eco["id"])

    mosaic_path = resolve_mosaic_path(
        paths["mosaics_dir"],
        tile=tile,
        year=int(year),
        filename_template=paths["mosaic_filename_template"],
    )
    info = read_mosaic_info(mosaic_path)

    expected_bands = int(project.get("n_bands_full", 184))
    bands_ok = info.count == expected_bands

    stats = warp_eco_mask_to_mosaic(
        ecoregions_path=paths["ecoregions"],
        mosaic_crs=info.crs,
        mosaic_transform=info.transform,
        mosaic_width=info.width,
        mosaic_height=info.height,
        ecoregion_id=eco_id,
    )
    eco_ok = stats.n_eco > 0

    summary = {
        "tile": tile,
        "year": int(year),
        "ecoregion": {
            "id": eco_id,
            "name": eco.get("name"),
            "label": eco.get("label"),
        },
        "mosaic": {
            "path": str(info.path),
            "crs": str(info.crs),
            "width": info.width,
            "height": info.height,
            "count": info.count,
            "dtype": info.dtype,
            "nodata": info.nodata,
            "res": list(info.res),
            "bounds": list(info.bounds),
            "bands_ok": bands_ok,
            "expected_bands": expected_bands,
        },
        "eco_mask": {
            "source": paths["ecoregions"],
            "method": "reproject_nearest_to_mosaic_grid",
            "n_pixels": stats.n_pixels,
            "n_eco": stats.n_eco,
            "pct_eco": round(stats.pct_eco, 4),
            "eco_ok": eco_ok,
        },
        "status": "PASS" if (bands_ok and eco_ok) else "FAIL",
    }

    print(json.dumps(summary, indent=2))

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2) + "\n")
        print(f"Wrote {out}", file=sys.stderr)

    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
