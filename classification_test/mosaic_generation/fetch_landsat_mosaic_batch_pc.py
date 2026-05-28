#!/usr/bin/env python3
"""
Batch Landsat C2 L2 SR mosaics for MGRS 100 km tiles (parallel workers).

Tile bounds and UTM EPSG are derived from MGRS codes via the mgrs library
(same grid as fetch_landsat_mosaic_pc.py — no GeoJSON catalog required).

Usage:
    # Dry-run: validate tiles and list planned outputs
    python fetch_landsat_mosaic_batch_pc.py \\
        --tiles 19HCD,18GXR --dry-run

    # Test 2 tiles, 2 workers (verbose per-tile logs under data/landsat_mosaic/logs/)
    python fetch_landsat_mosaic_batch_pc.py --tiles 19HCD,18GXR --workers 2

    # Q1 2024, 5 scenes, median (recommended)
    python fetch_landsat_mosaic_batch_pc.py \\
        --tiles 18FXH,18GXP,18HYD,19HCD,19JCJ,19KDU \\
        --datetime 2024-01-01/2024-03-31 \\
        --max-scenes 5 \\
        --workers 6 \\
        --data-dir ~/data/mosaic_parallel_test

Composite note:
    **median** (default) — standard for seasonal Landsat mosaics; robust to clouds
    and outliers (MapBiomas / USGS CDR style).
    **mean** — smoother but clouds/outliers pull values; use only if you pre-filter
    heavily or mask clouds per scene.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from fetch_landsat_mosaic_pc import (
    DEFAULT_DATETIME,
    epsg_from_mgrs_tile,
    mgrs_tile_bbox_wgs84,
    normalize_mgrs_tile,
    process_mgrs_tile,
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
    out_path: Path
    skip_existing: bool
    log_file: Path
    verbose: bool
    quiet: bool


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Parallel Landsat SR mosaics for Chile MGRS tiles via Planetary Computer",
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
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Output directory (default: {DEFAULT_DATA_DIR})",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Parallel worker processes (one tile per worker at a time)",
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
        help="JSONL manifest path (default: <data-dir>/manifest_<datetime>.jsonl)",
    )
    p.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Per-tile verbose logs (default: <data-dir>/logs/<period>/)",
    )
    p.add_argument(
        "--batch-log",
        type=Path,
        default=None,
        help="Main batch run log file (default: <data-dir>/batch_<period>.log)",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="DEBUG in worker tile logs",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Minimal console output; detail goes to --log-dir files",
    )
    p.add_argument(
        "--progress-interval",
        type=float,
        default=15.0,
        help="Seconds between progress-table prints (0 disables; default 15)",
    )
    p.add_argument(
        "--stream-worker-logs",
        action="store_true",
        help=(
            "Stream each worker's logs to console (interleaved, prefixed by [TILE]). "
            "Off by default to keep the progress table readable; per-tile logs always "
            "go to --log-dir."
        ),
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


def datetime_slug(datetime_range: str) -> str:
    return datetime_range.replace("/", "_").replace(":", "")


def output_path(data_dir: Path, tile: str, datetime_range: str) -> Path:
    slug = datetime_slug(datetime_range)
    return data_dir / slug / f"mgrs_{tile}_landsat_sr.tif"


def tile_log_path(log_dir: Path, tile: str) -> Path:
    return log_dir / f"{tile}.log"


def build_jobs(args: argparse.Namespace, tile_ids: list[str]) -> list[TileJob]:
    args.data_dir.mkdir(parents=True, exist_ok=True)
    slug = datetime_slug(args.datetime)
    log_dir = args.log_dir or (args.data_dir / "logs" / slug)
    log_dir.mkdir(parents=True, exist_ok=True)
    worker_quiet = not args.stream_worker_logs
    jobs: list[TileJob] = []
    for tile in tile_ids:
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
                out_path=output_path(args.data_dir, tile, args.datetime),
                skip_existing=args.skip_existing,
                log_file=tile_log_path(log_dir, tile),
                verbose=args.verbose,
                quiet=worker_quiet,
            )
        )
    return jobs


def run_tile_job(job: TileJob) -> dict:
    """Worker entry point (picklable)."""
    t0 = time.perf_counter()
    try:
        # When quiet=True (default), per-worker logs go only to job.log_file so the
        # parent's progress table stays readable. With --stream-worker-logs they
        # also stream to the inherited stdout, prefixed by [TILE].
        result = process_mgrs_tile(
            job.tile,
            datetime_range=job.datetime_range,
            max_cloud=job.max_cloud,
            platform=job.platform,
            max_scenes=job.max_scenes,
            diverse_paths=job.diverse_paths,
            resolution=job.resolution,
            composite=job.composite,
            out_path=job.out_path,
            skip_existing=job.skip_existing,
            log_file=job.log_file,
            verbose=job.verbose,
            quiet=job.quiet,
        )
    except Exception as exc:
        result = {
            "tile": job.tile,
            "status": "error",
            "out_path": str(job.out_path),
            "log_file": str(job.log_file),
            "error": str(exc),
        }
    result["elapsed_s"] = round(time.perf_counter() - t0, 1)
    return result


def append_manifest(manifest_path: Path, record: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _tail_log_line(log_file: Path, *, max_bytes: int = 8192) -> str:
    """Return the last non-empty line of a log file (best-effort, never raises)."""
    try:
        with log_file.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            chunk = fh.read().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return "(no log yet)"
    except OSError:
        return "(log unreadable)"
    lines = [ln.rstrip() for ln in chunk.splitlines() if ln.strip()]
    return lines[-1] if lines else "(empty log)"


def _file_size_mib(path: Path) -> float | None:
    try:
        return path.stat().st_size / (1024 * 1024)
    except FileNotFoundError:
        return None


def _log_age_s(log_file: Path, fallback: float) -> float:
    try:
        return max(0.0, time.time() - log_file.stat().st_mtime)
    except FileNotFoundError:
        return fallback


class BatchProgress:
    """
    Background heartbeat that prints a compact status table for in-flight tiles.

    Detects "running" by the presence of the worker's per-tile log file. Tails
    each running tile's log to show the latest phase / heartbeat line and the
    growing GeoTIFF size when the write phase starts.
    """

    def __init__(self, jobs: list[TileJob], *, interval_s: float):
        self.interval_s = interval_s
        self.total = len(jobs)
        self.tiles: dict[str, dict] = {
            job.tile: {
                "log_file": job.log_file,
                "out_path": job.out_path,
                "finished": False,
            }
            for job in jobs
        }
        self.done_count = 0
        self.batch_start = time.time()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.interval_s <= 0 or self.total == 0:
            return
        self._thread = threading.Thread(
            target=self._loop, name="batch-progress", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def mark_done(self, tile: str) -> None:
        with self._lock:
            info = self.tiles.get(tile)
            if info is not None and not info["finished"]:
                info["finished"] = True
                self.done_count += 1

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            try:
                self._print_status()
            except Exception:
                # Never let the progress thread kill the batch
                pass

    def _print_status(self) -> None:
        log = get_logger()
        with self._lock:
            running = []
            pending: list[str] = []
            for tile, info in self.tiles.items():
                if info["finished"]:
                    continue
                if info["log_file"].exists():
                    running.append((tile, info))
                else:
                    pending.append(tile)
            done = self.done_count
            total = self.total

        if not running and not pending:
            return

        wall = time.time() - self.batch_start
        log.info("─" * 72)
        log.info(
            "Progress @ %5.0fs wall:  %d/%d done  |  %d running  |  %d pending",
            wall,
            done,
            total,
            len(running),
            len(pending),
        )
        for tile, info in sorted(running, key=lambda kv: kv[0]):
            elapsed = _log_age_s(info["log_file"], fallback=wall)
            tail = _tail_log_line(info["log_file"])
            size = _file_size_mib(info["out_path"])
            size_str = f"  tif={size:5.0f}MiB" if size is not None else ""
            # Trim very long lines so the table stays scannable
            if len(tail) > 110:
                tail = tail[:107] + "…"
            log.info("  %-6s  %5.0fs%s  | %s", tile, elapsed, size_str, tail)
        if pending:
            log.info("  pending: %s", ", ".join(sorted(pending)))


def main() -> int:
    args = parse_args()
    try:
        tile_ids = parse_tile_ids(args.tiles)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.limit > 0:
        tile_ids = tile_ids[: args.limit]

    slug = datetime_slug(args.datetime)
    manifest = args.manifest or (args.data_dir / f"manifest_{slug}.jsonl")
    log_dir = args.log_dir or (args.data_dir / "logs" / slug)
    batch_log = args.batch_log or (args.data_dir / f"batch_{slug}.log")

    setup_logging(
        level=resolve_log_level(verbose=args.verbose, quiet=args.quiet),
        log_file=None if args.dry_run else batch_log,
    )
    log = get_logger()

    log.info("=" * 56)
    log.info("Batch Landsat mosaic run")
    log.info("Tiles: %s (%d)", ", ".join(tile_ids), len(tile_ids))
    log.info(
        "Workers: %d  datetime: %s  max_scenes: %d  composite: %s",
        args.workers, args.datetime, args.max_scenes, args.composite,
    )
    log.info("Data dir: %s", args.data_dir)
    log.info("Per-tile logs: %s", log_dir)
    log.info("Batch log: %s", batch_log)
    log.info("Manifest: %s", manifest)
    if args.progress_interval > 0 and not args.dry_run:
        log.info(
            "Progress table every %.0fs (use `tail -f %s/<TILE>.log` for live per-tile detail)",
            args.progress_interval,
            log_dir,
        )
    if args.stream_worker_logs:
        log.info("Streaming worker logs to console (interleaved, prefixed by [TILE])")

    if args.dry_run:
        log.info("Dry-run — planned outputs:")
        for t in tile_ids:
            bbox = mgrs_tile_bbox_wgs84(t)
            epsg = epsg_from_mgrs_tile(t)
            out = output_path(args.data_dir, t, args.datetime)
            tlog = tile_log_path(log_dir, t)
            log.info(
                "  %s  EPSG:%d  bbox=%.4f,%.4f,%.4f,%.4f → %s  (log: %s)",
                t,
                epsg,
                *bbox,
                out,
                tlog,
            )
        return 0

    if manifest.exists():
        manifest.unlink()

    jobs = build_jobs(args, tile_ids)
    ok = skipped = err = 0
    t0 = time.perf_counter()
    log.info("Submitting %d job(s) to process pool …", len(jobs))

    progress = BatchProgress(jobs, interval_s=args.progress_interval)
    progress.start()

    try:
        with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {pool.submit(run_tile_job, job): job for job in jobs}
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
                        "out_path": str(job.out_path),
                        "log_file": str(job.log_file),
                    }
                progress.mark_done(job.tile)
                append_manifest(manifest, result)

                status = result.get("status")
                if status == "ok":
                    ok += 1
                    cov = result.get("coverage_pct", "?")
                    stac = result.get("timing_stac_search_s", "?")
                    cog = result.get("timing_cog_read_composite_s", "?")
                    write = result.get("timing_write_geotiff_s", "?")
                    io_mb = result.get("io_read_bytes")
                    io_s = f" read={io_mb / (1024 * 1024):.0f}MiB" if io_mb else ""
                    out_size = _file_size_mib(job.out_path)
                    out_s = f" tif={out_size:.0f}MiB" if out_size is not None else ""
                    log.info(
                        "[%d/%d] OK   %-6s  cov=%s%%  stac=%ss  cog=%ss  write=%ss%s%s  total=%ss",
                        done,
                        len(jobs),
                        job.tile,
                        cov,
                        stac,
                        cog,
                        write,
                        io_s,
                        out_s,
                        result.get("elapsed_s"),
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
                        done,
                        len(jobs),
                        job.tile,
                        result.get("error", result),
                        job.log_file,
                    )
    finally:
        progress.stop()

    elapsed = round(time.perf_counter() - t0, 1)
    log.info(
        "Done — ok=%d skipped=%d errors=%d total=%d wall=%ss manifest=%s",
        ok,
        skipped,
        err,
        len(jobs),
        elapsed,
        manifest,
    )
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
