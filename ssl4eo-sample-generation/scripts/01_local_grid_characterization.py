#!/usr/bin/env python3
"""Caracterizacion de grillas SSL4EO en el cluster (rasterio, sin Earth Engine)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cluster_config import ECO_TIF, LANDCOVER_DIR, MGRS_GPKG
from local_grid_characterization import RunConfig, run_and_export
from project_paths import GRID_CHARACTERIZATION_DIR


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Caracteriza grillas SSL4EO localmente con GeoTIFF del cluster."
    )
    parser.add_argument("--utm", type=int, choices=[12, 17, 18, 19], default=19)
    parser.add_argument("--rect-side", type=int, choices=[1, 2, 3, 4, 5], default=3)
    parser.add_argument("--stats-scale", type=int, default=300)
    parser.add_argument("--class-level", choices=["n3", "general"], default="n3")
    parser.add_argument("--start-year", type=int, default=1999)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--landcover-dir", type=Path, default=LANDCOVER_DIR)
    parser.add_argument("--eco-tif", type=Path, default=ECO_TIF)
    parser.add_argument("--mgrs-gpkg", type=Path, default=MGRS_GPKG)
    parser.add_argument("--output-dir", type=Path, default=GRID_CHARACTERIZATION_DIR)
    parser.add_argument("--tiles", nargs="*", default=None, help="Solo estas tiles MGRS.")
    parser.add_argument("--run-scale300-all", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    GRID_CHARACTERIZATION_DIR.mkdir(parents=True, exist_ok=True)

    jobs = (
        [
            {"utm": 18, "rect_side": 2},
            {"utm": 18, "rect_side": 3},
            {"utm": 19, "rect_side": 2},
            {"utm": 19, "rect_side": 3},
        ]
        if args.run_scale300_all
        else [{"utm": args.utm, "rect_side": args.rect_side}]
    )

    for job in jobs:
        cfg = RunConfig(
            rect_chips_side=job["rect_side"],
            target_utm_zone=job["utm"],
            stats_scale=args.stats_scale,
            start_year=args.start_year,
            end_year=args.end_year,
            class_level=args.class_level,
            landcover_dir=args.landcover_dir,
            eco_tif=args.eco_tif,
            mgrs_gpkg=args.mgrs_gpkg,
        )
        if args.tiles:
            from local_grid_characterization import characterize, export_name, write_geopackage_zip

            gdf = characterize(cfg, tile_names=args.tiles)
            name = export_name(cfg)
            out_zip = args.output_dir / f"{name}.zip"
            write_geopackage_zip(gdf, out_zip)
            print(f"  Rectangulos filtrados: {len(gdf)}")
            print(f"  Exportado: {out_zip}")
        else:
            run_and_export(cfg, output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
