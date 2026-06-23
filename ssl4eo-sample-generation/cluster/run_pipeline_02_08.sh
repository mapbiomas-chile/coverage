#!/usr/bin/env bash
# Pasos 02-08 del pipeline SSL4EO scale300 (post-caracterizacion local).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/activate_mb_labels.sh"
cd "${SCRIPT_DIR}/.."

export GRILLAS_ROOT="${GRILLAS_ROOT:-/home/lserey/mapbiomas_land/prod/samples}"
export PYTHONPATH="${SCRIPT_DIR}/../scripts:${PYTHONPATH:-}"

GRID="${GRILLAS_ROOT}/intermediate_files/grid_characterization"
FINAL="${GRILLAS_ROOT}/final_samples"
REVIEW="${GRILLAS_ROOT}/intermediate_files/review"

mkdir -p "${GRID}" "${FINAL}" "${REVIEW}"

suffix="_n3"
PLAN_FILES=()

run_selection() {
  local utm="$1"
  local grid_tag="$2"
  local input_flag="$3"
  local zip="${GRID}/grilla_ssl4eo_muestras_${grid_tag}_UTM${utm}_scale300${suffix}.zip"
  local out_dir="${FINAL}/UTM${utm}/${grid_tag}"
  local stem="grilla_ssl4eo_muestras_${grid_tag}_UTM${utm}_scale300"
  local sel_csv="${out_dir}/seleccion_${stem}.csv"
  local sel_geojson="${out_dir}/seleccion_${stem}.geojson"
  local plan_csv="${REVIEW}/plan_revision_UTM${utm}_${grid_tag}_scale300.csv"

  if [[ ! -f "${zip}" ]]; then
    echo "ERROR: falta ZIP ${zip}"
    exit 1
  fi

  echo "=== 02 seleccion UTM${utm} ${grid_tag} ==="
  python scripts/02_rectangle_selection.py \
    "${input_flag}" "${zip}"

  echo "=== 03 taxonomia UTM${utm} ${grid_tag} ==="
  python scripts/03_annotate_grid_taxonomy.py -i "${sel_csv}"

  echo "=== 07 plan revision UTM${utm} ${grid_tag} ==="
  python scripts/07_generate_rectangle_review_plan.py \
    -i "${sel_geojson}" \
    -o "${plan_csv}"

  PLAN_FILES+=("${plan_csv}")
}

run_selection 18 homogeneo_2x2 --homogeneo
run_selection 18 mixto_3x3 --mixto
run_selection 19 homogeneo_2x2 --homogeneo
run_selection 19 mixto_3x3 --mixto

echo "=== 04 revision ==="
python scripts/04_rectangle_selection_review.py --utm 18 19

echo "=== 05 balance audit ==="
python scripts/05_balance_audit.py

echo "=== 08 plan nacional ==="
python scripts/08_consolidate_national_review_plan.py \
  --input "${PLAN_FILES[@]}" \
  --out-dir "${REVIEW}"

echo "=== 06 dashboard HTML ==="
python scripts/06_visualize_reports.py \
  --export-html "${REVIEW}/revision_dashboard.html"

echo "Pipeline 02-08 completado en ${GRILLAS_ROOT}"
