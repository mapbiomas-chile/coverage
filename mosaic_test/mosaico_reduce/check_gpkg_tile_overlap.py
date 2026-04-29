#!/usr/bin/env python3
"""
Check whether a local GPKG intersects a CIM grid tile in Google Earth Engine.

Default usage (from mosaico_reduce directory):
    python check_gpkg_tile_overlap.py

Example:
    python check_gpkg_tile_overlap.py \
      --gpkg ../../inputs/gpk/Muestra_Lagogpk.gpkg \
      --tile SJ-18-X-B \
      --project mapbiomas-chile
"""

from __future__ import annotations

import argparse
from pathlib import Path

import ee
import geopandas as gpd


GRID_ASSET = "projects/mapbiomas-workspace/AUXILIAR/cim-world-1-250000"


def _load_gpkg_bbox_4326(gpkg_path: Path) -> tuple[list[float], int, str]:
    gdf = gpd.read_file(gpkg_path)
    feature_count = len(gdf)
    if feature_count == 0:
        raise ValueError(f"GPKG has no features: {gpkg_path}")

    source_crs = str(gdf.crs) if gdf.crs else "None"
    if gdf.crs is not None and str(gdf.crs).upper() != "EPSG:4326":
        gdf = gdf.to_crs(4326)

    minx, miny, maxx, maxy = gdf.total_bounds
    return [float(minx), float(miny), float(maxx), float(maxy)], feature_count, source_crs


def _get_tile_geometry(tile_name: str) -> ee.Geometry:
    fc = ee.FeatureCollection(GRID_ASSET).filter(ee.Filter.eq("name", tile_name))
    count = fc.size().getInfo()
    if count == 0:
        raise ValueError(f"Tile not found in grid asset: {tile_name}")
    return ee.Feature(fc.first()).geometry()


def check_overlap(gpkg_path: Path, tile_name: str, project: str) -> dict:
    if not gpkg_path.exists():
        raise FileNotFoundError(f"GPKG not found: {gpkg_path}")

    bbox, feature_count, source_crs = _load_gpkg_bbox_4326(gpkg_path)

    ee.Initialize(project=project)
    tile_geometry = _get_tile_geometry(tile_name)
    tile_bbox_coords = tile_geometry.bounds().coordinates().getInfo()

    gpkg_bbox_geom = ee.Geometry.BBox(bbox[0], bbox[1], bbox[2], bbox[3])
    intersects = bool(tile_geometry.intersects(gpkg_bbox_geom, ee.ErrorMargin(1)).getInfo())

    return {
        "gpkg_path": str(gpkg_path),
        "gpkg_features": feature_count,
        "gpkg_source_crs": source_crs,
        "gpkg_bbox_4326": bbox,
        "tile_name": tile_name,
        "tile_bbox_coords": tile_bbox_coords,
        "intersects_bbox": intersects,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check intersection between a local GPKG and a CIM tile in Earth Engine."
    )
    parser.add_argument(
        "--gpkg",
        default="../../inputs/gpk/Muestra_Lagogpk.gpkg",
        help="Path to input GPKG (default: ../../inputs/gpk/Muestra_Lagogpk.gpkg)",
    )
    parser.add_argument(
        "--tile",
        default="SJ-18-X-B",
        help="CIM tile name to query in Earth Engine (default: SJ-18-X-B)",
    )
    parser.add_argument(
        "--project",
        default="mapbiomas-chile",
        help="Earth Engine project ID (default: mapbiomas-chile)",
    )
    args = parser.parse_args()

    result = check_overlap(Path(args.gpkg), args.tile, args.project)
    print(f"gpkg_path: {result['gpkg_path']}")
    print(f"gpkg_features: {result['gpkg_features']}")
    print(f"gpkg_source_crs: {result['gpkg_source_crs']}")
    print(f"gpkg_bbox_4326: {result['gpkg_bbox_4326']}")
    print(f"tile_name: {result['tile_name']}")
    print(f"tile_bbox_coords: {result['tile_bbox_coords']}")
    print(f"intersects_bbox: {result['intersects_bbox']}")


if __name__ == "__main__":
    main()
