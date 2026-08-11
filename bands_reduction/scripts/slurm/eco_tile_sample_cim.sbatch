#!/bin/bash
#SBATCH -J br_eco_tile
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 1
#SBATCH --mem=16G
#SBATCH -t 02:00:00
#SBATCH -o /home/perazo/coverage/bands_reduction/results/CIM2015/logs/eco_tiles/%A_%a.out
#SBATCH -e /home/perazo/coverage/bands_reduction/results/CIM2015/logs/eco_tiles/%A_%a.err
#
# One tile per array task (CIM 2015). Requires inventory tiles.txt.
#
#   mkdir -p results/CIM2015/logs/eco_tiles
#   ECO_ID=6
#   N=$(wc -l < results/CIM2015/E${ECO_ID}/2015/01_inventory/tiles.txt)
#   sbatch --array=1-${N}%4 --export=ALL,ECO_ID=${ECO_ID} scripts/slurm/eco_tile_sample_cim.sbatch
#
# After array completes, run eco_merged_finish_cim.sbatch with dependency.

set -euo pipefail
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

BR_ROOT="${BR_ROOT:-/home/perazo/coverage/bands_reduction}"
cd "$BR_ROOT"
PY="${PY:-/home/perazo/.conda/envs/mb_coverage/bin/python}"
ECO_ID="${ECO_ID:?Set ECO_ID}"
YEAR="${YEAR:-2015}"
N_PIXELS="${N_PIXELS:-100000}"

TILE_LIST="${TILE_LIST:-results/CIM2015/E${ECO_ID}/${YEAR}/01_inventory/tiles.txt}"
TILE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$TILE_LIST")
if [[ -z "${TILE}" ]]; then
  echo "Empty tile for SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID}" >&2
  exit 1
fi

mkdir -p "results/CIM2015/E${ECO_ID}/${YEAR}/eco_merged/tiles"

echo "=== br_eco_tile start $(date -Is) host=$(hostname) eco=${ECO_ID} tile=${TILE} ==="

"$PY" scripts/10_sample_eco_tile.py \
  --eco-id "$ECO_ID" \
  --year "$YEAR" \
  --tile "$TILE" \
  --max-pixels "$N_PIXELS"

echo "=== DONE eco=${ECO_ID} tile=${TILE} $(date -Is) ==="
