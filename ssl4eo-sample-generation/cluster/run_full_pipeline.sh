#!/usr/bin/env bash
# Pipeline SSL4EO scale300 completo en el cluster (01 local + 02-08).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/activate_mb_labels.sh"

export GRILLAS_ROOT="${GRILLAS_ROOT:-/home/lserey/mapbiomas_land/prod/samples}"
export MAPBIOMAS_LAND_ROOT="${MAPBIOMAS_LAND_ROOT:-/home/lserey/mapbiomas_land}"
export PYTHONPATH="${SCRIPT_DIR}/../scripts:${PYTHONPATH:-}"
cd "${SCRIPT_DIR}/.."

RUN_CHAR="${RUN_CHAR:-1}"

if [[ "${RUN_CHAR}" == "1" ]]; then
  bash "${SCRIPT_DIR}/run_local_characterization.sh"
fi

bash "${SCRIPT_DIR}/run_pipeline_02_08.sh"
