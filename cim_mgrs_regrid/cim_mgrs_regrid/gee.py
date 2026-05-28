"""Shared Earth Engine helpers."""

from __future__ import annotations

import ee

from cim_mgrs_regrid.config import (
    ASSET_CIM_GRID,
    ASSET_MGRS_TILES,
    CIM_GRID_NAME_PROP,
    DEFAULT_EE_PROJECT,
    MGRS_TILE_ID_FIELDS,
)


def initialize(project: str = DEFAULT_EE_PROJECT) -> None:
    ee.Initialize(project=project)


def cim_grid_fc() -> ee.FeatureCollection:
    return ee.FeatureCollection(ASSET_CIM_GRID)


def mgrs_tiles_fc() -> ee.FeatureCollection:
    return ee.FeatureCollection(ASSET_MGRS_TILES)


def cim_feature(grid_name: str) -> ee.Feature:
    fc = cim_grid_fc().filter(ee.Filter.eq(CIM_GRID_NAME_PROP, grid_name))
    if fc.size().getInfo() == 0:
        raise ValueError(f"CIM grid not found ({CIM_GRID_NAME_PROP}={grid_name!r})")
    return ee.Feature(fc.first())


def detect_mgrs_tile_id_field(sample_limit: int = 1) -> str:
    """Return the first property name present on MGRS tiles that can serve as tile id."""
    sample = mgrs_tiles_fc().limit(sample_limit).first()
    if sample is None:
        raise RuntimeError("MGRS tiles asset is empty")
    props = sample.propertyNames().getInfo()
    prop_set = set(props)
    for field in MGRS_TILE_ID_FIELDS:
        if field in prop_set:
            return field
    raise RuntimeError(
        f"No known tile id field on {ASSET_MGRS_TILES}. "
        f"Properties on first feature: {props}"
    )


def mgrs_tile_id(feature: ee.Feature, id_field: str) -> str:
    value = feature.get(id_field)
    if value is not None:
        return str(value.getInfo())
    return str(feature.id().getInfo())


def inspect_assets() -> dict:
    """Counts and property names for CIM and MGRS assets."""
    initialize()
    cim = cim_grid_fc()
    mgrs = mgrs_tiles_fc()
    cim_sample = ee.Feature(cim.first())
    mgrs_sample = ee.Feature(mgrs.first())
    mgrs_id_field = detect_mgrs_tile_id_field()
    return {
        "cim_asset": ASSET_CIM_GRID,
        "cim_count": cim.size().getInfo(),
        "cim_properties": cim_sample.propertyNames().getInfo(),
        "mgrs_asset": ASSET_MGRS_TILES,
        "mgrs_count": mgrs.size().getInfo(),
        "mgrs_properties": mgrs_sample.propertyNames().getInfo(),
        "mgrs_tile_id_field": mgrs_id_field,
    }
