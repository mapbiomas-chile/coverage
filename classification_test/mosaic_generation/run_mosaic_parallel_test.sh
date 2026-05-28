#!/usr/bin/env bash
# Parallel Landsat SR mosaic test — 6 MGRS tiles via Planetary Computer.
#
# Two backends share the same tile list / params:
#
#   stackstac (default) → fetch_landsat_mosaic_batch_pc.py
#       N tiles in parallel, each tile via stackstac + Dask (multi-threaded
#       intra-tile). Parent prints a progress table every 15 s; per-tile
#       detail goes to logs/<slug>/<TILE>.log.
#
#   serial              → fetch_landsat_serial_batch_pc.py
#       N tiles in parallel, each tile fetched band-by-band (rasterio +
#       WarpedVRT, one HTTPS request at a time). Worker logs stream live
#       to stdout prefixed by [TILE]; per-tile detail in
#       logs/<slug>/log_<TILE>_<slug>.log.
#
# Usage:
#   ./run_mosaic_parallel_test.sh                    # stackstac backend
#   ./run_mosaic_parallel_test.sh stackstac          # explicit stackstac
#   ./run_mosaic_parallel_test.sh serial             # serial-by-band backend
#
#   # Any extra args after the backend keyword are forwarded to the python script:
#   ./run_mosaic_parallel_test.sh stackstac --dry-run
#   ./run_mosaic_parallel_test.sh serial --skip-existing -v
#   ./run_mosaic_parallel_test.sh stackstac --progress-interval 5

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BACKEND="${1:-stackstac}"
if [[ "$BACKEND" == "stackstac" || "$BACKEND" == "serial" ]]; then
    shift || true
else
    BACKEND="stackstac"
fi

case "$BACKEND" in
    stackstac)
        PY_SCRIPT="fetch_landsat_mosaic_batch_pc.py"
        DATA_DIR="${HOME}/data/mosaic_parallel_test"
        ;;
    serial)
        PY_SCRIPT="fetch_landsat_serial_batch_pc.py"
        DATA_DIR="${HOME}/data/mosaic_parallel_test_serial"
        ;;
    *)
        echo "Unknown backend: $BACKEND  (use 'stackstac' or 'serial')" >&2
        exit 2
        ;;
esac

TILES="18FXH,18GXP,18HYD,19HCD,19JCJ,19KDU"
WORKERS=6
DATETIME="2024-01-01/2024-03-31"
MAX_SCENES=5
SLUG="${DATETIME//\//_}"

mkdir -p "$DATA_DIR"
CONSOLE_LOG="${DATA_DIR}/console_$(date +%Y%m%d_%H%M%S).log"

echo "Backend:     $BACKEND  ($PY_SCRIPT)"
echo "Output dir:  $DATA_DIR"
echo "Tiles:       $TILES"
echo "Workers:     $WORKERS"
echo "Datetime:    $DATETIME"
echo "Console log: $CONSOLE_LOG"
echo

python -u "$PY_SCRIPT" \
  --tiles "$TILES" \
  --workers "$WORKERS" \
  --datetime "$DATETIME" \
  --max-scenes "$MAX_SCENES" \
  --composite median \
  --data-dir "$DATA_DIR" \
  "$@" \
  2>&1 | tee "$CONSOLE_LOG"

echo
echo "Done. Outputs under: $DATA_DIR"
case "$BACKEND" in
    stackstac)
        echo "  GeoTIFFs:  ${DATA_DIR}/${SLUG}/mgrs_*_landsat_sr.tif"
        echo "  Manifest:  ${DATA_DIR}/manifest_${SLUG}.jsonl"
        echo "  Batch log: ${DATA_DIR}/batch_${SLUG}.log"
        echo "  Tile logs: ${DATA_DIR}/logs/${SLUG}/<TILE>.log"
        ;;
    serial)
        echo "  GeoTIFFs:    ${DATA_DIR}/${SLUG}/mgrs_*_${SLUG}.tif"
        echo "  Manifest:    ${DATA_DIR}/manifest_serial_batch_${SLUG}.jsonl"
        echo "  Batch log:   ${DATA_DIR}/batch_serial_${SLUG}.log"
        echo "  Tile logs:   ${DATA_DIR}/logs/${SLUG}/log_<TILE>_${SLUG}.log"
        echo "  Tile metrics ${DATA_DIR}/metrics/${SLUG}/metrics_<TILE>_${SLUG}.csv"
        ;;
esac
