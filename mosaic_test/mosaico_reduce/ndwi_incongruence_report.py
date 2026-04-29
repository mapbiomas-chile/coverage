#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import statistics as st

import ee
import geopandas as gpd
import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NDWI incongruence report and plot")
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate a PNG plot of NDWI mean by year.",
    )
    parser.add_argument(
        "--plot-output",
        default="../outputs/ndwi_incongruence_plot.png",
        help="Output PNG path for plot (default: ../outputs/ndwi_incongruence_plot.png).",
    )
    return parser.parse_args()


def make_plot(rows: list[dict], output_path: str) -> None:
    years = [int(r["year"]) for r in rows]
    ndwi = [float(r["ndwi_mean"]) for r in rows]
    colors = ["#1f77b4" if y <= 2012 else "#ff7f0e" for y in years]

    plt.figure(figsize=(10, 4.5))
    plt.plot(years, ndwi, color="#444444", linewidth=1, alpha=0.6)
    plt.scatter(years, ndwi, c=colors, s=34, zorder=3)
    plt.axvline(2012.5, color="#888888", linestyle="--", linewidth=1)
    plt.title("NDWI mean by year (SJ-18-X-B)")
    plt.xlabel("Year")
    plt.ylabel("NDWI mean")
    plt.grid(alpha=0.2)
    plt.tight_layout()
    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Plot saved: {output_path}")


def summarize_reference_ndwi(
    geom: ee.Geometry,
    start_year: int,
    end_year: int,
) -> list[dict]:
    ref_col = ee.ImageCollection("LANDSAT/COMPOSITES/C02/T1_L2_32DAY_NDWI")
    out: list[dict] = []
    for year in range(start_year, end_year + 1):
        y0 = f"{year}-01-01"
        y1 = f"{year + 1}-01-01"
        yearly = ref_col.filterDate(y0, y1)
        count = int(yearly.size().getInfo())
        if count == 0:
            continue
        annual = yearly.mean()
        ndwi_raw = (
            annual.select("NDWI")
            .reduceRegion(
                ee.Reducer.mean(),
                geom,
                30,
                maxPixels=10**12,
                bestEffort=True,
            )
            .get("NDWI")
        )
        ndwi_val = ee.Number(ndwi_raw).getInfo() if ndwi_raw is not None else None
        if ndwi_val is None:
            continue
        out.append({"year": year, "ndwi_mean": float(ndwi_val)})
    return out


def make_overlay_plot(
    rows: list[dict],
    ref_rows: list[dict],
    output_path: str,
) -> None:
    years = [int(r["year"]) for r in rows]
    ndwi = [float(r["ndwi_mean"]) for r in rows]
    colors = ["#1f77b4" if y <= 2012 else "#ff7f0e" for y in years]

    plt.figure(figsize=(10, 4.5))
    plt.plot(years, ndwi, color="#444444", linewidth=1, alpha=0.6, label="Mosaico base")
    plt.scatter(years, ndwi, c=colors, s=34, zorder=3)
    if ref_rows:
        ref_years = [int(r["year"]) for r in ref_rows]
        ref_ndwi = [float(r["ndwi_mean"]) for r in ref_rows]
        plt.plot(
            ref_years,
            ref_ndwi,
            color="#2ca02c",
            linewidth=2,
            linestyle="--",
            marker="o",
            markersize=3,
            label="Landsat 32-day NDWI (annual mean)",
        )
    plt.axvline(2012.5, color="#888888", linestyle="--", linewidth=1)
    plt.title("NDWI mean by year (SJ-18-X-B)")
    plt.xlabel("Year")
    plt.ylabel("NDWI mean")
    plt.grid(alpha=0.2)
    plt.legend()
    plt.tight_layout()
    pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Plot saved: {output_path}")


def main() -> None:
    args = parse_args()
    ee.Initialize(project="mapbiomas-chile")
    gpkg = pathlib.Path(r"c:\Users\pedro\Documents\mosaico_test\inputs\gpk\Muestra_Lagogpk.gpkg")
    gdf = gpd.read_file(gpkg)
    if gdf.crs and str(gdf.crs).upper() != "EPSG:4326":
        gdf = gdf.to_crs(4326)
    geom = ee.Geometry(gdf.geometry.union_all().__geo_interface__)

    col = (
        ee.ImageCollection("projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2")
        .filterMetadata("territory", "equals", "CHILE")
        .filterMetadata("grid_name", "equals", "SJ-18-X-B")
        .filter(ee.Filter.listContains("system:band_names", "ndwi_median"))
    )

    def summarize(img: ee.Image) -> ee.Feature:
        ndwi_raw = (
            img.select("ndwi_median")
            .reduceRegion(
                ee.Reducer.mean(),
                geom,
                30,
                maxPixels=10**12,
                bestEffort=True,
            )
            .get("ndwi_median")
        )
        # In mosaico assets, many index bands are stored with scale/offset convention:
        # stored_ndwi ~= (physical_ndwi + 1) * 10000
        # Convert to physical NDWI scale [-1, 1] for cross-dataset comparison.
        ndwi = ee.Algorithms.If(
            ee.Algorithms.IsEqual(ndwi_raw, None),
            None,
            ee.Number(ndwi_raw).divide(10000).subtract(1),
        )
        return ee.Feature(
            None,
            {
                "year": img.get("year"),
                "satellite": img.get("satellite"),
                "version": img.get("version"),
                "system_index": img.get("system:index"),
                "ndwi_mean": ndwi,
            },
        )

    feats = (
        ee.FeatureCollection(col.map(summarize))
        .filter(ee.Filter.notNull(["year", "ndwi_mean"]))
        .sort("year")
        .getInfo()["features"]
    )
    rows = [f["properties"] for f in feats]
    rows.sort(key=lambda r: int(r["year"]))

    pre = [float(r["ndwi_mean"]) for r in rows if int(r["year"]) <= 2012]
    post = [float(r["ndwi_mean"]) for r in rows if int(r["year"]) >= 2013]
    print(f"n={len(rows)} years={rows[0]['year']}..{rows[-1]['year']}")
    print(
        "pre2013 "
        f"n={len(pre)} mean={sum(pre)/len(pre):.4f} median={st.median(pre):.4f} "
        f"range=({min(pre):.4f},{max(pre):.4f})"
    )
    print(
        "post2012 "
        f"n={len(post)} mean={sum(post)/len(post):.4f} median={st.median(post):.4f} "
        f"range=({min(post):.4f},{max(post):.4f})"
    )
    print("year\tsat\tndwi_mean\tsystem_index")
    for r in rows:
        print(
            f"{int(r['year'])}\t{r.get('satellite')}\t{float(r['ndwi_mean']):.4f}\t{r.get('system_index')}"
        )
    if args.plot:
        min_year = int(rows[0]["year"])
        max_year = int(rows[-1]["year"])
        ref_rows = summarize_reference_ndwi(geom, min_year, max_year)
        print(f"reference_ndwi_rows={len(ref_rows)} dataset=LANDSAT/COMPOSITES/C02/T1_L2_32DAY_NDWI")
        make_overlay_plot(rows, ref_rows, args.plot_output)


if __name__ == "__main__":
    main()
