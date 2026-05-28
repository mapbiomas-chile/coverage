#!/usr/bin/env python3
"""
Serial / single-threaded Landsat C2 L2 SR download for ONE MGRS tile.

Goal of this script: measure real download speed for Planetary Computer
COG assets, scene by scene and band by band, with no Dask, no parallelism.

We want to answer:
    - Can we sustain the throughput needed to mosaic all of Chile,
      quarterly, for ~30 years?
    - Does Microsoft Planetary Computer throttle the connection after
      N requests / N bytes / N minutes?
    - How long does each phase take (STAC, per-COG read, composite, write)?

Strategy:
    1. STAC search on Planetary Computer for the MGRS tile bbox.
    2. Choose N scenes (one best per WRS path/row by default).
    3. For each (scene, band) read the COG into a UTM target grid using
       rasterio + WarpedVRT — strictly sequential, one HTTPS connection at a time.
       Log URL, elapsed, bytes, MB/s.
    4. Median composite across scenes (in-memory NumPy).
    5. Write 7-band GeoTIFF.

Usage:
    python fetch_landsat_serial_pc.py \\
        --mgrs 19HCD \\
        --datetime 2024-01-01/2024-03-31 \\
        --max-scenes 5

    python fetch_landsat_serial_pc.py --mgrs 19HCD --datetime 2024-01-01/2024-12-31 \\
        --max-scenes 20   # bigger throttling probe

Outputs:
    GeoTIFF:  /mnt/e/mapbiomas/coverage/data/serial_test/mgrs_<TILE>_<period>.tif
    Log:      /mnt/e/mapbiomas/coverage/data/serial_test/log_<TILE>_<period>.log
    Metrics:  /mnt/e/mapbiomas/coverage/data/serial_test/metrics_<TILE>_<period>.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from contextlib import contextmanager

from fetch_landsat_mosaic_pc import (
    COLLECTION,
    DEFAULT_DATETIME,
    LANDSAT_SR_OFFSET,
    LANDSAT_SR_SCALE,
    MGRS_TILE_SIZE_KM,
    OLI_SR_ASSETS,
    PC_STAC_URL,
    SSL4EO_BAND_NAMES,
    epsg_from_mgrs_tile,
    mgrs_tile_bbox_wgs84,
    normalize_mgrs_tile,
    open_catalog,
    select_scenes,
    wrs_path_row,
)


@contextmanager
def measure_proc_recv_bytes():
    """
    Per-process bytes received via read() syscalls (Linux only, via
    /proc/<pid>/io read_chars — psutil exposes it as Process.io_counters().read_chars).

    `read_chars` counts bytes pulled into the process from any fd (sockets, pipes,
    disk). For COG reads via GDAL/libcurl this is dominated by HTTPS socket recvs,
    so it's an accurate per-worker network counter — unlike system-wide
    net_io_counters which gets contaminated by other parallel workers.

    Falls back gracefully if psutil or read_chars is unavailable (non-Linux).
    """
    box: dict[str, int | None] = {"delta": None}
    try:
        import psutil

        proc = psutil.Process()
        ctr = proc.io_counters()
        before = getattr(ctr, "read_chars", None)
        if before is None:
            yield box
            return
        yield box
        after = proc.io_counters().read_chars
        box["delta"] = after - before
    except (ImportError, AttributeError, OSError):
        yield box
from mosaic_logging import get_logger, resolve_log_level, setup_logging

DEFAULT_DATA_DIR = Path("/mnt/e/mapbiomas/coverage/data/serial_test")


@dataclass
class AssetTiming:
    scene_id: str
    asset: str
    url: str
    bytes_read: int
    seconds: float
    http_status: str

    @property
    def mb_per_s(self) -> float:
        return (self.bytes_read / (1024 * 1024)) / self.seconds if self.seconds > 0 else 0.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mgrs", default="19HCD", help="MGRS tile id (default: 19HCD)")
    p.add_argument("--mgrs-size-km", type=float, default=MGRS_TILE_SIZE_KM)
    p.add_argument("--datetime", default=DEFAULT_DATETIME, help="ISO interval, e.g. 2024-01-01/2024-03-31")
    p.add_argument("--max-cloud", type=float, default=25.0)
    p.add_argument("--max-scenes", type=int, default=5)
    p.add_argument(
        "--platform",
        choices=("any", "landsat-8", "landsat-9"),
        default="any",
    )
    p.add_argument("--no-diverse-paths", action="store_true")
    p.add_argument("--resolution", type=float, default=30.0)
    p.add_argument("--epsg", type=int, default=None, help="Override UTM EPSG (default: from MGRS)")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--composite", choices=("median", "mean"), default="median")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def datetime_slug(s: str) -> str:
    return s.replace("/", "_").replace(":", "")


def target_grid(bbox_wgs84, epsg: int, resolution: float):
    """Build a target raster grid (transform, width, height) in EPSG snapped to resolution."""
    import rasterio.transform
    from pyproj import Transformer

    t = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    xs, ys = [], []
    for lon, lat in [
        (bbox_wgs84[0], bbox_wgs84[1]),
        (bbox_wgs84[0], bbox_wgs84[3]),
        (bbox_wgs84[2], bbox_wgs84[1]),
        (bbox_wgs84[2], bbox_wgs84[3]),
    ]:
        x, y = t.transform(lon, lat)
        xs.append(x)
        ys.append(y)
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minx = (minx // resolution) * resolution
    miny = (miny // resolution) * resolution
    maxx = ((maxx // resolution) + 1) * resolution
    maxy = ((maxy // resolution) + 1) * resolution
    width = int(round((maxx - minx) / resolution))
    height = int(round((maxy - miny) / resolution))
    transform = rasterio.transform.from_origin(minx, maxy, resolution, resolution)
    return transform, width, height


def read_cog_to_grid(href: str, target_crs: str, target_transform, width: int, height: int):
    """Single sequential COG read into the target grid via WarpedVRT, returns uint16 array."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT

    gdal_env = {
        "GDAL_HTTP_MULTIRANGE": "YES",
        "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "VSI_CACHE": "TRUE",
        "VSI_CACHE_SIZE": "67108864",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
    }
    with rasterio.Env(**gdal_env):
        with rasterio.open(href) as src:
            with WarpedVRT(
                src,
                crs=target_crs,
                transform=target_transform,
                width=width,
                height=height,
                resampling=Resampling.nearest,
            ) as vrt:
                return vrt.read(1)


def fetch_assets_serial(
    items,
    bbox_wgs84,
    epsg: int,
    resolution: float,
):
    """Read every (scene, band) one at a time. Returns (stack, timings, target_meta)."""
    import numpy as np

    log = get_logger()
    transform, width, height = target_grid(bbox_wgs84, epsg, resolution)
    log.info("Target grid: %d × %d px @ %.0f m (EPSG:%d)", width, height, resolution, epsg)
    log.info("Target extent (UTM): minx=%.1f miny=%.1f maxx=%.1f maxy=%.1f",
             transform.c, transform.f - height * resolution,
             transform.c + width * resolution, transform.f)

    n_scenes = len(items)
    n_bands = len(OLI_SR_ASSETS)
    stack = np.full((n_scenes, n_bands, height, width), np.iinfo(np.uint16).max, dtype=np.uint16)
    timings: list[AssetTiming] = []

    total_assets = n_scenes * n_bands
    t_all_start = time.perf_counter()
    bytes_total = 0

    for s_idx, item in enumerate(items):
        log.info("―" * 56)
        log.info("Scene %d/%d: %s  (cloud=%s%%)",
                 s_idx + 1, n_scenes, item.id,
                 item.properties.get("eo:cloud_cover", "?"))
        scene_t0 = time.perf_counter()
        scene_bytes = 0

        for b_idx, asset_name in enumerate(OLI_SR_ASSETS):
            asset = item.assets.get(asset_name)
            if asset is None:
                log.warning("  asset %s missing in %s — skipping", asset_name, item.id)
                continue
            href = asset.href
            asset_t0 = time.perf_counter()
            err_msg = "ok"
            try:
                with measure_proc_recv_bytes() as io_box:
                    arr = read_cog_to_grid(href, f"EPSG:{epsg}", transform, width, height)
                stack[s_idx, b_idx] = arr
                bytes_read = io_box.get("delta") or 0
            except Exception as exc:
                bytes_read = 0
                err_msg = type(exc).__name__ + ": " + str(exc)[:120]
                log.error("  asset %s failed: %s", asset_name, err_msg)
            elapsed = time.perf_counter() - asset_t0
            timings.append(AssetTiming(
                scene_id=item.id,
                asset=asset_name,
                url=href.split("?")[0],  # drop SAS query for logs
                bytes_read=bytes_read,
                seconds=elapsed,
                http_status=err_msg,
            ))
            scene_bytes += bytes_read
            bytes_total += bytes_read

            done = s_idx * n_bands + b_idx + 1
            mb = bytes_read / (1024 * 1024)
            rate = mb / elapsed if elapsed > 0 else 0
            log.info(
                "  [%d/%d] %-8s %s  %5.1fs  %6.1f MiB  %5.1f MiB/s  %s",
                done, total_assets, asset_name, item.id, elapsed, mb, rate, err_msg,
            )

        scene_total = time.perf_counter() - scene_t0
        scene_mb = scene_bytes / (1024 * 1024)
        scene_rate = scene_mb / scene_total if scene_total > 0 else 0
        log.info(
            "  scene total: %.1fs  %.1f MiB  %.1f MiB/s",
            scene_total, scene_mb, scene_rate,
        )

    total_s = time.perf_counter() - t_all_start
    total_mb = bytes_total / (1024 * 1024)
    log.info("―" * 56)
    log.info(
        "All assets done — %d files, %.1fs, %.1f MiB total, %.1f MiB/s avg",
        len(timings), total_s, total_mb, total_mb / total_s if total_s > 0 else 0,
    )

    target_meta = {
        "crs": f"EPSG:{epsg}",
        "transform": transform,
        "width": width,
        "height": height,
    }
    return stack, timings, target_meta, total_s, bytes_total


def composite_and_write(stack, target_meta, out_path: Path, composite: str = "median") -> tuple[float, int]:
    """Median/mean across scenes, scale to reflectance, write 7-band GeoTIFF. Returns (seconds, bytes)."""
    import numpy as np
    import rasterio

    log = get_logger()
    nodata = np.iinfo(np.uint16).max

    log.info("Compositing: %s across %d scenes (in-memory NumPy) …", composite, stack.shape[0])
    t0 = time.perf_counter()
    masked = np.ma.masked_equal(stack, nodata)
    if composite == "mean":
        agg = masked.mean(axis=0)
    else:
        agg = np.ma.median(masked, axis=0)
    agg = agg.filled(np.nan).astype("float32")
    refl = agg * LANDSAT_SR_SCALE + LANDSAT_SR_OFFSET
    np.clip(refl, 0.0, 1.0, out=refl)
    comp_s = time.perf_counter() - t0
    log.info("Composite done in %.1fs — shape=%s dtype=%s", comp_s, refl.shape, refl.dtype)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Writing GeoTIFF → %s (compress=deflate) …", out_path)
    t1 = time.perf_counter()
    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        width=target_meta["width"],
        height=target_meta["height"],
        count=refl.shape[0],
        dtype="float32",
        crs=target_meta["crs"],
        transform=target_meta["transform"],
        nodata=float("nan"),
        compress="deflate",
        predictor=2,
        tiled=True,
    ) as dst:
        for i in range(refl.shape[0]):
            dst.write(refl[i], i + 1)
            dst.set_band_description(i + 1, SSL4EO_BAND_NAMES[i])
    write_s = time.perf_counter() - t1
    size_bytes = out_path.stat().st_size
    log.info("Write done in %.1fs — %.1f MiB", write_s, size_bytes / (1024 * 1024))
    return comp_s + write_s, size_bytes


def save_metrics(csv_path: Path, timings: list[AssetTiming]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["idx", "scene_id", "asset", "seconds", "bytes", "mib", "mib_per_s", "status", "url"])
        for i, t in enumerate(timings, 1):
            w.writerow([
                i, t.scene_id, t.asset,
                round(t.seconds, 3), t.bytes_read,
                round(t.bytes_read / (1024 * 1024), 3),
                round(t.mb_per_s, 3),
                t.http_status, t.url,
            ])


def main() -> int:
    args = parse_args()
    tile = normalize_mgrs_tile(args.mgrs)
    slug = datetime_slug(args.datetime)

    out_dir = args.data_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tif = out_dir / f"mgrs_{tile}_{slug}.tif"
    log_file = out_dir / f"log_{tile}_{slug}.log"
    metrics_csv = out_dir / f"metrics_{tile}_{slug}.csv"

    setup_logging(
        level=resolve_log_level(verbose=args.verbose, quiet=False),
        log_file=log_file,
        tile=tile,
    )
    log = get_logger()

    log.info("=" * 60)
    log.info("Serial Landsat fetch — throttling / throughput probe")
    log.info("Tile: %s  datetime: %s  max_scenes: %d  composite: %s",
             tile, args.datetime, args.max_scenes, args.composite)
    log.info("Output: %s", out_tif)
    log.info("Metrics CSV: %s", metrics_csv)
    log.info("Log file: %s", log_file)

    # Phase 1: STAC search
    log.info("─" * 56)
    log.info("Phase 1/3: STAC search")
    bbox = mgrs_tile_bbox_wgs84(tile, size_km=args.mgrs_size_km)
    epsg = args.epsg if args.epsg is not None else epsg_from_mgrs_tile(tile)
    log.info("BBox WGS84: %s", bbox)
    log.info("UTM EPSG:%d", epsg)

    catalog = open_catalog()
    query = {"eo:cloud_cover": {"lt": args.max_cloud}}
    if args.platform != "any":
        query["platform"] = {"eq": args.platform}

    t0 = time.perf_counter()
    items_all = list(catalog.search(
        collections=[COLLECTION],
        bbox=list(bbox),
        datetime=args.datetime,
        query=query,
        max_items=max(100, args.max_scenes * 15),
    ).items())
    stac_s = time.perf_counter() - t0
    log.info("STAC: %d candidate(s) in %.2fs", len(items_all), stac_s)
    if not items_all:
        log.error("No scenes found.")
        return 1

    items = select_scenes(items_all, args.max_scenes, diverse_paths=not args.no_diverse_paths)
    paths = {wrs_path_row(it) for it in items}
    log.info("Selected %d scene(s) across %d WRS path/row:", len(items), len(paths))
    for i, it in enumerate(items, 1):
        cc = it.properties.get("eo:cloud_cover", "?")
        dt = it.properties.get("datetime", "?")
        path, row = wrs_path_row(it)
        log.info("  [%d/%d] %s  path/row=%s/%s  cloud=%s%%  %s",
                 i, len(items), it.id, path, row, cc, dt)

    # Phase 2: serial COG reads
    log.info("─" * 56)
    log.info("Phase 2/3: Serial COG reads (one HTTPS request at a time)")
    stack, timings, target_meta, cog_s, bytes_total = fetch_assets_serial(
        items, bbox, epsg, args.resolution,
    )

    # Phase 3: composite + write
    log.info("─" * 56)
    log.info("Phase 3/3: Composite + write GeoTIFF")
    comp_write_s, output_bytes = composite_and_write(
        stack, target_meta, out_tif, composite=args.composite,
    )

    # Summary
    total_s = stac_s + cog_s + comp_write_s
    total_mb = bytes_total / (1024 * 1024)
    log.info("=" * 60)
    log.info("Summary:")
    log.info("  STAC search:        %7.2fs", stac_s)
    log.info("  COG reads (serial): %7.2fs   %.1f MiB    %.1f MiB/s avg",
             cog_s, total_mb, total_mb / cog_s if cog_s > 0 else 0)
    log.info("  composite + write:  %7.2fs   out=%.1f MiB", comp_write_s, output_bytes / (1024 * 1024))
    log.info("  total:              %7.2fs", total_s)
    log.info("Per-asset stats (min / median / max seconds):")
    if timings:
        secs = sorted(t.seconds for t in timings)
        rates = sorted(t.mb_per_s for t in timings if t.bytes_read > 0)
        log.info("  seconds:  min=%.2f  median=%.2f  max=%.2f", secs[0], secs[len(secs) // 2], secs[-1])
        if rates:
            log.info("  MiB/s:    min=%.2f  median=%.2f  max=%.2f",
                     rates[0], rates[len(rates) // 2], rates[-1])
        errs = [t for t in timings if t.http_status != "ok"]
        if errs:
            log.warning("  %d asset(s) failed — see CSV", len(errs))

    save_metrics(metrics_csv, timings)
    log.info("Metrics CSV written: %s", metrics_csv)
    log.info("GeoTIFF written:    %s", out_tif)
    return 0


if __name__ == "__main__":
    sys.exit(main())
