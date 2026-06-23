#!/usr/bin/env bash
# Caracterizacion local scale300 (4 corridas) — sin Earth Engine.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/activate_mb_labels.sh"

export GRILLAS_ROOT="${GRILLAS_ROOT:-/home/lserey/mapbiomas_land/prod/samples}"
export MAPBIOMAS_LAND_ROOT="${MAPBIOMAS_LAND_ROOT:-/home/lserey/mapbiomas_land}"
export PYTHONPATH="${SCRIPT_DIR}/../scripts:${PYTHONPATH:-}"
cd "${SCRIPT_DIR}/.."

bash "${SCRIPT_DIR}/check_inputs.sh"

python scripts/01_local_grid_characterization.py --run-scale300-all
