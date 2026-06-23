#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/activate_mb_labels.sh"

export GRILLAS_ROOT="${GRILLAS_ROOT:-/home/lserey/mapbiomas_land/prod/samples}"
export MAPBIOMAS_LAND_ROOT="${MAPBIOMAS_LAND_ROOT:-/home/lserey/mapbiomas_land}"
export PYTHONPATH="${SCRIPT_DIR}/../scripts:${PYTHONPATH:-}"
cd "${SCRIPT_DIR}/.."

mkdir -p \
  "${GRILLAS_ROOT}/final_samples" \
  "${GRILLAS_ROOT}/intermediate_files/grid_characterization" \
  "${GRILLAS_ROOT}/intermediate_files/review"

python - <<'PY'
from cluster_config import check_cluster_inputs, ECO_TIF, LANDCOVER_DIR, MGRS_GPKG
from project_paths import FINALES_DIR, GRID_CHARACTERIZATION_DIR, REVISION_DIR

missing = check_cluster_inputs(start_year=1999, end_year=2024)
print(f"GRILLAS_ROOT -> {FINALES_DIR.parent}")
print(f"Landcover:    {LANDCOVER_DIR}")
print(f"Eco:          {ECO_TIF}")
print(f"MGRS:         {MGRS_GPKG}")
print(f"Salida grilla: {GRID_CHARACTERIZATION_DIR}")
print(f"Salida final: {FINALES_DIR}")
print(f"Review:       {REVISION_DIR}")
if missing:
    print("\nFALTAN insumos:")
    for m in missing:
        print(f"  - {m}")
    raise SystemExit(1)
print("\nInsumos locales OK.")
PY
