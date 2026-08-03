#!/usr/bin/env python3
"""Export a band-list JSON (full 184 or from a representatives.json).

Shared contract so JM / clustering / FCBF exchange the same file format.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.band_list import band_list_from_indices, save_band_list
from src.io.mosaic import find_mosaic_tile, read_band_names
from src.utils.config import load_yaml


def _indices_from_representatives(path: Path) -> list[int]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    reps = data.get("representatives", data.get("bands"))
    if reps is None:
        raise ValueError(f"No 'representatives' or 'bands' in {path}")
    if isinstance(reps, dict):
        # allow { "0": {...}, ... } or {"indices": [...]}
        if "indices" in reps:
            reps = reps["indices"]
        else:
            reps = sorted(int(k) for k in reps.keys())
    return [int(i) for i in reps]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/global.yaml")
    parser.add_argument("--tile", default="19KCQ")
    parser.add_argument("--ecoregion", type=int, default=2)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument(
        "--source",
        default="full",
        help="Label for band-list source field (full | waludi_bandclust | ...)",
    )
    parser.add_argument(
        "--from-representatives",
        type=Path,
        default=None,
        help="Optional PE representatives.json with band indices",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cfg = load_yaml(ROOT / args.config if not Path(args.config).is_absolute() else args.config)
    year = args.year or int(cfg.get("project", {}).get("year", 2015))
    mosaic_path = find_mosaic_tile(cfg["paths"]["mosaic"], args.tile, year)
    names = read_band_names(mosaic_path)

    if args.from_representatives:
        bands = _indices_from_representatives(args.from_representatives)
        source = args.source if args.source != "full" else "waludi_bandclust"
    else:
        bands = list(range(len(names)))
        source = args.source

    band_names = [names[i] for i in bands]
    payload = band_list_from_indices(
        bands,
        source=source,
        ecoregion=args.ecoregion,
        tile=args.tile,
        year=year,
        band_names=band_names,
    )
    out = save_band_list(args.out, payload)
    print(f"Wrote {out} ({len(bands)} bands, source={source})")


if __name__ == "__main__":
    main()
