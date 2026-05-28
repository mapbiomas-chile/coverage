#!/usr/bin/env python3
"""
Batch Landsat C2 L2 SR mosaics for MGRS 100 km tiles (parallel workers).

Each worker processes ONE MGRS tile using the same serial band-by-band read
path as fetch_landsat_serial_pc.py (rasterio + WarpedVRT, one HTTPS request
at a time per tile). Different tiles run in parallel.

Process model:
    - Workers are spawned with multiprocessing context "spawn" → each worker
      is a fresh Python interpreter (no fork/copy-on-write of parent state).
      Heavy, isolated processes — not threads — so GDAL state and per-process
      I/O counters stay clean and independent across workers.

Metrics:
    - Per-asset bytes are measured per-process via psutil read_chars (Linux
      /proc/<pid>/io), which counts bytes read from sockets by THIS worker.
      So per-asset MiB/s is accurate per tile, not contaminated by other
      parallel workers (unlike a system-wide net counter).

Live visibility:
    - Each worker streams its full per-(scene, asset) progress log to the
      inherited stdout, prefixed by [TILE]. Full detail is also written to
      the per-tile log file.

Per-tile outputs (under --data-dir):
    <slug>/mgrs_<TILE>_landsat_sr.tif        7-band float32 SR mosaic
    logs/<slug>/<TILE>.log                   per-tile log (serial-style)
    metrics/<slug>/metrics_<TILE>.csv        per-asset timing CSV

Usage:
    python fetch_landsat_mosaic_batch_pc.py \\
        --tiles 18FXH,18GXP,18HYD,19HCD,19JCJ,19KDU \\
        --workers 6 \\
        --datetime 2024-01-01/2024-03-31 \\
        --max-scenes 5 \\
        --data-dir ~/data/mosaic_parallel_test
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from fetch_landsat_mosaic_pc import (
    COLLECTION,
    DEFAULT_DATETIME,
    MGRS_TILE_SIZE_KM,
    epsg_from_mgrs_tile,
    mgrs_tile_bbox_wgs84,
    normalize_mgrs_tile,
    open_catalog,
    select_scenes,
    wrs_path_row,
)
from fetch_landsat_serial_pc import (
    composite_and_write,
    datetime_slug,
    fetch_assets_serial,
    save_metrics,
)
from mosaic_logging import get_logger, resolve_log_level, setup_logging

DEFAULT_DATA_DIR = Path("/mnt/e/mapbiomas/coverage/data/landsat_mosaic")


@dataclass(frozen=True)
class TileJob:
    tile: str
    datetime_range: str
    max_cloud: float
    platform: str
    max_scenes: int
    diverse_paths: bool
    composite: str
    resolution: float
    epsg: int | None
    mgrs_size_km: float
    out_tif: Path
    log_file: Path
    metrics_csv: Path
    skip_existing: bool
    verbose: bool


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Parallel Landsat C2 L2 SR mosaics for MGRS tiles "
            "(one tile per worker, serial band-by-band reads via rasterio+WarpedVRT)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--tiles",
        required=True,
        help="Comma-separated MGRS 100 km tile ids (e.g. 19HCD,18GXR). Bounds/EPSG via mgrs library.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N tiles from --tiles list (0 = all)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Parallel worker processes (one tile per worker at a time)",
    )
    p.add_argument(
        "--datetime",
        default=DEFAULT_DATETIME,
        help="ISO interval for STAC search, e.g. 2024-01-01/2024-03-31",
    )
    p.add_argument("--max-cloud", type=float, default=25.0)
    p.add_argument("--max-scenes", type=int, default=5)
    p.add_argument(
        "--no-diverse-paths",
        action="store_true",
        help="Do not pick best scene per WRS path/row (not recommended for MGRS tiles)",
    )
    p.add_argument(
        "--platform",
        choices=("any", "landsat-8", "landsat-9"),
        default="any",
    )
    p.add_argument(
        "--composite",
        choices=("median", "mean"),
        default="median",
        help="Multi-scene compositing (median recommended)",
    )
    p.add_argument("--resolution", type=float, default=30.0)
    p.add_argument(
        "--epsg",
        type=int,
        default=None,
        help="Override UTM EPSG for all tiles (default: per-tile from MGRS)",
    )
    p.add_argument("--mgrs-size-km", type=float, default=MGRS_TILE_SIZE_KM)
    p.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Output directory (default: {DEFAULT_DATA_DIR})",
    )
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip tiles whose output GeoTIFF already exists",
    )
    p.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="JSONL manifest path (default: <data-dir>/manifest_<slug>.jsonl)",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="DEBUG in worker logs",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Minimal parent console output; per-tile logs always written",
    )
    p.add_argument("--dry-run", action="store_true", help="List tiles and exit")
    return p.parse_args()


def parse_tile_ids(tiles_arg: str) -> list[str]:
    """Parse comma-separated MGRS ids; validate format and grid cell via mgrs."""
    parts = [p.strip() for p in tiles_arg.split(",") if p.strip()]
    if not parts:
        raise ValueError("--tiles must list at least one MGRS id (e.g. 19HCD,18GXR)")
    ids: list[str] = []
    seen: set[str] = set()
    for part in parts:
        tile = normalize_mgrs_tile(part)
        if tile in seen:
            continue
        try:
            mgrs_tile_bbox_wgs84(tile)
        except Exception as exc:
            raise ValueError(f"Invalid or unknown MGRS tile {tile!r}: {exc}") from exc
        seen.add(tile)
        ids.append(tile)
    return ids


def build_jobs(args: argparse.Namespace, tiles: list[str]) -> list[TileJob]:
    slug = datetime_slug(args.datetime)
    data_dir = args.data_dir.expanduser()
    tif_dir = data_dir / slug
    log_dir = data_dir / "logs" / slug
    metrics_dir = data_dir / "metrics" / slug
    for d in (tif_dir, log_dir, metrics_dir):
        d.mkdir(parents=True, exist_ok=True)

    jobs: list[TileJob] = []
    for tile in tiles:
        jobs.append(
            TileJob(
                tile=tile,
                datetime_range=args.datetime,
                max_cloud=args.max_cloud,
                platform=args.platform,
                max_scenes=args.max_scenes,
                diverse_paths=not args.no_diverse_paths,
                composite=args.composite,
                resolution=args.resolution,
                epsg=args.epsg,
                mgrs_size_km=args.mgrs_size_km,
                out_tif=tif_dir / f"mgrs_{tile}_landsat_sr.tif",
                log_file=log_dir / f"{tile}.log",
                metrics_csv=metrics_dir / f"metrics_{tile}.csv",
                skip_existing=args.skip_existing,
                verbose=args.verbose,
            )
        )
    return jobs


def process_tile(job: TileJob) -> dict:
    """
    Worker entry point: STAC + serial COG reads + composite+write for ONE tile.

    Logs go to the per-tile log file AND to the inherited stdout, with each
    line prefixed by [TILE] so the parent process sees live progress from many
    workers interleaved.
    """
    setup_logging(
        level=resolve_log_level(verbose=job.verbose, quiet=False),
        log_file=job.log_file,
        tile=job.tile,
        console=True,
    )
    log = get_logger()
    t_worker = time.perf_counter()

    try:
        if job.skip_existing and job.out_tif.is_file():
            log.info("Skip — output already exists: %s", job.out_tif)
            return {
                "tile": job.tile,
                "status": "skipped",
                "out_tif": str(job.out_tif),
                "log_file": str(job.log_file),
                "elapsed_s": round(time.perf_counter() - t_worker, 2),
            }

        log.info("=" * 60)
        log.info("Landsat C2 L2 SR mosaic — tile %s", job.tile)
        log.info(
            "datetime=%s  max_scenes=%d  composite=%s  resolution=%.0fm",
            job.datetime_range,
            job.max_scenes,
            job.composite,
            job.resolution,
        )
        log.info("Output:      %s", job.out_tif)
        log.info("Log file:    %s", job.log_file)
        log.info("Metrics CSV: %s", job.metrics_csv)

        log.info("─" * 56)
        log.info("Phase 1/3: STAC search")
        bbox = mgrs_tile_bbox_wgs84(job.tile, size_km=job.mgrs_size_km)
        epsg = job.epsg if job.epsg is not None else epsg_from_mgrs_tile(job.tile)
        log.info("BBox WGS84: %s", bbox)
        log.info("UTM EPSG:%d", epsg)

        catalog = open_catalog()
        query: dict = {"eo:cloud_cover": {"lt": job.max_cloud}}
        if job.platform != "any":
            query["platform"] = {"eq": job.platform}

        t0 = time.perf_counter()
        items_all = list(
            catalog.search(
                collections=[COLLECTION],
                bbox=list(bbox),
                datetime=job.datetime_range,
                query=query,
                max_items=max(100, job.max_scenes * 15),
            ).items()
        )
        stac_s = time.perf_counter() - t0
        log.info("STAC: %d candidate(s) in %.2fs", len(items_all), stac_s)
        if not items_all:
            log.error("No scenes found.")
            return {
                "tile": job.tile,
                "status": "error",
                "error": "no scenes found in STAC search",
                "out_tif": str(job.out_tif),
                "log_file": str(job.log_file),
                "elapsed_s": round(time.perf_counter() - t_worker, 2),
            }

        items = select_scenes(items_all, job.max_scenes, diverse_paths=job.diverse_paths)
        paths = {wrs_path_row(it) for it in items}
        log.info("Selected %d scene(s) across %d WRS path/row:", len(items), len(paths))
        for i, it in enumerate(items, 1):
            cc = it.properties.get("eo:cloud_cover", "?")
            dt = it.properties.get("datetime", "?")
            path, row = wrs_path_row(it)
            log.info(
                "  [%d/%d] %s  path/row=%s/%s  cloud=%s%%  %s",
                i, len(items), it.id, path, row, cc, dt,
            )

        log.info("─" * 56)
        log.info("Phase 2/3: Serial COG reads (one HTTPS request at a time)")
        stack, timings, target_meta, cog_s, bytes_total = fetch_assets_serial(
            items, bbox, epsg, job.resolution,
        )

        log.info("─" * 56)
        log.info("Phase 3/3: Composite + write GeoTIFF")
        comp_write_s, output_bytes = composite_and_write(
            stack, target_meta, job.out_tif, composite=job.composite,
        )

        save_metrics(job.metrics_csv, timings)

        total_s = stac_s + cog_s + comp_write_s
        total_mb = bytes_total / (1024 * 1024)
        log.info("=" * 60)
        log.info("Summary — tile %s", job.tile)
        log.info("  STAC search:        %7.2fs", stac_s)
        log.info(
            "  COG reads (serial): %7.2fs   %.1f MiB    %.1f MiB/s avg",
            cog_s, total_mb, total_mb / cog_s if cog_s > 0 else 0,
        )
        log.info(
            "  composite + write:  %7.2fs   out=%.1f MiB",
            comp_write_s, output_bytes / (1024 * 1024),
        )
        log.info("  total:              %7.2fs", total_s)
        if timings:
            secs = sorted(t.seconds for t in timings)
            rates = sorted(t.mb_per_s for t in timings if t.bytes_read > 0)
            log.info(
                "  per-asset seconds:  min=%.2f  median=%.2f  max=%.2f",
                secs[0], secs[len(secs) // 2], secs[-1],
            )
            if rates:
                log.info(
                    "  per-asset MiB/s:    min=%.2f  median=%.2f  max=%.2f",
                    rates[0], rates[len(rates) // 2], rates[-1],
                )
            errs = [t for t in timings if t.http_status != "ok"]
            if errs:
                log.warning("  %d asset(s) failed — see CSV", len(errs))

        return {
            "tile": job.tile,
            "status": "ok",
            "out_tif": str(job.out_tif),
            "log_file": str(job.log_file),
            "metrics_csv": str(job.metrics_csv),
            "n_scenes": len(items),
            "n_assets": len(timings),
            "epsg": epsg,
            "stac_search_s": round(stac_s, 2),
            "cog_read_s": round(cog_s, 2),
            "composite_write_s": round(comp_write_s, 2),
            "total_s": round(total_s, 2),
            "bytes_read": bytes_total,
            "output_bytes": output_bytes,
            "elapsed_s": round(time.perf_counter() - t_worker, 2),
        }

    except Exception as exc:
        log.exception("Tile %s failed: %s", job.tile, exc)
        return {
            "tile": job.tile,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "out_tif": str(job.out_tif),
            "log_file": str(job.log_file),
            "elapsed_s": round(time.perf_counter() - t_worker, 2),
        }


def append_manifest(manifest_path: Path, record: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    try:
        tiles = parse_tile_ids(args.tiles)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.limit > 0:
        tiles = tiles[: args.limit]

    slug = datetime_slug(args.datetime)
    data_dir = args.data_dir.expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.manifest or (data_dir / f"manifest_{slug}.jsonl")
    batch_log = data_dir / f"batch_{slug}.log"

    setup_logging(
        level=resolve_log_level(verbose=args.verbose, quiet=args.quiet),
        log_file=None if args.dry_run else batch_log,
    )
    log = get_logger()

    log.info("=" * 60)
    log.info("Batch Landsat mosaic run (one tile per worker, serial band-by-band)")
    log.info("Tiles (%d): %s", len(tiles), ", ".join(tiles))
    log.info(
        "Workers: %d  datetime: %s  max_scenes: %d  composite: %s",
        args.workers, args.datetime, args.max_scenes, args.composite,
    )
    log.info("Data dir: %s", data_dir)
    log.info("Batch log: %s", batch_log)
    log.info("Manifest: %s", manifest)
    log.info("Per-tile logs:    %s", data_dir / "logs" / slug)
    log.info("Per-tile metrics: %s", data_dir / "metrics" / slug)

    jobs = build_jobs(args, tiles)

    if args.dry_run:
        log.info("Dry-run — planned outputs:")
        for j in jobs:
            log.info(
                "  %s → %s  (log: %s, metrics: %s)",
                j.tile, j.out_tif, j.log_file, j.metrics_csv,
            )
        return 0

    if manifest.exists():
        manifest.unlink()

    ok = err = skipped = 0
    t0 = time.perf_counter()
    log.info("Submitting %d job(s) to %d worker(s) [spawn, fresh interpreter per worker] …",
             len(jobs), args.workers)
    log.info(
        "(Worker logs stream to stdout below, prefixed by [TILE]. "
        "Full detail per tile in its log file.)"
    )

    # mp_context="spawn" → each worker is a fresh Python interpreter (no fork
    # copy-on-write of parent state). This guarantees heavy, isolated processes
    # so per-process counters (psutil read_chars) and GDAL state stay clean.
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=max(1, args.workers), mp_context=ctx) as pool:
        futures = {pool.submit(process_tile, job): job for job in jobs}
        done = 0
        for fut in as_completed(futures):
            job = futures[fut]
            done += 1
            try:
                result = fut.result()
            except Exception as exc:
                result = {
                    "tile": job.tile,
                    "status": "error",
                    "error": f"worker crashed: {exc}",
                    "out_tif": str(job.out_tif),
                    "log_file": str(job.log_file),
                }
            append_manifest(manifest, result)

            status = result.get("status")
            if status == "ok":
                ok += 1
                mib = (result.get("bytes_read") or 0) / (1024 * 1024)
                log.info(
                    "[%d/%d] OK   %-6s  stac=%ss  cog=%ss  write=%ss  "
                    "total=%ss  read=%.0fMiB",
                    done, len(jobs), job.tile,
                    result.get("stac_search_s"),
                    result.get("cog_read_s"),
                    result.get("composite_write_s"),
                    result.get("total_s"),
                    mib,
                )
            elif status == "skipped":
                skipped += 1
                log.info(
                    "[%d/%d] SKIP %-6s  (output exists)",
                    done, len(jobs), job.tile,
                )
            else:
                err += 1
                log.error(
                    "[%d/%d] ERR  %-6s  %s  log=%s",
                    done, len(jobs), job.tile,
                    result.get("error", result),
                    job.log_file,
                )

    elapsed = round(time.perf_counter() - t0, 1)
    log.info("=" * 60)
    log.info(
        "Done — ok=%d skipped=%d errors=%d total=%d wall=%ss",
        ok, skipped, err, len(jobs), elapsed,
    )
    log.info("Manifest: %s", manifest)
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
