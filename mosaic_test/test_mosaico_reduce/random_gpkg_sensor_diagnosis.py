#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import random
import statistics as st
from pathlib import Path

import ee
import geopandas as gpd
from shapely.geometry import Point, shape


GRID_ASSET = "projects/mapbiomas-workspace/AUXILIAR/cim-world-1-250000"
COLLECTION_ASSET = "projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2"


def get_tile_polygon(tile_name: str):
    fc = ee.FeatureCollection(GRID_ASSET).filter(ee.Filter.eq("name", tile_name))
    if fc.size().getInfo() == 0:
        raise ValueError(f"Tile not found: {tile_name}")
    geom_geojson = ee.Feature(fc.first()).geometry().getInfo()
    return shape(geom_geojson)


def generate_random_points_gpkg(
    polygon,
    n_points: int,
    seed: int,
    output_gpkg: Path,
) -> gpd.GeoDataFrame:
    rng = random.Random(seed)
    minx, miny, maxx, maxy = polygon.bounds
    points = []
    i = 0
    while len(points) < n_points:
        i += 1
        if i > n_points * 2000:
            raise RuntimeError("Too many attempts generating random points in tile polygon.")
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        p = Point(x, y)
        if polygon.contains(p):
            points.append(p)

    gdf = gpd.GeoDataFrame(
        {"sample_id": list(range(1, n_points + 1))},
        geometry=points,
        crs="EPSG:4326",
    )
    gdf.to_file(output_gpkg, driver="GPKG")
    return gdf


def build_samples_fc(gdf: gpd.GeoDataFrame, buffer_m: float) -> ee.FeatureCollection:
    feats = []
    for _, row in gdf.iterrows():
        p = row.geometry
        geom = ee.Geometry.Point([float(p.x), float(p.y)]).buffer(buffer_m)
        feat = ee.Feature(geom, {"sample_id": int(row["sample_id"])})
        feats.append(feat)
    return ee.FeatureCollection(feats)


def get_images(tile: str, territory: str, suffix: str):
    col = (
        ee.ImageCollection(COLLECTION_ASSET)
        .filterMetadata("territory", "equals", territory)
        .filterMetadata("grid_name", "equals", tile)
        .filter(ee.Filter.listContains("system:band_names", "ndwi_median"))
    )
    if suffix.strip():
        col = col.filter(ee.Filter.stringContains("system:index", suffix.strip()))

    feats = (
        ee.FeatureCollection(
            col.map(
                lambda img: ee.Feature(
                    None,
                    {
                        "idx": img.get("system:index"),
                        "year": img.get("year"),
                        "satellite": img.get("satellite"),
                    },
                )
            )
        )
        .filter(ee.Filter.notNull(["idx", "year", "satellite"]))
        .sort("year")
        .getInfo()["features"]
    )
    rows = [f["properties"] for f in feats]
    rows.sort(key=lambda r: (int(r["year"]), str(r["idx"])))
    return rows


def summarize_by_sample(
    images_meta: list[dict],
    samples_fc: ee.FeatureCollection,
    scale: int,
) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for im in images_meta:
        idx = str(im["idx"])
        year = int(im["year"])
        sat = str(im["satellite"]).lower()
        img = ee.Image(f"{COLLECTION_ASSET}/{idx}").select("ndwi_median")
        reduced = img.reduceRegions(
            collection=samples_fc,
            reducer=ee.Reducer.mean(),
            scale=scale,
        ).getInfo()["features"]

        for ft in reduced:
            p = ft.get("properties", {})
            sid = int(p["sample_id"])
            val = p.get("mean")
            if val is None:
                continue
            ndwi = float(val) / 10000.0
            out.setdefault(sid, []).append(
                {"year": year, "satellite": sat, "ndwi": ndwi, "idx": idx}
            )
    for sid in out:
        out[sid].sort(key=lambda r: (r["year"], r["idx"]))
    return out


def mean_or_none(vals: list[float]):
    return None if not vals else sum(vals) / len(vals)


def run_diagnosis(sample_series: dict[int, list[dict]]):
    rows = []
    for sid, series in sample_series.items():
        pre = [r["ndwi"] for r in series if r["year"] <= 2012]
        post = [r["ndwi"] for r in series if r["year"] >= 2013]
        l57 = [r["ndwi"] for r in series if r["satellite"] in {"l5", "l7"}]
        l8 = [r["ndwi"] for r in series if r["satellite"] == "l8"]
        l9 = [r["ndwi"] for r in series if r["satellite"] == "l9"]

        pre_m = mean_or_none(pre)
        post_m = mean_or_none(post)
        if pre_m is not None and post_m is not None and pre_m != 0:
            delta_pct = ((post_m - pre_m) / pre_m) * 100.0
        else:
            delta_pct = None

        rows.append(
            {
                "sample_id": sid,
                "n_obs": len(series),
                "pre2013_mean": pre_m,
                "post2012_mean": post_m,
                "delta_pct": delta_pct,
                "l57_mean": mean_or_none(l57),
                "l8_mean": mean_or_none(l8),
                "l9_mean": mean_or_none(l9),
            }
        )
    rows.sort(key=lambda r: r["sample_id"])
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    headers = [
        "sample_id",
        "n_obs",
        "pre2013_mean",
        "post2012_mean",
        "delta_pct",
        "l57_mean",
        "l8_mean",
        "l9_mean",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate random GPKG samples in tile and diagnose sensor discontinuity."
    )
    parser.add_argument("--tile", default="SJ-18-X-B")
    parser.add_argument("--territory", default="CHILE")
    parser.add_argument("--project", default="mapbiomas-chile")
    parser.add_argument("--n-points", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--buffer-m", type=float, default=120.0)
    parser.add_argument("--scale", type=int, default=30)
    parser.add_argument("--suffix", default="", help="Filter system:index by substring.")
    parser.add_argument("--output-gpkg", default="random_samples_sj18xb.gpkg")
    parser.add_argument("--output-csv", default="sensor_discontinuity_random_samples.csv")
    args = parser.parse_args()

    ee.Initialize(project=args.project)

    tile_poly = get_tile_polygon(args.tile)
    gpkg_path = Path(args.output_gpkg)
    gdf = generate_random_points_gpkg(
        polygon=tile_poly,
        n_points=args.n_points,
        seed=args.seed,
        output_gpkg=gpkg_path,
    )
    samples_fc = build_samples_fc(gdf, args.buffer_m)
    images = get_images(args.tile, args.territory, args.suffix)
    if not images:
        raise RuntimeError("No images found for current filters.")

    sample_series = summarize_by_sample(images, samples_fc, args.scale)
    diag_rows = run_diagnosis(sample_series)
    csv_path = Path(args.output_csv)
    write_csv(csv_path, diag_rows)

    deltas = [r["delta_pct"] for r in diag_rows if r["delta_pct"] is not None]
    n_neg = len([d for d in deltas if d < 0])
    n_total = len(deltas)
    median_delta = st.median(deltas) if deltas else None

    print(f"Random samples GPKG: {gpkg_path.resolve()}")
    print(f"Diagnosis CSV: {csv_path.resolve()}")
    print(f"Images analyzed: {len(images)}")
    print(f"Samples with pre/post comparison: {n_total}")
    if median_delta is not None:
        print(f"Median delta post-vs-pre (%): {median_delta:.2f}")
        print(f"Negative deltas: {n_neg}/{n_total} ({(100*n_neg/n_total):.1f}%)")
        if n_total > 0 and (n_neg / n_total) >= 0.7:
            print("Conclusion: discontinuity is spatially widespread; likely sensor-era effect.")
        else:
            print("Conclusion: discontinuity is mixed spatially; inspect local context.")


if __name__ == "__main__":
    main()
