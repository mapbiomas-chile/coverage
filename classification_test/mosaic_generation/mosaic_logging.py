"""Shared logging helpers for Landsat mosaic scripts."""

from __future__ import annotations

import logging
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

LOGGER_NAME = "landsat_mosaic"


def setup_logging(
    *,
    level: str = "INFO",
    log_file: Path | None = None,
    tile: str | None = None,
    console: bool = True,
) -> logging.Logger:
    """
    Configure the landsat_mosaic logger.

    level: DEBUG | INFO | WARNING | ERROR
    log_file: optional path (parent dirs created)
    tile: prefix worker logs, e.g. [19HCD]
    console: emit to stdout (disable in quiet worker mode if log_file set)
    """
    # Make stdout line-buffered so progress appears immediately
    # (Python forces full buffering when stdout is not a TTY, e.g. piped to tee).
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, OSError):
        pass

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    prefix = f"[{tile}] " if tile else ""
    fmt = logging.Formatter(
        f"%(asctime)s %(levelname)-5s {prefix}%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if console:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


@contextmanager
def heartbeat(label: str, *, interval_s: float = 15.0, progress_fn=None):
    """
    Emit a "... still running" log line every interval_s seconds while
    the wrapped block runs. Useful around long blocking calls like
    stackstac's data.load() or rio.to_raster() so the user sees progress.

    progress_fn: optional callable returning a short progress string to append.
    """
    log = get_logger()
    started = time.perf_counter()
    stop = threading.Event()

    def _tick() -> None:
        while not stop.wait(interval_s):
            elapsed = time.perf_counter() - started
            extra = ""
            if progress_fn is not None:
                try:
                    extra = f" — {progress_fn()}"
                except Exception:
                    extra = ""
            log.info("  ... %s in progress — %.0fs elapsed%s", label, elapsed, extra)

    th = threading.Thread(target=_tick, name=f"hb-{label}", daemon=True)
    th.start()
    try:
        yield
    finally:
        stop.set()
        th.join(timeout=1.0)


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def log_phase(step: int, total: int, title: str) -> None:
    get_logger().info("—" * 56)
    get_logger().info("Phase %d/%d: %s", step, total, title)


def resolve_log_level(*, verbose: bool, quiet: bool) -> str:
    if quiet:
        return "WARNING"
    if verbose:
        return "DEBUG"
    return "INFO"
