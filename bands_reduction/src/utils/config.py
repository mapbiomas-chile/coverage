"""Load and merge YAML configs; path helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_path(value: str | Path | None, *, base: Path | None = None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    root = base or project_root()
    return (root / path).resolve()


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_configs(
    global_config: str | Path,
    ecoregion_config: str | Path | None = None,
    local_config: str | Path | None = None,
) -> dict[str, Any]:
    """Load global.yaml, optional local.yaml, optional ecoregion YAML."""
    cfg = load_yaml(global_config)
    gpath = Path(global_config)
    if local_config is None:
        candidate = gpath.parent / "local.yaml"
        if candidate.is_file():
            local_config = candidate
    if local_config is not None and Path(local_config).is_file():
        cfg = _deep_merge(cfg, load_yaml(local_config))
    if ecoregion_config is not None:
        eco = load_yaml(ecoregion_config)
        cfg["ecoregion"] = eco.get("ecoregion", eco)
        if "pilot" in eco:
            cfg["pilot"] = eco["pilot"]
    return cfg


def resolve_results_dir(cfg: dict[str, Any], repo_root: Path) -> Path:
    """Repo-local results root (paths.results_dir, else ``<repo>/results``)."""
    raw = (cfg.get("paths") or {}).get("results_dir")
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (repo_root / p).resolve()
    return (repo_root / "results").resolve()


def eco_year_dir(results_dir: Path, eco_id: int, year: int) -> Path:
    return Path(results_dir) / f"E{eco_id}" / str(year)


def inventory_dir(results_dir: Path, eco_id: int, year: int) -> Path:
    return eco_year_dir(results_dir, eco_id, year) / "01_inventory"


def clusters_by_tile_dir(results_dir: Path, eco_id: int, year: int) -> Path:
    return eco_year_dir(results_dir, eco_id, year) / "02_clusters_by_tile"


def clusters_united_dir(results_dir: Path, eco_id: int, year: int) -> Path:
    return eco_year_dir(results_dir, eco_id, year) / "clusters_united"


def eco_merged_dir(results_dir: Path, eco_id: int, year: int) -> Path:
    """Official eco-level outputs: sample + clusters + representatives."""
    return eco_year_dir(results_dir, eco_id, year) / "eco_merged"


def corr_threshold_dirname(corr_thr: float) -> str:
    """Folder name for a |r| cut, e.g. 0.95 → ``0.95``."""
    return f"{float(corr_thr):.2f}"
