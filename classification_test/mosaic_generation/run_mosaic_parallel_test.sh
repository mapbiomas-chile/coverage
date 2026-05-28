#!/usr/bin/env bash
# Parallel Landsat SR mosaic test — 6 MGRS tiles via Planetary Computer.
#
# Usage:
#   ./run_mosaic_parallel_test.sh
#   ./run_mosaic_parallel_test.sh --dry-run
#   ./run_mosaic_parallel_test.sh --skip-existing

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATA_DIR="${HOME}/data/mosaic_parallel_test"
TILES="18FXH,18GXP,18HYD,19HCD,19JCJ,19KDU"
WORKERS=6
DATETIME="2024-01-01/2024-03-31"
MAX_SCENES=5

mkdir -p "$DATA_DIR"

CONSOLE_LOG="${DATA_DIR}/console_$(date +%Y%m%d_%H%M%S).log"

echo "Output dir:  $DATA_DIR"
echo "Tiles:       $TILES"
echo "Workers:     $WORKERS"
echo "Datetime:    $DATETIME"
echo "Console log: $CONSOLE_LOG"
echo

python -u fetch_landsat_mosaic_batch_pc.py \
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
echo "  GeoTIFFs:  ${DATA_DIR}/${DATETIME//\//_}/mgrs_*_landsat_sr.tif"
echo "  Manifest:  ${DATA_DIR}/manifest_${DATETIME//\//_}.jsonl"
echo "  Tile logs: ${DATA_DIR}/logs/${DATETIME//\//_}/"
