#!/bin/bash
#SBATCH -J br_eco_fin
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 1
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o /home/perazo/coverage/bands_reduction/results/CIM2015/logs/eco_merged/finish_%A_%j.out
#SBATCH -e /home/perazo/coverage/bands_reduction/results/CIM2015/logs/eco_merged/finish_%A_%j.err
#
# Merge tile partials + cluster + representatives for one ecorregion.
#
#   sbatch --export=ALL,ECO_ID=6 scripts/slurm/eco_merged_finish_cim.sbatch
#   sbatch --dependency=afterok:ARRAY_JOB_ID --export=ALL,ECO_ID=6 \
#     scripts/slurm/eco_merged_finish_cim.sbatch

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
CORR_THRESHOLDS="${CORR_THRESHOLDS:-0.95,0.90,0.85}"
TILE_LIST="${TILE_LIST:-results/CIM2015/E${ECO_ID}/${YEAR}/01_inventory/tiles.txt}"

echo "=== br_eco_fin start $(date -Is) host=$(hostname) eco=${ECO_ID} ==="

echo "=== 10 merge eco samples ==="
"$PY" scripts/10_merge_eco_samples.py \
  --eco-id "$ECO_ID" \
  --year "$YEAR" \
  --n-pixels "$N_PIXELS" \
  --tiles-list "$TILE_LIST"

echo "=== 11 cluster thresholds ==="
"$PY" scripts/11_cluster_eco_thresholds.py \
  --eco-id "$ECO_ID" --year "$YEAR" --corr-thresholds "$CORR_THRESHOLDS" --save-corr

echo "=== 12 representatives ==="
"$PY" scripts/12_select_eco_representatives.py \
  --eco-id "$ECO_ID" --year "$YEAR" --corr-thresholds "$CORR_THRESHOLDS"

echo "=== DONE eco_id=${ECO_ID} $(date -Is) ==="
