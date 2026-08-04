#!/bin/bash
#SBATCH -J br_E2_clust
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 1
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o /home/perazo/coverage/bands_reduction/results/E2/2015/02_clusters_by_tile/logs/%x_%A_%a.out
#SBATCH -e /home/perazo/coverage/bands_reduction/results/E2/2015/02_clusters_by_tile/logs/%x_%A_%a.err
#
# Usage (from bands_reduction/) — acordado: largemem, 1 CPU, 16G, %8
#   mkdir -p results/E2/2015/02_clusters_by_tile/logs
#   # after inventory:
#   N=$(wc -l < results/E2/2015/01_inventory/tiles.txt)
#   sbatch --array=1-${N}%8 scripts/legacy/slurm/cluster_E2_per_tile.sbatch
#
# Optional env overrides:
#   OUT_ROOT, TILE_LIST, N_PIXELS, CORR_THRESHOLDS, ECO_ID, YEAR

set -euo pipefail

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"

BR_ROOT="${BR_ROOT:-/home/perazo/coverage/bands_reduction}"
cd "$BR_ROOT"

PY="${PY:-/home/perazo/.conda/envs/mb_coverage/bin/python}"
ECO_ID="${ECO_ID:-2}"
YEAR="${YEAR:-2015}"
STAGE="$BR_ROOT/results/E${ECO_ID}/${YEAR}/02_clusters_by_tile"
TILE_LIST="${TILE_LIST:-$BR_ROOT/results/E${ECO_ID}/${YEAR}/01_inventory/tiles.txt}"
OUT_ROOT="${OUT_ROOT:-$STAGE/tiles}"
N_PIXELS="${N_PIXELS:-30000}"
CORR_THRESHOLDS="${CORR_THRESHOLDS:-0.95,0.90,0.85}"

mkdir -p "$STAGE/logs" "$OUT_ROOT"

TILE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$TILE_LIST")
if [[ -z "${TILE}" ]]; then
  echo "Empty tile for SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID}" >&2
  exit 1
fi

echo "host=$(hostname) task=${SLURM_ARRAY_TASK_ID} tile=${TILE}"
echo "out_root=${OUT_ROOT}"

"$PY" scripts/legacy/07_cluster_tile_thresholds.py \
  --config configs/global.yaml \
  --tile "$TILE" \
  --eco-id "$ECO_ID" \
  --year "$YEAR" \
  --n-pixels "$N_PIXELS" \
  --corr-thresholds "$CORR_THRESHOLDS" \
  --out-root "$OUT_ROOT"

echo "DONE tile=${TILE}"
