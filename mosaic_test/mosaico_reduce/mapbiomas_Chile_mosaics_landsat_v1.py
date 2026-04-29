"""
Google Earth Engine Landsat Mosaic Generator for Chile
===========================================================

This script generates annual Landsat mosaics for Chile using Google Earth Engine.
It processes Landsat Collection 2 imagery (Landsat 4-9) with cloud/shadow masking,
spectral indices calculation, and SMA (Spectral Mixture Analysis) to create
analysis-ready composite images organized by grid tiles.

Version: 1
Dependencies: earthengine-api, custom MapBiomas modules

Recent changes (2026-03-31)
---------------------------
1) JSON-driven execution:
   - `gridNames` and the job list come from the JSON parameter file.
   - One export task per JSON row; natural key is (grid_name, year, satellite).
"""

import ee
import sys
import os
import json
import traceback
from datetime import datetime

# -----------------------------------------------------------------------------
# Runtime switches (override via environment when scripting CI/batch runs):
#   MOSAIC_REDUCED_MODE=1   -> only optical bands + NDVI/NDWI + reduced stats (default)
#   MOSAIC_REDUCED_MODE=0   -> full indices + SMA + Chile band typing + terrain
#   MOSAIC_EXPORT_TAG=foo   -> appended to exportAssetSuffix so asset names stay unique
#   MOSAIC_MAX_JOBS=N      -> process only first N JSON rows per territory (smoke tests)
#   MOSAIC_SKIP_ACTIVE_TASK_GUARD=1 -> skip slow ee.batch.Task.list() at startup
# -----------------------------------------------------------------------------

def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str):
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return None
    return int(str(raw).strip())


REDUCED_MODE = _env_bool("MOSAIC_REDUCED_MODE", True)
STRICT_SENSOR_YEAR_GUARD = _env_bool("MOSAIC_STRICT_SENSOR_YEAR_GUARD", True)
REQUIRE_EXPORT_TAG = _env_bool("MOSAIC_REQUIRE_EXPORT_TAG", True)

_export_tag = os.environ.get("MOSAIC_EXPORT_TAG", "").strip()
_export_suffix_extra = f"-{_export_tag}" if _export_tag else ""
if REQUIRE_EXPORT_TAG and not _export_tag:
    raise ValueError(
        "MOSAIC_EXPORT_TAG is required when MOSAIC_REQUIRE_EXPORT_TAG=1. "
        "Set a unique tag (e.g. pedro-20260428) to avoid collisions in shared accounts."
    )

# Add custom module paths to Python path
sys.path.append(os.path.abspath('..\\'))
sys.path.append(os.path.abspath('..\\mapbiomas-mosaics'))

print(sys.path)

# Import custom MapBiomas modules for processing
from modules.CloudAndShadowMaskC2 import *
from modules.SpectralIndexes import *
from modules.Miscellaneous import *
from modules.SmaAndNdfi import *
from modules.Collection import *
from modules.BandNames import * 
from modules.DataType import *
from modules.Mosaic import *

# Prevent Python from writing .pyc files
sys.dont_write_bytecode = True

# Initialize Google Earth Engine with MapBiomas Chile project
ee.Initialize(project = "mapbiomas-chile")

# ============================================================================
# CONFIGURATION PARAMETERS
# ============================================================================

# JSON parameter file generated from spreadsheet
# JSON input with READY=TRUE mosaics parameters.
# Expected location (when running from this directory):
paramsJsonPath = "input_params_2026_SJ-18-X-B.json"

# Appended to the export asset name so jobs are not skipped when an asset without
# this suffix already exists. Production runs: use "".
# MOSAIC_EXPORT_TAG is appended when set (see header) to avoid overwriting assets.
if REDUCED_MODE:
    _default_export_suffix = "-REDUCED-NDVI-NDWI-v2"
else:
    _default_export_suffix = "-PROD"
exportAssetSuffix = _default_export_suffix + _export_suffix_extra

# Version of the landsat masks to use
versionMasks = '2'

# Asset path for 1:250,000 scale grid system (CIM world grid)
gridsAsset = 'projects/mapbiomas-workspace/AUXILIAR/cim-world-1-250000'

# Asset path for Landsat tile masks (removes image edge artifacts)
assetMasks = "projects/mapbiomas-workspace/AUXILIAR/landsat-mask"


# Territory names to process (no spaces allowed)
territoryNames = [
    'CHILE'
]

# Version numbers for each territory
version = {
    'CHILE': '3',
}

# Data filtering parameters for each territory
dataFilter = {
    'CHILE': {
        'dateStart': '01-01',
        'dateEnd': '12-31',
        'cloudCover': 80
    },
}

# Grid names (1:250,000 map sheets) covering Chile
gridNames = { "CHILE": [] }

# Google Earth Engine Collection IDs for Landsat satellites (Collection 2, Tier 1, Level 2)
collectionIds = {
    'l4': 'LANDSAT/LT04/C02/T1_L2',  # Landsat 4 TM (1982-1993)
    'l5': 'LANDSAT/LT05/C02/T1_L2',  # Landsat 5 TM (1984-2013)
    'l7': 'LANDSAT/LE07/C02/T1_L2',  # Landsat 7 ETM+ (1999-present)
    'l8': 'LANDSAT/LC08/C02/T1_L2',  # Landsat 8 OLI (2013-present)
    'l9': 'LANDSAT/LC09/C02/T1_L2',  # Landsat 9 OLI-2 (2021-present)
}

# Landsat identifiers for SMA endmember selection
landsatIds = {
    'l4': 'landsat-4',
    'l5': 'landsat-5',
    'l7': 'landsat-7',
    'l8': 'landsat-8',
    'l9': 'landsat-9',
}

# Output asset collections for each Landsat sensor
outputCollections = {
    'l4': 'projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2',
    'l5': 'projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2',
    'l7': 'projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2',
    'l8': 'projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2',
    'l9': 'projects/mapbiomas-chile/assets/MOSAICS/test_landcover_2'
}

# Keep export compact: only optical Landsat bands + NDVI/NDWI medians.
CORE_BANDS_ONLY_EXPORT = _env_bool("MOSAIC_CORE_BANDS_ONLY_EXPORT", True)

# Buffer size in meters to expand grid boundaries (reduces edge effects)
bufferSize = 100

# Year and satellite combinations to process
# Format: [year, satellite_code]
yearsSat = []


def parse_iso_date(value, fallback):
    text = str(value or "").strip()
    if not text:
        return fallback
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return fallback


def normalize_satellite(value):
    text = str(value or "").strip().lower()
    if text in {"l4", "l5", "l7", "l8", "l9"}:
        return text
    if text in {"4", "5", "7", "8", "9"}:
        return f"l{text}"
    if text.startswith("l") and len(text) > 1 and text[1:].isdigit():
        return text
    raise ValueError(f"Invalid satellite code in JSON: {value}")


def valid_sensors_for_year(year):
    """Return allowed Landsat sensors for a given year in this pipeline."""
    # Requested L7 validity window: [1984-01-01, 2017-01-01)
    l7_start_year = 1984
    l7_end_year_exclusive = 2017

    if year <= 1998:
        allowed = {"l4", "l5"}
    elif year <= 2012:
        allowed = {"l5"}
    elif year <= 2020:
        allowed = {"l8"}
    else:
        allowed = {"l8", "l9"}

    if l7_start_year <= year < l7_end_year_exclusive:
        allowed.add("l7")

    return allowed


def is_valid_year_sensor_combo(year, satellite):
    return satellite in valid_sensors_for_year(year)


def list_active_export_descriptions():
    """Return descriptions for RUNNING/READY Earth Engine export tasks."""
    active_states = {"READY", "RUNNING"}
    descriptions = set()
    try:
        for task in ee.batch.Task.list():
            status = task.status()
            state = str(status.get("state", "")).upper()
            desc = str(status.get("description", "")).strip()
            if state in active_states and desc:
                descriptions.add(desc)
    except Exception as exc:
        print(f"Warning: could not list active tasks: {exc}")
    return descriptions


def gee_output_asset_exists(asset_id: str) -> bool:
    """True if an Earth Engine asset already exists at asset_id (prevents overwrite)."""
    try:
        ee.data.getAsset(asset_id)
        return True
    except Exception:
        return False


def load_processing_params(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    params_by_territory = {}
    params_index = {}

    def to_bool(value, default=True):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if not s:
            return default
        if s in {"false", "0", "no", "n", "off"}:
            return False
        if s in {"true", "1", "yes", "y", "on"}:
            return True
        return default

    for item in records:
        territory = str(item.get("country", "CHILE")).strip().upper()
        grid_name = str(item.get("grid_name", "")).strip()
        year = int(item.get("year"))
        satellite = normalize_satellite(item.get("satellite"))

        if not grid_name:
            continue

        default_start = f"{year}-01-01"
        default_end = f"{year}-12-31"

        cloud_cover_raw = item.get("cloud_cover", 80)
        cloud_cover = int(cloud_cover_raw) if str(cloud_cover_raw).strip() else 80

        black_list_raw = item.get("black_list", [])
        if isinstance(black_list_raw, list):
            black_list = [str(x).strip() for x in black_list_raw if str(x).strip()]
        elif str(black_list_raw).strip():
            black_list = [str(black_list_raw).strip()]
        else:
            black_list = []

        # If false, do not apply the tile mask stored in assetMasks and do not filter tiles by mask existence.
        use_tile_mask = to_bool(
            item.get("USETILEMASK", item.get("usetilemask", item.get("use_tile_mask"))),
            default=True,
        )

        param = {
            "territory": territory,
            "grid_name": grid_name,
            "year": year,
            "satellite": satellite,
            "date_start": parse_iso_date(item.get("t0_s"), default_start),
            "date_end": parse_iso_date(item.get("t1_s"), default_end),
            "cloud_cover": cloud_cover,
            "black_list": black_list,
            "use_tile_mask": use_tile_mask,
        }

        params_by_territory.setdefault(territory, []).append(param)
        params_index[(territory, grid_name, year, satellite)] = param

    return params_by_territory, params_index


processingParamsByTerritory, processingParamsIndex = load_processing_params(paramsJsonPath)

_mosaic_max_jobs = _env_int("MOSAIC_MAX_JOBS")
if _mosaic_max_jobs is not None and _mosaic_max_jobs > 0:
    for _terr in list(processingParamsByTerritory.keys()):
        processingParamsByTerritory[_terr] = processingParamsByTerritory[_terr][:_mosaic_max_jobs]
    print(
        f"MOSAIC_MAX_JOBS: {_mosaic_max_jobs} row(s) per territory "
        "(unset to process full JSON)"
    )

# Override static config with JSON-driven parameters
territoryNames = sorted(processingParamsByTerritory.keys())
gridNames = {
    territory: sorted({p["grid_name"] for p in params})
    for territory, params in processingParamsByTerritory.items()
}
print(f"Loaded {sum(len(v) for v in processingParamsByTerritory.values())} parameter rows from JSON")
print(f"Territories: {territoryNames}")
print(f"Unique grid count: {sum(len(v) for v in gridNames.values())}")
print(
    "Export jobs (one per JSON row; unique key is grid_name + year + satellite): "
    f"{sum(len(v) for v in processingParamsByTerritory.values())}"
)

# In-memory guard avoids duplicate submissions during a single execution.
submittedOutputNames = set()
# Guard against re-submitting jobs already queued/running in EE.
if _env_bool("MOSAIC_SKIP_ACTIVE_TASK_GUARD", False):
    print(
        "MOSAIC_SKIP_ACTIVE_TASK_GUARD: skipping ee.batch.Task.list() (faster startup)"
    )
    activeTaskDescriptions = set()
else:
    print("Listing READY/RUNNING Earth Engine export tasks...")
    sys.stdout.flush()
    activeTaskDescriptions = list_active_export_descriptions()
print(f"Active EE tasks detected (READY/RUNNING): {len(activeTaskDescriptions)}")
print(f"REDUCED_MODE: {REDUCED_MODE}  (set MOSAIC_REDUCED_MODE=0 for full pipeline)")
print(
    "STRICT_SENSOR_YEAR_GUARD: "
    f"{STRICT_SENSOR_YEAR_GUARD}  "
    "(set MOSAIC_STRICT_SENSOR_YEAR_GUARD=0 to allow non-standard year/sensor rows)"
)
print(
    "CORE_BANDS_ONLY_EXPORT: "
    f"{CORE_BANDS_ONLY_EXPORT}  "
    "(set MOSAIC_CORE_BANDS_ONLY_EXPORT=0 to keep legacy extra bands/statistics)"
)
print(
    "REQUIRE_EXPORT_TAG: "
    f"{REQUIRE_EXPORT_TAG}  "
    "(set MOSAIC_REQUIRE_EXPORT_TAG=0 only if you intentionally allow runs without explicit tag)"
)
print(f"export asset name suffix: {exportAssetSuffix!r}")
if _export_tag:
    print(f"MOSAIC_EXPORT_TAG: {_export_tag!r}")


def multiplyBy10000(image):
    if REDUCED_MODE:
        bands = [
            'blue',
            'red',
            'green',
            'nir',
            'swir1',
            'swir2',
            'ndvi',
            'ndwi',
        ]
    else:
        bands = [
            'blue',
            'red',
            'green',
            'nir',
            'swir1',
            'swir2',
            'cai',
            'evi2',
            'gcvi',
            'hallcover',
            'hallheigth',
            'ndvi',
            'ndwi',
            'pri',
            'savi',
            'ndbi',
            'ndmi',
            'ndsi',
            'mbi',
        ]

    return image.addBands(
        srcImg=image.select(bands).multiply(10000),
        names=bands,
        overwrite=True
    )


def divideBy10000(image):

    bands = [
        'blue',
        'red',
        'green',
        'nir',
        'swir1',
        'swir2'
    ]

    return image.addBands(
        srcImg=image.select(bands).divide(10000),
        names=bands,
        overwrite=True
    )


def applyCloudAndShadowMask(collection):

    # Get cloud and shadow masks
    collectionWithMasks = getMasks(collection,
                                   cloudThresh=10,
                                   cloudFlag=True,
                                   cloudScore=True,
                                   cloudShadowFlag=True,
                                   cloudShadowTdom=True,
                                   zScoreThresh=-1,
                                   shadowSumThresh=4000,
                                   dilatePixels=4,
                                   cloudHeights=[
                                       200, 700, 1200, 1700, 2200, 2700,
                                       3200, 3700, 4200, 4700
                                   ],
                                   cloudBand='cloudShadowFlagMask')

    # get collection without clouds
    collectionWithoutClouds = collectionWithMasks \
        .map(
            lambda image: image.mask(
                image.select([
                    'cloudFlagMask',
                    'cloudShadowFlagMask'  # ,
                    # 'cloudScoreMask',
                    # 'cloudShadowTdomMask'
                ]).reduce(ee.Reducer.anyNonZero()).eq(0)
            )
        )

    return collectionWithoutClouds


def getTiles(collection):

    collection = collection.map(
        lambda image: image.set(
            'tile', {
                'path': image.get('WRS_PATH'),
                'row': image.get('WRS_ROW'),
                'id': ee.Number(image.get('WRS_PATH'))
                        .multiply(1000).add(image.get('WRS_ROW')).int32()
            }
        )
    )

    tiles = collection.distinct(['tile']).reduceColumns(
        ee.Reducer.toList(), ['tile']).get('list')

    return tiles.getInfo()


def getExcludedImages(biome, year):

    assetId = 'projects/mapbiomas-workspace/MOSAICOS/workspace-c5'

    collection = ee.ImageCollection(assetId) \
        .filterMetadata('region', 'equals', biome) \
        .filterMetadata('year', 'equals', str(year))

    excluded = ee.List(collection.reduceColumns(ee.Reducer.toList(), ['black_list']).get('list')) \
        .map(
            lambda names: ee.String(names).split(',')
    )

    return excluded.flatten().getInfo()


# ============================================================================
# MAIN PROCESSING LOOP
# ============================================================================

# Load all available tile masks for filtering valid path/row combinations
collectionTiles = ee.ImageCollection(assetMasks)

allTiles = collectionTiles.reduceColumns(
    ee.Reducer.toList(), ['tile']).get('list').getInfo()

# Process each territory (currently only Paraguay)
for territoryName in territoryNames:

    # Load grid features for this territory
    grids = ee.FeatureCollection(gridsAsset)\
        .filter(
        ee.Filter.inList('name', gridNames[territoryName])
    )

    # One export per JSON row: unique (grid_name, year, satellite)
    for param in processingParamsByTerritory[territoryName]:
        gridName = param["grid_name"]
        year = param["year"]
        satellite = param["satellite"]
        paramConfig = param

        print(year, satellite, gridName)
        if not is_valid_year_sensor_combo(year, satellite):
            allowed = ", ".join(sorted(valid_sensors_for_year(year)))
            msg = (
                f"Invalid year/satellite combination for {gridName} ({year}, {satellite}). "
                f"Allowed sensors for {year}: {allowed}."
            )
            if STRICT_SENSOR_YEAR_GUARD:
                print(f"Skipping row due to strict guard: {msg}")
                continue
            print(f"Warning: {msg}")

        # Per-combination parameters from JSON
        dateStart = paramConfig["date_start"]
        dateEnd = paramConfig["date_end"]
        cloudCover = paramConfig["cloud_cover"]

        try:
            # Check if this mosaic already exists in the output collection
            alreadyInCollection = ee.ImageCollection(outputCollections[satellite]) \
                .filterMetadata('year', 'equals', year) \
                .filterMetadata('territory', 'equals', territoryName) \
                .reduceColumns(ee.Reducer.toList(), ['system:index']) \
                .get('list') \
                .getInfo()
            
            # Construct output asset name
            outputName = 'TMP-' + territoryName + '-' + \
                gridName + '-' + \
                str(year) + '-' + \
                satellite.upper() + '-' + \
                str(version[territoryName]) + \
                exportAssetSuffix

            output_asset_id = outputCollections[satellite] + '/' + outputName
            asset_on_gee = gee_output_asset_exists(output_asset_id)
            
            # Skip if asset exists in GEE, collection reports it, task is queued, or duplicate in this run.
            if (
                not asset_on_gee
                and outputName not in alreadyInCollection
                and outputName not in activeTaskDescriptions
                and outputName not in submittedOutputNames
            ):
                
                # Define processing geometry with buffer
                grid = grids.filter(ee.Filter.eq('name', gridName))
                grid = ee.Feature(grid.first()).geometry()\
                    .buffer(bufferSize).bounds()

                excluded = paramConfig["black_list"]

                # Retrieve Landsat images for this grid and year
                collection = getCollection(collectionIds[satellite],
                                           dateStart=dateStart,
                                           dateEnd=dateEnd,
                                           cloudCover=cloudCover,
                                           geometry=grid,
                                           trashList=excluded
                                           )

                # Detect which Landsat tiles (path/row) intersect this grid
                tiles = getTiles(collection)
                use_tile_mask = bool(paramConfig.get("use_tile_mask", True))
                # If use_tile_mask is enabled, filter only tiles with available mask assets.
                # Otherwise keep all tiles (so scenes are not filtered out just because the mask asset is missing).
                if use_tile_mask:
                    tiles = list(
                        filter(
                            lambda tile: tile['id'] in allTiles,
                            tiles
                        )
                    )

                subcollectionList = []
                
                if len(tiles) > 0:
                    # Process each Landsat tile separately to apply tile-specific masks
                    for tile in tiles:
                        print(tile['path'], tile['row'])

                        # Filter collection to this specific path/row
                        subcollection = collection \
                            .filterMetadata('WRS_PATH', 'equals', tile['path']) \
                            .filterMetadata('WRS_ROW', 'equals', tile['row'])

                        # Load and apply tile mask (removes edge artifacts)
                        if use_tile_mask:
                            tileMask = ee.Image(
                                '{}/{}-{}'.format(assetMasks, tile['id'], versionMasks))

                            subcollection = subcollection.map(
                                lambda image: image.mask(tileMask).selfMask()
                            )

                        subcollectionList.append(subcollection)

                    # Merge all tile subcollections into single collection
                    collection = ee.List(subcollectionList) \
                        .iterate(
                            lambda subcollection, collection:
                                ee.ImageCollection(
                                    collection).merge(subcollection),
                            ee.ImageCollection([])
                    )

                    collection = ee.ImageCollection(collection)

                    # Standardize band names to consistent naming convention
                    bands = getBandNames(satellite + 'c2')
                    collection = collection.select(
                        bands['bandNames'],
                        bands['newNames']
                    )

                    # Apply cloud and shadow masking
                    collection = applyCloudAndShadowMask(collection)

                    if REDUCED_MODE:
                        # Reduced test profile:
                        # original optical bands + NDVI/NDWI only.
                        collection = (collection
                            .map(divideBy10000)
                            .map(getNDVI)
                            .map(getNDWI)
                            .map(multiplyBy10000)
                            .map(
                                lambda image: image.select([
                                    "blue", "green", "red", "nir", "swir1", "swir2",
                                    "ndvi", "ndwi"
                                ])
                            )
                        )
                    else:
                        endmember = ENDMEMBERS[landsatIds[satellite]]
                        collection = collection.map(
                            lambda image: image.addBands(
                                getFractions(image, endmember))
                        )
                        collection = collection\
                            .map(getNDFI)\
                            .map(getSEFI)\
                            .map(getWEFI)\
                            .map(getFNS)

                        collection = (collection
                            .map(divideBy10000)
                            .map(getCAI)
                            .map(getEVI2)
                            .map(getGCVI)
                            .map(getHallCover)
                            .map(getHallHeigth)
                            .map(getNDVI)
                            .map(getNDWI)
                            .map(getPRI)
                            .map(getSAVI)
                            .map(getNDBI)
                            .map(getNDMI)
                            .map(getNDSI)
                            .map(getMBI)
                            .map(multiplyBy10000)
                        )

                    # Generate annual mosaic using percentile-based compositing
                    # Pantanal uses NDWI (water index), others use NDVI (vegetation)
                    if territoryName in ['PANTANAL']:
                        percentileBand = 'ndwi'
                    else:
                        percentileBand = 'ndvi'

                    mosaic = getMosaic(collection,
                                       percentileDry=25,      # 25th percentile (dry season)
                                       percentileWet=75,      # 75th percentile (wet season)
                                       percentileBand=percentileBand,
                                       dateStart=dateStart,
                                       dateEnd=dateEnd)

                    if REDUCED_MODE:
                        keep_base = ["blue", "green", "red", "nir", "swir1", "swir2", "ndvi", "ndwi"]
                        stat_suffixes = [
                            "_median", "_median_dry", "_median_wet",
                            "_min", "_max", "_amp", "_stdDev"
                        ]
                        keep_bands = []
                        for base in keep_base:
                            keep_bands.extend([f"{base}{suffix}" for suffix in stat_suffixes])
                        keep_bands.extend(["ndvi_p25", "ndvi_p75"])
                        mosaic = mosaic.select(keep_bands)
                    else:
                        mosaic = promoteMedianToBaseName(
                            mosaic, ['mbi', 'ndbi', 'ndmi', 'ndsi'])

                        mosaic = getEntropyG(mosaic)
                        mosaic = getAspect(mosaic)
                        mosaic = getElevation(mosaic)
                        mosaic = getSlope(mosaic)
                        mosaic = getTpi(mosaic)

                        mosaic = setBandTypes(mosaic, mtype="chile")

                    if CORE_BANDS_ONLY_EXPORT:
                        export_bands = [
                            "blue_median",
                            "green_median",
                            "red_median",
                            "nir_median",
                            "swir1_median",
                            "swir2_median",
                            "ndvi_median",
                            "ndwi_median",
                        ]
                        mosaic = mosaic.select(export_bands)

                    # Unify CRS/resolution: Landsat mosaics are often UTM while AW3D30 terrain
                    # bands use a different grid. Mixed projections frequently break Export or
                    # server-side compositing; anchor to the Landsat median composite grid.
                    _ref = mosaic.select("blue_median")
                    mosaic = mosaic.reproject(crs=_ref.projection(), scale=30)

                    # Add metadata properties
                    mosaic = mosaic.set('year', year)
                    mosaic = mosaic.set('collection', 1.0)
                    mosaic = mosaic.set('grid_name', gridName)
                    mosaic = mosaic.set('version', str(version[territoryName]))
                    mosaic = mosaic.set('territory', territoryName)
                    mosaic = mosaic.set('satellite', satellite)

                    print(outputName)

                    # Export mosaic to Earth Engine asset
                    task = ee.batch.Export.image.toAsset(
                        image=mosaic,
                        description=outputName,
                        assetId=output_asset_id,
                        region=grid.coordinates().getInfo(),
                        scale=30,              # 30-meter spatial resolution
                        maxPixels=int(1e13)    # Maximum pixels to export
                    )

                    task.start()
                    submittedOutputNames.add(outputName)
            else:
                reason = []
                if asset_on_gee:
                    reason.append("asset id already on GEE")
                if outputName in alreadyInCollection:
                    reason.append("index in collection")
                if outputName in activeTaskDescriptions:
                    reason.append("export task pending/running")
                if outputName in submittedOutputNames:
                    reason.append("duplicate in this run")
                msg = ", ".join(reason) if reason else "skip guard"
                print(f"Skipping {outputName}: {msg}")
        except Exception as e:
            # Handle queue limit errors
            msg = 'Too many tasks already in the queue (3000). Please wait for some of them to complete.'
            if str(e) == msg:
                raise Exception(e)
            else:
                print(e)
                traceback.print_exc()
