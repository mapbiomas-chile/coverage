#!/usr/bin/env python3
"""
Plot NDWI (mean over area) from reduced mosaics for a local GPKG geometry.

Default usage (from mosaico_reduce):
    python plot_ndwi_gpkg.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import ee
import geopandas as gpd
import matplotlib.pyplot as plt


def gpkg_to_ee_geometry(gpkg_path: Path) -> ee.Geometry:
    gdf = gpd.read_file(gpkg_path)
    if gdf.empty:
        raise ValueError(f"GPKG has no features: {gpkg_path}")

    if gdf.crs is not None and str(gdf.crs).upper() != "EPSG:4326":
        gdf = gdf.to_crs(4326)

    geom = gdf.geometry.unary_union
    if geom.is_empty:
        raise ValueError(f"Unified geometry is empty: {gpkg_path}")

    return ee.Geometry(geom.__geo_interface__)


def fetch_ndwi_series(
    collection_asset: str,
    region: ee.Geometry,
    territory: str,
    grid_name: str,
    export_suffix_contains: str,
    scale: int,
) -> list[dict]:
    col = ee.ImageCollection(collection_asset) \
        .filterMetadata("territory", "equals", territory) \
        .filterMetadata("grid_name", "equals", grid_name)

    if export_suffix_contains.strip():
        col = col.filter(ee.Filter.stringContains("system:index", export_suffix_contains.strip()))

    def summarize(image: ee.Image) -> ee.Feature:
        ndwi_raw = image.select("ndwi_median").reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=scale,
            maxPixels=1_000_000_000_000,
            bestEffort=True,
        ).get("ndwi_median")

        ndwi_scaled = ee.Algorithms.If(
            ee.Algorithms.IsEqual(ndwi_raw, None),
            None,
            ee.Number(ndwi_raw).divide(10000),
        )

        return ee.Feature(
            None,
            {
                "year": image.get("year"),
                "system_index": image.get("system:index"),
                # Reduced mosaic stores scaled integers (x10000)
                "ndwi_mean": ndwi_scaled,
            },
        )

    col = col.filter(ee.Filter.listContains("system:band_names", "ndwi_median"))
    feats = ee.FeatureCollection(col.map(summarize)) \
        .filter(ee.Filter.notNull(["ndwi_mean", "year"])) \
        .sort("year") \
        .getInfo()["features"]

    rows = []
    for ft in feats:
        props = ft["properties"]
        year = props.get("year")
        val = props.get("ndwi_mean")
        if year is None or val is None:
            continue
        rows.append(
            {
                "year": int(year),
                "ndwi_mean": float(val),
                "system_index": str(props.get("system_index", "")),
            }
        )

    rows.sort(key=lambda r: r["year"])
    return rows


def save_plot(rows: list[dict], output_png: Path, title: str) -> None:
    years = [r["year"] for r in rows]
    values = [r["ndwi_mean"] for r in rows]

    plt.figure(figsize=(10, 5))
    plt.plot(years, values, marker="o", linewidth=1.5)
    plt.title(title)
    plt.xlabel("Year")
    plt.ylabel("NDWI mean (unitless)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_png, dpi=160)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot NDWI mean over a GPKG area from reduced mosaic assets."
    )
    parser.add_argument(
        "--gpkg",
        default="../../inputs/gpk/Muestra_Lagogpk.gpkg",
        help="Input GPKG path (default: ../../inputs/gpk/Muestra_Lagogpk.gpkg)",
    )
    parser.add_argument(
        "--project",
        default="mapbiomas-chile",
        help="Earth Engine project (default: mapbiomas-chile)",
    )
    parser.add_argument(
        "--collection-asset",
        default="projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2",
        help="Mosaic ImageCollection asset path",
    )
    parser.add_argument(
        "--territory",
        default="CHILE",
        help="Territory metadata filter (default: CHILE)",
    )
    parser.add_argument(
        "--grid-name",
        default="SJ-18-X-B",
        help="Grid metadata filter (default: SJ-18-X-B)",
    )
    parser.add_argument(
        "--suffix",
        default="-REDUCED-NDVI-NDWI-v2",
        help="Substring filter in system:index to target reduced exports",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=30,
        help="Reduction scale in meters (default: 30)",
    )
    parser.add_argument(
        "--output",
        default="../outputs/ndwi_muestra_lago_timeseries.png",
        help="Output PNG filename (default: ../outputs/ndwi_muestra_lago_timeseries.png)",
    )
    args = parser.parse_args()

    gpkg_path = Path(args.gpkg)
    if not gpkg_path.exists():
        raise FileNotFoundError(f"GPKG not found: {gpkg_path}")

    ee.Initialize(project=args.project)
    region = gpkg_to_ee_geometry(gpkg_path)
    rows = fetch_ndwi_series(
        collection_asset=args.collection_asset,
        region=region,
        territory=args.territory,
        grid_name=args.grid_name,
        export_suffix_contains=args.suffix,
        scale=args.scale,
    )

    if not rows:
        raise RuntimeError(
            "No NDWI series found. Check filters: collection asset, territory, grid_name, suffix."
        )

    output_png = Path(args.output)
    title = f"NDWI mean over GPKG area ({args.grid_name})"
    save_plot(rows, output_png, title)

    print(f"Points plotted: {len(rows)}")
    print(f"First year: {rows[0]['year']}  Last year: {rows[-1]['year']}")
    print(f"Output PNG: {output_png.resolve()}")


if __name__ == "__main__":
    main()
