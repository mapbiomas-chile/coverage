#!/usr/bin/env python3
"""
Fetch / composite Landsat Collection 2 Level-2 SR from Microsoft Planetary Computer.

Designed for Chile AOIs via WGS84 bbox or MGRS 100 km tile (HLS / Prithvi grid),
output GeoTIFF with 7 OLI SR bands in SSL4EO order, reflectance ~0-1 float32.

Usage:
    # 1) Test network from NLHPC login or compute node
    python fetch_landsat_mosaic_pc.py --test-connection

    # 2) Full MGRS 100 km tile (UTM zone + EPSG inferred from tile id)
    python fetch_landsat_mosaic_pc.py \\
        --mgrs 19HCD \\
        --datetime 2024-01-01/2024-03-31 \\
        --max-scenes 10 \\
        # writes /mnt/e/mapbiomas/coverage/data/mgrs_19HCD_landsat_sr.tif by default

    # 3) Small custom bbox (legacy / sub-window inside a tile)
    python fetch_landsat_mosaic_pc.py \\
        --bbox -71.35 -33.55 -71.05 -33.35 \\
        --datetime 2024-01-01/2024-03-31

    # 4) Single best scene (lowest cloud)
    python fetch_landsat_mosaic_pc.py --mgrs 19HCD --max-scenes 1 --out ...

NLHPC notes:
    - Compute nodes must reach https://planetarycomputer.microsoft.com (HTTPS).
    - Run --test-connection on the same node type you use for jobs.
    - If your site uses a proxy: export https_proxy / http_proxy before running.
    - Optional API key: export PLANETARY_COMPUTER_API_KEY=... (see PC docs).
    - Heavy downloads: request enough --time in Slurm; start with small bbox.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from mosaic_logging import get_logger, heartbeat, log_phase, resolve_log_level, setup_logging

# USGS Landsat Collection 2 Level-2 surface reflectance scaling (DN -> reflectance)
LANDSAT_SR_SCALE = 2.75e-05
LANDSAT_SR_OFFSET = -0.2

# Planetary Computer asset names (OLI) in SSL4EO SR_B1..SR_B7 order
OLI_SR_ASSETS = ["coastal", "blue", "green", "red", "nir08", "swir16", "swir22"]
SSL4EO_BAND_NAMES = [
    "SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7",
]

PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"

# Example: Santiago outskirts ~12 km x 12 km
DEFAULT_BBOX = (-71.35, -33.55, -71.05, -33.35)
DEFAULT_DATETIME = "2024-01-01/2024-03-31"
MGRS_TILE_SIZE_KM = 100.0
# Persistent data root (WSL: Windows drive E:)
DEFAULT_DATA_DIR = Path("/mnt/e/mapbiomas/coverage/data")


@dataclass
class PhaseTiming:
    """Per-phase timings (seconds) and optional I/O byte counters."""

    stac_search_s: float = 0.0
    stack_setup_s: float = 0.0
    cog_read_composite_s: float = 0.0
    write_geotiff_s: float = 0.0
    total_s: float = 0.0
    io_read_bytes: int | None = None
    output_bytes: int | None = None
    scene_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "timing_stac_search_s": round(self.stac_search_s, 3),
            "timing_stack_setup_s": round(self.stack_setup_s, 3),
            "timing_cog_read_composite_s": round(self.cog_read_composite_s, 3),
            "timing_write_geotiff_s": round(self.write_geotiff_s, 3),
            "timing_total_s": round(self.total_s, 3),
            "io_read_bytes": self.io_read_bytes,
            "output_bytes": self.output_bytes,
            "scene_ids": self.scene_ids,
        }

    def log_lines(self) -> list[str]:
        lines = [
            f"  STAC search:        {self.stac_search_s:7.2f} s",
            f"  stackstac setup:    {self.stack_setup_s:7.2f} s  (plan Dask graph, no pixel I/O yet)",
            f"  COG read+composite: {self.cog_read_composite_s:7.2f} s  (HTTPS byte ranges from Azure)",
            f"  write GeoTIFF:      {self.write_geotiff_s:7.2f} s",
            f"  total:              {self.total_s:7.2f} s",
        ]
        if self.io_read_bytes is not None:
            mb = self.io_read_bytes / (1024 * 1024)
            lines.append(f"  process read I/O:   {mb:,.1f} MiB  (approx. COG bytes pulled; see note below)")
        if self.output_bytes is not None:
            mb = self.output_bytes / (1024 * 1024)
            lines.append(f"  output file:        {mb:,.1f} MiB")
        return lines


@contextmanager
def measure_process_read_bytes():
    """
    Best-effort byte counter for the COG read phase (Linux psutil).

    Counts process read I/O, dominated by network COG range requests here.
    """
    box: dict[str, int | None] = {"delta": None}
    try:
        import psutil

        proc = psutil.Process()
        before = proc.io_counters().read_bytes
        yield box
        after = proc.io_counters().read_bytes
        box["delta"] = after - before
    except ImportError:
        yield box


def normalize_mgrs_tile(tile: str) -> str:
    """MGRS id without spaces, e.g. '19HCD'."""
    t = tile.strip().upper().replace(" ", "")
    if len(t) < 5 or not t[:2].isdigit():
        raise ValueError(f"Invalid MGRS tile id: {tile!r} (expected e.g. 19HCD)")
    return t


def mgrs_tile_bbox_wgs84(tile: str, size_km: float = MGRS_TILE_SIZE_KM) -> tuple[float, float, float, float]:
    """
  WGS84 bounds (min_lon, min_lat, max_lon, max_lat) for an MGRS 100 km cell.

  Uses the SW corner from the mgrs package, then extends size_km east/north in UTM.
  """
    import mgrs
    from pyproj import Transformer

    tile = normalize_mgrs_tile(tile)
    zone = int(tile[:2])
    m = mgrs.MGRS()
    lat_sw, lon_sw = m.toLatLon(tile)

    epsg = epsg_from_mgrs_corner(zone, lat_sw)
    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    to_wgs = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)

    x_sw, y_sw = to_utm.transform(lon_sw, lat_sw)
    size_m = size_km * 1000.0
    x_ne = x_sw + size_m
    y_ne = y_sw + size_m

    min_lon, min_lat = to_wgs.transform(x_sw, y_sw)
    max_lon, max_lat = to_wgs.transform(x_ne, y_ne)
    return (
        min(min_lon, max_lon),
        min(min_lat, max_lat),
        max(min_lon, max_lon),
        max(min_lat, max_lat),
    )


def epsg_from_mgrs_corner(zone: int, lat: float) -> int:
    """WGS84 UTM EPSG from MGRS zone number and latitude (326xx N / 327xx S)."""
    if not 1 <= zone <= 60:
        raise ValueError(f"UTM zone out of range: {zone}")
    return (32600 if lat >= 0 else 32700) + zone


def epsg_from_mgrs_tile(tile: str) -> int:
    import mgrs

    tile = normalize_mgrs_tile(tile)
    lat, _lon = mgrs.MGRS().toLatLon(tile)
    return epsg_from_mgrs_corner(int(tile[:2]), lat)


def resolve_aoi(args: argparse.Namespace) -> tuple[tuple[float, float, float, float], int, str]:
    """Return (bbox_wgs84, epsg, label for logs)."""
    if args.mgrs:
        tile = normalize_mgrs_tile(args.mgrs)
        bbox = mgrs_tile_bbox_wgs84(tile, size_km=args.mgrs_size_km)
        epsg = args.epsg if args.epsg is not None else epsg_from_mgrs_tile(tile)
        label = f"MGRS {tile} ({args.mgrs_size_km:g} km)"
    else:
        bbox = tuple(args.bbox)
        epsg = args.epsg if args.epsg is not None else 32719
        label = "bbox"
    return bbox, epsg, label


def resolve_output_path(args: argparse.Namespace) -> Path:
    """Default GeoTIFF under --data-dir (mgrs_<tile>_... or chile_pc_landsat_sr.tif)."""
    if args.out is not None:
        return args.out
    data_dir = args.data_dir
    if args.mgrs:
        tile = normalize_mgrs_tile(args.mgrs)
        return data_dir / f"mgrs_{tile}_landsat_sr.tif"
    return data_dir / "chile_pc_landsat_sr.tif"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Landsat C2 L2 SR mosaic via Planetary Computer")
    p.add_argument(
        "--test-connection",
        action="store_true",
        help="Only check HTTPS reachability to Planetary Computer STAC API",
    )
    loc = p.add_mutually_exclusive_group()
    loc.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help=f"WGS84 bounds (default if no --mgrs: {DEFAULT_BBOX})",
    )
    loc.add_argument(
        "--mgrs",
        metavar="TILE",
        help="MGRS 100 km tile id (e.g. 19HCD). Sets WGS84 bounds and default UTM EPSG.",
    )
    p.add_argument(
        "--mgrs-size-km",
        type=float,
        default=MGRS_TILE_SIZE_KM,
        help="Extent in km when using --mgrs (default 100, standard MGRS cell)",
    )
    p.add_argument(
        "--datetime",
        default=DEFAULT_DATETIME,
        help="ISO interval for STAC search, e.g. 2024-01-01/2024-03-31",
    )
    p.add_argument("--max-cloud", type=float, default=25.0, help="eo:cloud_cover < this")
    p.add_argument(
        "--max-scenes",
        type=int,
        default=None,
        help="Scenes in median composite (default: 10 with --mgrs, else 3). "
        "MGRS 100 km needs several WRS paths; --max-scenes 1 covers ~2%% of tile.",
    )
    p.add_argument(
        "--no-diverse-paths",
        action="store_true",
        help="Pick N lowest-cloud scenes only (may share one WRS path; bad for --mgrs)",
    )
    p.add_argument(
        "--platform",
        choices=("any", "landsat-8", "landsat-9"),
        default="any",
        help="Filter platform (OLI sensors)",
    )
    p.add_argument(
        "--epsg",
        type=int,
        default=None,
        help="Output CRS (default: UTM zone from --mgrs, else 32719 for --bbox)",
    )
    p.add_argument("--resolution", type=float, default=30.0, help="Pixel size in meters")
    p.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Output directory when --out is omitted (default: {DEFAULT_DATA_DIR})",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output GeoTIFF path (overrides --data-dir naming)",
    )
    p.add_argument(
        "--composite",
        choices=("median", "mean"),
        default="median",
        help="Multi-scene compositing (median recommended: robust to clouds/outliers)",
    )
    p.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Write verbose log to this file (in addition to stdout)",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="DEBUG logging (STAC query details, array shapes, etc.)",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="WARNING only on console (use with --log-file to capture detail to disk)",
    )
    return p.parse_args()


def test_connection() -> None:
    log = get_logger()
    log.info("Testing HTTPS reachability to Planetary Computer STAC API")
    log.info("GET %s", PC_STAC_URL)
    try:
        with urllib.request.urlopen(PC_STAC_URL, timeout=60) as resp:
            code = resp.getcode()
            body = resp.read(200)
    except urllib.error.URLError as e:
        log.error("Cannot reach Planetary Computer: %s", e)
        log.error("On NLHPC: try from login node; check firewall/proxy with sysadmin.")
        sys.exit(1)
    log.info("Connection OK — HTTP %s, body preview: %r", code, body[:80])


def open_catalog():
    import planetary_computer as pc
    import pystac_client

    get_logger().debug("Opening STAC catalog %s (signing URLs with planetary_computer)", PC_STAC_URL)
    return pystac_client.Client.open(
        PC_STAC_URL,
        modifier=pc.sign_inplace,
    )


def wrs_path_row(item) -> tuple[str, str]:
    return (
        str(item.properties.get("landsat:wrs_path", "")),
        str(item.properties.get("landsat:wrs_row", "")),
    )


def select_scenes(
    items: list,
    max_scenes: int,
    *,
    diverse_paths: bool,
) -> list:
    """
    Choose scenes for compositing.

    For MGRS-sized AOIs, one Landsat swath covers only a fraction of the tile.
    Prefer the clearest scene per WRS path/row, then take up to max_scenes.
    """
    if max_scenes <= 1 or not diverse_paths:
        ranked = sorted(items, key=lambda it: it.properties.get("eo:cloud_cover", 999))
        return ranked[:max_scenes]

    best_per_path: dict[tuple[str, str], object] = {}
    for it in items:
        key = wrs_path_row(it)
        if key == ("", ""):
            key = (it.id, "")
        cc = it.properties.get("eo:cloud_cover", 999)
        prev = best_per_path.get(key)
        if prev is None or cc < prev.properties.get("eo:cloud_cover", 999):
            best_per_path[key] = it

    ranked = sorted(
        best_per_path.values(),
        key=lambda it: it.properties.get("eo:cloud_cover", 999),
    )
    return ranked[:max_scenes]


def search_items(
    bbox: tuple[float, float, float, float],
    datetime_range: str,
    max_cloud: float,
    platform: str,
    max_scenes: int,
    diverse_paths: bool = True,
):
    log = get_logger()
    catalog = open_catalog()
    query: dict = {"eo:cloud_cover": {"lt": max_cloud}}
    if platform != "any":
        query["platform"] = {"eq": platform}

    max_items = max(100, max_scenes * 15)
    log.info(
        "STAC search: collection=%s datetime=%s max_cloud<%.1f platform=%s max_items=%d",
        COLLECTION,
        datetime_range,
        max_cloud,
        platform,
        max_items,
    )
    log.info(
        "STAC bbox WGS84: min_lon=%.5f min_lat=%.5f max_lon=%.5f max_lat=%.5f",
        bbox[0],
        bbox[1],
        bbox[2],
        bbox[3],
    )
    log.debug("STAC query filter: %s", query)

    search = catalog.search(
        collections=[COLLECTION],
        bbox=list(bbox),
        datetime=datetime_range,
        query=query,
        max_items=max_items,
    )
    log.info("Fetching STAC item metadata from Planetary Computer API …")
    t0 = time.perf_counter()
    with heartbeat("STAC item fetch", interval_s=10):
        items = list(search.items())
    log.info("STAC metadata received in %.2f s — %d candidate scene(s)", time.perf_counter() - t0, len(items))

    if not items:
        raise RuntimeError(
            "No scenes found. Try wider --datetime, higher --max-cloud, or larger --bbox."
        )

    selected = select_scenes(items, max_scenes, diverse_paths=diverse_paths)
    paths_used = {wrs_path_row(it) for it in selected}
    log.info(
        "Scene selection: %d candidate(s) → using %d scene(s) across %d WRS path/row "
        "(diverse_paths=%s, max_scenes=%d)",
        len(items),
        len(selected),
        len(paths_used),
        diverse_paths,
        max_scenes,
    )
    for i, it in enumerate(selected, 1):
        cc = it.properties.get("eo:cloud_cover", "?")
        dt = it.properties.get("datetime", "?")
        path, row = wrs_path_row(it)
        log.info(
            "  [%d/%d] %s  path/row=%s/%s  cloud=%s%%  datetime=%s",
            i,
            len(selected),
            it.id,
            path,
            row,
            cc,
            dt,
        )
    if max_scenes == 1:
        log.warning(
            "Only 1 scene selected: a single Landsat pass covers a small fraction of "
            "a 100 km MGRS tile; use >=3 scenes (5+ recommended)."
        )
    return selected


def report_valid_coverage(data) -> float:
    """Fraction of pixels with valid red-band reflectance (>0)."""
    import numpy as np

    if "band" in data.dims:
        red = data.sel(band="red").values
    else:
        red = data.values[3]
    valid = np.isfinite(red) & (red > 0)
    pct = 100.0 * valid.mean()
    log = get_logger()
    log.info("Coverage QA: %.1f%% valid red-band pixels (%s / %s)", pct, f"{valid.sum():,}", f"{valid.size:,}")
    if pct < 50:
        log.warning("Low tile coverage (%.1f%%) — try more scenes or wider datetime window", pct)
    return pct


def dn_to_reflectance(da):
    """Apply USGS L2 SR scaling and clip to [0, 1]."""
    import xarray as xr

    out = da.astype("float32") * LANDSAT_SR_SCALE + LANDSAT_SR_OFFSET
    return out.clip(0.0, 1.0)


def _log_cog_asset_list(items, assets: list[str]) -> None:
    """Log which COG URLs will be fetched (INFO summary, DEBUG full list)."""
    from urllib.parse import urlsplit

    log = get_logger()
    entries: list[tuple[str, str, str]] = []
    for it in items:
        for a in assets:
            href = it.assets[a].href if a in it.assets else None
            if href:
                entries.append((it.id, a, href))

    log.info(
        "COG plan: %d scene(s) × %d band(s) = %d COG asset(s) to read from Azure",
        len(items),
        len(assets),
        len(entries),
    )
    for scene_id, asset_name, url in entries:
        parts = urlsplit(url)
        path = parts.path.split("/")[-1] or parts.path
        log.info("    %s · %-8s · %s%s", scene_id, asset_name, parts.netloc, "/" + path)
        log.debug("        full URL: %s", url)


class _DaskTaskCounter:
    """Counts completed dask tasks for live progress reporting."""

    def __init__(self) -> None:
        self.total = 0
        self.done = 0
        self._lock = __import__("threading").Lock()

    def __enter__(self):
        from dask.callbacks import Callback

        parent = self

        class _CB(Callback):
            def _start_state(self, dsk, state):
                with parent._lock:
                    parent.total = (
                        len(state.get("ready", ()))
                        + len(state.get("running", ()))
                        + len(state.get("finished", ()))
                        + len(state.get("released", ()))
                        + len(state.get("waiting", ()))
                    )
                    if parent.total == 0:
                        try:
                            parent.total = len(dsk)
                        except Exception:
                            parent.total = 0
                    parent.done = len(state.get("finished", ()))

            def _posttask(self, key, result, dsk, state, worker_id):
                with parent._lock:
                    parent.done += 1

        self._cb = _CB()
        self._cb.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._cb.__exit__(exc_type, exc, tb)

    def progress(self) -> str:
        with self._lock:
            if self.total == 0:
                return f"{self.done} chunks done"
            pct = 100.0 * self.done / self.total
            return f"{self.done}/{self.total} chunks ({pct:.0f}%)"


def stack_scenes(
    items,
    bbox,
    epsg: int,
    resolution: float,
    composite: str = "median",
    *,
    load_pixels: bool = True,
):
    import stackstac

    log = get_logger()
    log.info(
        "stackstac setup: %d scene(s), %d band(s), EPSG:%d, resolution=%.1f m",
        len(items),
        len(OLI_SR_ASSETS),
        epsg,
        resolution,
    )
    log.debug("Assets: %s", ", ".join(OLI_SR_ASSETS))
    log.info("Building lazy Dask graph (no COG byte I/O yet) …")

    t0 = time.perf_counter()
    data = stackstac.stack(
        items,
        assets=OLI_SR_ASSETS,
        bounds_latlon=bbox,
        epsg=epsg,
        resolution=resolution,
        snap_bounds=False,
        dtype="float64",
        rescale=False,
    )
    setup_s = time.perf_counter() - t0
    log.info("Dask graph ready in %.2f s — dims=%s", setup_s, dict(data.sizes))

    data = dn_to_reflectance(data)
    if "time" in data.dims and data.sizes.get("time", 1) > 1:
        log.info(
            "Composite operator: %s over %d scene(s) (applied lazily until .load())",
            composite,
            data.sizes["time"],
        )
        if composite == "mean":
            data = data.mean(dim="time", skipna=True)
        else:
            data = data.median(dim="time", skipna=True)
    elif "time" in data.dims:
        log.info("Single scene in stack — dropping time dimension")
        data = data.isel(time=0, drop=True)

    read_s = 0.0
    io_read_bytes = None
    if load_pixels:
        _log_cog_asset_list(items, OLI_SR_ASSETS)
        log.info(
            "COG read + compute: pulling HTTPS byte ranges from Azure COGs "
            "(partial reads, not full scene downloads) …"
        )
        t1 = time.perf_counter()
        counter = _DaskTaskCounter()
        with measure_process_read_bytes() as io_box, counter, heartbeat(
            "COG read + composite", interval_s=10, progress_fn=counter.progress
        ):
            data = data.load()
        read_s = time.perf_counter() - t1
        log.info("Final %s", counter.progress())
        io_read_bytes = io_box.get("delta")
        if io_read_bytes is not None:
            log.info(
                "COG read finished in %.2f s — process read I/O ≈ %.1f MiB",
                read_s,
                io_read_bytes / (1024 * 1024),
            )
        else:
            log.info("COG read finished in %.2f s", read_s)
        log.debug("Loaded array dims=%s dtype=%s", dict(data.sizes), data.dtype)

    return data, {
        "stack_setup_s": setup_s,
        "cog_read_composite_s": read_s,
        "io_read_bytes": io_read_bytes,
    }


def write_geotiff(data, out_path: Path) -> None:
    import rioxarray  # noqa: F401 — registers .rio accessor

    log = get_logger()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if "band" not in data.dims:
        data = data.assign_coords(band=SSL4EO_BAND_NAMES)
    log.info("Writing GeoTIFF → %s (compress=deflate) …", out_path)
    t0 = time.perf_counter()
    with heartbeat("GeoTIFF write", interval_s=15):
        data.rio.to_raster(out_path, compress="deflate")
    size_mb = out_path.stat().st_size / (1024 * 1024)
    log.info(
        "Write complete in %.2f s — shape=%s size=%.1f MiB bands=%s",
        time.perf_counter() - t0,
        dict(data.sizes),
        size_mb,
        list(data.coords.get("band", OLI_SR_ASSETS).values),
    )


def process_mgrs_tile(
    tile: str,
    *,
    datetime_range: str,
    max_cloud: float = 25.0,
    platform: str = "any",
    max_scenes: int = 5,
    diverse_paths: bool = True,
    epsg: int | None = None,
    resolution: float = 30.0,
    mgrs_size_km: float = MGRS_TILE_SIZE_KM,
    composite: str = "median",
    out_path: Path,
    skip_existing: bool = False,
    log_file: Path | None = None,
    verbose: bool = False,
    quiet: bool = False,
) -> dict:
    """Build one MGRS-tile Landsat SR mosaic. Returns a status dict for batch manifests."""
    tile = normalize_mgrs_tile(tile)
    out_path = out_path.resolve()

    setup_logging(
        level=resolve_log_level(verbose=verbose, quiet=quiet and log_file is None),
        log_file=log_file,
        tile=tile,
        console=not (quiet and log_file is not None),
    )
    log = get_logger()

    if skip_existing and out_path.is_file():
        log.info("Skip — output already exists: %s", out_path)
        return {
            "tile": tile,
            "status": "skipped",
            "out_path": str(out_path),
            "message": "output exists",
            "log_file": str(log_file) if log_file else None,
        }

    log.info("=" * 56)
    log.info("Landsat C2 L2 SR mosaic — tile %s", tile)
    log.info("Output: %s", out_path)
    log.info(
        "Params: datetime=%s max_scenes=%d max_cloud=%.1f composite=%s resolution=%.0fm",
        datetime_range,
        max_scenes,
        max_cloud,
        composite,
        resolution,
    )
    if log_file:
        log.info("Log file: %s", log_file)

    t_total = time.perf_counter()
    timing = PhaseTiming()
    bbox = mgrs_tile_bbox_wgs84(tile, size_km=mgrs_size_km)
    out_epsg = epsg if epsg is not None else epsg_from_mgrs_tile(tile)
    log.info("AOI: MGRS %s (%.0f km) → EPSG:%d", tile, mgrs_size_km, out_epsg)
    log.debug("BBox WGS84: %s", bbox)

    log_phase(1, 4, "STAC catalog search (metadata only, small JSON over HTTPS)")
    t0 = time.perf_counter()
    items = search_items(
        bbox=bbox,
        datetime_range=datetime_range,
        max_cloud=max_cloud,
        platform=platform,
        max_scenes=max_scenes,
        diverse_paths=diverse_paths,
    )
    timing.stac_search_s = time.perf_counter() - t0
    timing.scene_ids = [it.id for it in items]

    log_phase(2, 4, "stackstac setup + COG read + temporal composite")
    data, stack_timing = stack_scenes(
        items,
        bbox,
        out_epsg,
        resolution,
        composite=composite,
        load_pixels=True,
    )
    timing.stack_setup_s = stack_timing["stack_setup_s"]
    timing.cog_read_composite_s = stack_timing["cog_read_composite_s"]
    timing.io_read_bytes = stack_timing["io_read_bytes"]

    log_phase(3, 4, "Coverage QA")
    coverage_pct = report_valid_coverage(data)

    log_phase(4, 4, "Write GeoTIFF to disk")

    t0 = time.perf_counter()
    write_geotiff(data, out_path)
    timing.write_geotiff_s = time.perf_counter() - t0
    timing.total_s = time.perf_counter() - t_total
    timing.output_bytes = out_path.stat().st_size if out_path.is_file() else None

    log.info("Timing summary:")
    for line in timing.log_lines():
        log.info(line)
    log.info(
        "Note: io_read_bytes counts process read I/O during COG fetch "
        "(HTTP byte ranges via signed PC URLs, not full scene file sizes)."
    )
    log.info("Finished tile %s — coverage=%.1f%% total=%.1f s", tile, coverage_pct, timing.total_s)

    return {
        "tile": tile,
        "status": "ok",
        "out_path": str(out_path),
        "log_file": str(log_file) if log_file else None,
        "coverage_pct": round(coverage_pct, 2),
        "n_scenes": len(items),
        "epsg": out_epsg,
        "composite": composite,
        "datetime": datetime_range,
        **timing.as_dict(),
    }


def main() -> int:
    args = parse_args()

    setup_logging(
        level=resolve_log_level(verbose=args.verbose, quiet=args.quiet),
        log_file=args.log_file,
    )
    log = get_logger()

    if args.test_connection:
        test_connection()
        return 0

    if args.bbox is None and args.mgrs is None:
        args.bbox = list(DEFAULT_BBOX)

    bbox, epsg, aoi_label = resolve_aoi(args)
    out_path = resolve_output_path(args).resolve()
    max_scenes = args.max_scenes if args.max_scenes is not None else (10 if args.mgrs else 3)
    diverse_paths = not args.no_diverse_paths

    log.info("=" * 56)
    log.info("Landsat C2 L2 SR mosaic — single AOI run")
    log.info("AOI: %s", aoi_label)
    log.info("BBox WGS84: %s", bbox)
    log.info("Output EPSG:%s  resolution=%.1f m", epsg, args.resolution)
    log.info("Output file: %s", out_path)
    log.info(
        "datetime=%s max_scenes=%d diverse_paths=%s composite=%s max_cloud=%.1f",
        args.datetime,
        max_scenes,
        diverse_paths,
        args.composite,
        args.max_cloud,
    )
    if args.log_file:
        log.info("Log file: %s", args.log_file)

    log_phase(1, 4, "STAC catalog search")
    t_search = time.perf_counter()
    items = search_items(
        bbox=bbox,
        datetime_range=args.datetime,
        max_cloud=args.max_cloud,
        platform=args.platform,
        max_scenes=max_scenes,
        diverse_paths=diverse_paths,
    )
    stac_search_s = time.perf_counter() - t_search

    log_phase(2, 4, "stackstac setup + COG read + composite")
    data, stack_timing = stack_scenes(
        items, bbox, epsg, args.resolution, composite=args.composite, load_pixels=True
    )

    log_phase(3, 4, "Coverage QA")
    report_valid_coverage(data)

    log_phase(4, 4, "Write GeoTIFF")
    t0 = time.perf_counter()
    write_geotiff(data, out_path)
    write_s = time.perf_counter() - t0

    timing = PhaseTiming(
        stac_search_s=stac_search_s,
        stack_setup_s=stack_timing["stack_setup_s"],
        cog_read_composite_s=stack_timing["cog_read_composite_s"],
        write_geotiff_s=write_s,
        total_s=stac_search_s + stack_timing["stack_setup_s"]
        + stack_timing["cog_read_composite_s"] + write_s,
        io_read_bytes=stack_timing["io_read_bytes"],
        output_bytes=out_path.stat().st_size if out_path.is_file() else None,
        scene_ids=[it.id for it in items],
    )
    log.info("Timing summary:")
    for line in timing.log_lines():
        log.info(line)

    log.info(
        "Next: chip this GeoTIFF for SSL4EO (256 or 264 px, 7 bands). "
        "Reflectance is float32 0–1; multiply by 255 if your model expects 0–255 scale."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
