#!/usr/bin/env python3
"""
Plot annual time series for all *_median bands over a GPKG area.

Default usage (from mosaico_reduce):
    python plot_all_bands_gpkg.py
"""

from __future__ import annotations

import argparse
import math
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

    geom = gdf.geometry.union_all()
    if geom.is_empty:
        raise ValueError(f"Unified geometry is empty: {gpkg_path}")

    return ee.Geometry(geom.__geo_interface__)


def to_real_value(band: str, value: float) -> float:
    # Reflectance/index medians in this workflow are typically stored x10000.
    if band.endswith("_median"):
        return float(value) / 10000.0
    return float(value)


def fetch_series(
    collection_asset: str,
    region: ee.Geometry,
    territory: str,
    grid_name: str,
    export_suffix_contains: str,
    scale: int,
    band_limit: int | None,
) -> tuple[list[str], list[dict]]:
    col = ee.ImageCollection(collection_asset) \
        .filterMetadata("territory", "equals", territory) \
        .filterMetadata("grid_name", "equals", grid_name)

    if export_suffix_contains.strip():
        col = col.filter(ee.Filter.stringContains("system:index", export_suffix_contains.strip()))

    first = ee.Image(col.first())
    band_names = first.bandNames().getInfo()
    median_bands = sorted([b for b in band_names if b.endswith("_median")])
    if not median_bands:
        raise RuntimeError("No *_median bands found in selected collection/images.")

    if band_limit is not None and band_limit > 0:
        median_bands = median_bands[:band_limit]

    def summarize(image: ee.Image) -> ee.Feature:
        stats = image.select(median_bands).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=scale,
            maxPixels=1_000_000_000_000,
            bestEffort=True,
        )
        props = ee.Dictionary(stats) \
            .set("year", image.get("year")) \
            .set("system_index", image.get("system:index")) \
            .set("satellite", image.get("satellite"))
        return ee.Feature(None, props)

    feats = ee.FeatureCollection(col.map(summarize)) \
        .filter(ee.Filter.notNull(["year"])) \
        .sort("year") \
        .getInfo()["features"]

    rows = []
    for ft in feats:
        p = ft["properties"]
        year = p.get("year")
        if year is None:
            continue
        row = {
            "year": int(year),
            "system_index": str(p.get("system_index", "")),
            "satellite": str(p.get("satellite", "")),
        }
        for b in median_bands:
            val = p.get(b)
            row[b] = None if val is None else to_real_value(b, float(val))
        rows.append(row)

    rows.sort(key=lambda r: r["year"])
    return median_bands, rows


def save_multi_panel_plot(bands: list[str], rows: list[dict], output_png: Path, title: str) -> None:
    cols = 3
    n = len(bands)
    rows_n = math.ceil(n / cols)
    fig, axes = plt.subplots(rows_n, cols, figsize=(18, max(4, rows_n * 3)), squeeze=False)
    fig.suptitle(title, fontsize=14)

    years = [r["year"] for r in rows]
    for i, band in enumerate(bands):
        ax = axes[i // cols][i % cols]
        y = [r.get(band) for r in rows]
        x_plot = [x for x, v in zip(years, y) if v is not None]
        y_plot = [v for v in y if v is not None]
        ax.plot(x_plot, y_plot, marker="o", linewidth=1.2, markersize=3)
        ax.set_title(band, fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis="both", labelsize=8)

    for j in range(n, rows_n * cols):
        axes[j // cols][j % cols].axis("off")

    plt.tight_layout(rect=(0, 0.02, 1, 0.96))
    output_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_png, dpi=180)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot annual time series for all *_median bands over a GPKG area."
    )
    parser.add_argument("--gpkg", default="../../inputs/gpk/Muestra_Lagogpk.gpkg")
    parser.add_argument("--project", default="mapbiomas-chile")
    parser.add_argument(
        "--collection-asset",
        default="projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2",
    )
    parser.add_argument("--territory", default="CHILE")
    parser.add_argument("--grid-name", default="SJ-18-X-B")
    parser.add_argument(
        "--suffix",
        default="-REDUCED-NDVI-NDWI-v2",
        help="Filter by substring in system:index. Use empty string for all.",
    )
    parser.add_argument("--scale", type=int, default=30)
    parser.add_argument(
        "--band-limit",
        type=int,
        default=0,
        help="Optional cap of bands to plot (0 = all).",
    )
    parser.add_argument(
        "--output",
        default="../outputs/all_bands_median_timeseries.png",
        help="Output PNG filename.",
    )
    args = parser.parse_args()

    gpkg_path = Path(args.gpkg)
    if not gpkg_path.exists():
        raise FileNotFoundError(f"GPKG not found: {gpkg_path}")

    ee.Initialize(project=args.project)
    region = gpkg_to_ee_geometry(gpkg_path)
    bands, rows = fetch_series(
        collection_asset=args.collection_asset,
        region=region,
        territory=args.territory,
        grid_name=args.grid_name,
        export_suffix_contains=args.suffix,
        scale=args.scale,
        band_limit=None if args.band_limit <= 0 else args.band_limit,
    )

    if not rows:
        raise RuntimeError("No rows found with the current filters.")

    output_png = Path(args.output)
    save_multi_panel_plot(
        bands,
        rows,
        output_png,
        title=f"All *_median bands over GPKG area ({args.grid_name})",
    )

    print(f"Years: {rows[0]['year']}..{rows[-1]['year']} (n={len(rows)})")
    print(f"Bands plotted: {len(bands)}")
    print(f"Output PNG: {output_png.resolve()}")


if __name__ == "__main__":
    main()
