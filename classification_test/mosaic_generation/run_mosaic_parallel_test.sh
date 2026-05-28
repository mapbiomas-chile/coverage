#!/usr/bin/env bash
# Parallel Landsat SR mosaic test — N MGRS tiles via Planetary Computer.
#
# Each tile is launched as a SEPARATE heavyweight Python subprocess
# (`python fetch_landsat_serial_pc.py --mgrs <TILE> …`). No Python-level
# pool, no fork, no threads — bash backgrounds N processes at a time and
# waits on them.
#
# Per-tile metrics (MiB/s, bytes, etc.) come from the serial script's
# per-process counter (psutil read_chars), so each tile's numbers are its
# own (not contaminated by sibling processes).
#
# Worker logs stream to the inherited stdout with [TILE] prefix and to
# per-tile log/CSV files under --data-dir.
#
# Usage:
#   ./run_mosaic_parallel_test.sh                # default tiles & params
#   ./run_mosaic_parallel_test.sh -v             # forward extra flags to python
#   ./run_mosaic_parallel_test.sh --max-cloud 10

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DATA_DIR="${HOME}/data/mosaic_parallel_test"
TILES="18FXH,18GXP,18HYD,19HCD,19JCJ,19KDU"
WORKERS=6
DATETIME="2024-01-01/2024-03-31"
MAX_SCENES=5
SLUG="${DATETIME//\//_}"

mkdir -p "$DATA_DIR"
CONSOLE_LOG="${DATA_DIR}/console_$(date +%Y%m%d_%H%M%S).log"

EXTRA_ARGS=("$@")

run_tile() {
    local TILE="$1"
    python -u fetch_landsat_serial_pc.py \
        --mgrs "$TILE" \
        --datetime "$DATETIME" \
        --max-scenes "$MAX_SCENES" \
        --composite median \
        --data-dir "$DATA_DIR" \
        "${EXTRA_ARGS[@]}"
}

main() {
    echo "Data dir:    $DATA_DIR"
    echo "Tiles:       $TILES"
    echo "Workers:     $WORKERS (max concurrent independent python subprocesses)"
    echo "Datetime:    $DATETIME"
    echo "Console log: $CONSOLE_LOG"
    echo "Extra args:  ${EXTRA_ARGS[*]:-(none)}"
    echo

    IFS=',' read -ra TILE_ARRAY <<< "$TILES"
    local N_TILES=${#TILE_ARRAY[@]}

    local T_START
    T_START=$(date +%s)
    local PIDS=()
    local PID_TILES=()

    for TILE in "${TILE_ARRAY[@]}"; do
        while [[ $(jobs -r -p | wc -l) -ge $WORKERS ]]; do
            sleep 0.5
        done
        echo "[bash $(date +%H:%M:%S)] Launching $TILE …"
        run_tile "$TILE" &
        PIDS+=("$!")
        PID_TILES+=("$TILE")
    done

    local FAIL=0
    local IDX=0
    for PID in "${PIDS[@]}"; do
        local TILE="${PID_TILES[$IDX]}"
        if wait "$PID"; then
            echo "[bash $(date +%H:%M:%S)] $TILE (PID $PID) OK"
        else
            local RC=$?
            echo "[bash $(date +%H:%M:%S)] $TILE (PID $PID) FAILED rc=$RC"
            FAIL=$((FAIL + 1))
        fi
        IDX=$((IDX + 1))
    done

    local T_END
    T_END=$(date +%s)
    local ELAPSED=$((T_END - T_START))
    echo
    echo "Done — ${N_TILES} tile(s), ${FAIL} failure(s), wall=${ELAPSED}s"
    echo "Outputs under: $DATA_DIR"
    echo "  GeoTIFF:  ${DATA_DIR}/mgrs_<TILE>_${SLUG}.tif"
    echo "  Log:      ${DATA_DIR}/log_<TILE>_${SLUG}.log"
    echo "  Metrics:  ${DATA_DIR}/metrics_<TILE>_${SLUG}.csv"
    return "$FAIL"
}

main 2>&1 | tee "$CONSOLE_LOG"
exit "${PIPESTATUS[0]}"
