# Test tile selection (Google Earth Engine)

Earth Engine script to **select representative MGRS test tiles** over Chile, using the MapBiomas Chile tile grid (Collection 3) and the reference LULC classification (Collection 2).

This folder is part of the [mapbiomas-chile/coverage](https://github.com/mapbiomas-chile/coverage) repository.

**Repository layout** (two levels: a parent folder, then this folder inside it):

```text
classification_test/          ← parent directory (repo root)
└── test_tile_selection/      ← this directory (you are here)
    ├── README.md
    └── test_tile_selection.js
```

| File | Description |
|------|-------------|
| `test_tile_selection.js` | Paste into the [Earth Engine Code Editor](https://code.earthengine.google.com/) and run. |

A sibling implementation also exists in [Lissettecs/gee-test-tiles](https://github.com/Lissettecs/gee-test-tiles); this copy is maintained here for classification / coverage workflows.

---

## What the script does

1. Loads the MapBiomas Chile Sentinel tile collection and the final LULC classification (Collection 2).
2. Filters tiles by a **minimum overlap** between the tile geometry and valid (non-zero) LULC pixels.
3. Computes **per-class areas and metrics** inside each tile (configurable scale).
4. Picks a set of tiles **spread across latitude bands**; if some bands are empty, it fills with the most “representative” remaining tiles (dominance, overlap, class diversity).
5. Adds **map layers**, UI panels, and **export tasks** (Google Drive and, optionally, an Earth Engine Asset).

---

## Requirements

| Requirement | Notes |
|-------------|--------|
| Google Earth Engine account | [Sign up](https://earthengine.google.com/signup/) or institutional access. |
| Read access to MapBiomas Chile assets | Paths under `projects/mapbiomas-chile/assets/...`. Permission errors mean you need project access or local asset substitutes. |
| Google Drive folder (optional) | For `Export.table.toDrive`, create the folder in `DRIVE_FOLDER` or rename it. |

No Python is required for this script: it is **Code Editor** JavaScript.

---

## How to run (Code Editor)

1. Open [https://code.earthengine.google.com/](https://code.earthengine.google.com/).
2. Create a **new script** or use a GEE repository.
3. Copy and paste the full contents of **`test_tile_selection.js`** from this folder.
4. Save and click **Run**.

### What you should see

- **Console**: collection sizes, LULC band used, selected tile IDs, etc.
- **Map**: LULC, valid/selected tiles, centroids.
- **Tasks**: GeoJSON, CSV, and Asset exports—each task must be started manually from the **Tasks** tab.

---

## Parameters to review

Edit the initial block in `test_tile_selection.js`:

| Variable | Meaning | Typical values |
|----------|---------|----------------|
| `NUM_TILES_SELECCIONAR` | Target number of tiles in the final set. | `5`, `10`, `20`, … |
| `UMBRAL_OVERLAP_PCT` | Minimum tile–LULC overlap % (reduces ocean-dominated tiles). | `30` balanced; `50` stricter. |
| `YEAR_REF` | Year for `classification_<year>` on the LULC image. | Must exist on the asset; use console `lulc.bandNames()` if unsure. |
| `ANALYSIS_SCALE` | Meters for per-class `reduceRegion`. | `300` (fast) or `30` (slow, finer). |
| `DRIVE_FOLDER` | Google Drive folder for table exports. | e.g. `'MapBiomas_Chile'`. |
| `EXPORT_PREFIX` | Export name prefix. | Auto-built from tile count and threshold; customizable. |

---

## Exports and permissions

### Google Drive (GeoJSON and CSV)

- GeoJSON of selected tile geometries.
- CSV with descriptive metrics and per-class percentages.

Run the corresponding tasks after the script compiles.

### Earth Engine Asset

Default `assetId` is under `projects/mapbiomas-chile/assets/LULC/COLLECTION-03/ANCILLARY_DATA/...`. **Write access** to that project is required. Otherwise comment out `Export.table.toAsset` or point `assetId` to your own project.

---

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| Missing `classification_YYYY` band | Adjust `YEAR_REF`; inspect printed band names. |
| Memory / timeout errors | Raise `ANALYSIS_SCALE`, reduce `NUM_TILES_SELECCIONAR`, or tune `tileScale` with care. |
| Too few selected tiles | Lower `UMBRAL_OVERLAP_PCT` or check valid tiles in the script’s latitude range. |
| Asset export denied | Use Drive exports or a personal `assetId`. |

---

## Credits

Underlying MapBiomas Chile data and terms of use apply. Follow Earth Engine and MapBiomas policies when publishing results.
