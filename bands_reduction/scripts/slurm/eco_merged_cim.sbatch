#!/bin/bash
#SBATCH -J br_eco_cim
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 6
#SBATCH --mem=32G
#SBATCH -t 02:00:00
#SBATCH -o /home/perazo/coverage/bands_reduction/results/CIM2015/logs/eco_merged/%A_%a.out
#SBATCH -e /home/perazo/coverage/bands_reduction/results/CIM2015/logs/eco_merged/%A_%a.err
#
# Eco-merged pipeline (CIM 2015) — one ecorregion per array task.
# Requires inventory: scripts/06_inventory_eco_tiles.py --eco-id $ECO_ID
#
#   mkdir -p results/CIM2015/logs/eco_merged
#   sbatch --array=1-15%3 scripts/slurm/eco_merged_cim.sbatch
#   sbatch --export=ALL,ECO_ID=6 scripts/slurm/eco_merged_cim.sbatch

set -euo pipefail
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

BR_ROOT="${BR_ROOT:-/home/perazo/coverage/bands_reduction}"
cd "$BR_ROOT"
PY="${PY:-/home/perazo/.conda/envs/mb_coverage/bin/python}"
ECO_ID="${ECO_ID:-${SLURM_ARRAY_TASK_ID:?Set ECO_ID or use --array}}"
YEAR="${YEAR:-2015}"
N_PIXELS="${N_PIXELS:-100000}"
CORR_THRESHOLDS="${CORR_THRESHOLDS:-0.95,0.90,0.85}"

mkdir -p "results/CIM2015/E${ECO_ID}/${YEAR}/eco_merged/logs"

echo "=== br_eco_cim start $(date -Is) host=$(hostname) eco=${ECO_ID} workers=${WORKERS} ==="

echo "=== 10 sample eco merged (CIM) ==="
WORKERS="${WORKERS:-6}"
"$PY" scripts/10_sample_eco_merged.py \
  --eco-id "$ECO_ID" --year "$YEAR" --n-pixels "$N_PIXELS" --workers "$WORKERS"

echo "=== 11 cluster thresholds ==="
"$PY" scripts/11_cluster_eco_thresholds.py \
  --eco-id "$ECO_ID" --year "$YEAR" --corr-thresholds "$CORR_THRESHOLDS" --save-corr

echo "=== 12 representatives ==="
"$PY" scripts/12_select_eco_representatives.py \
  --eco-id "$ECO_ID" --year "$YEAR" --corr-thresholds "$CORR_THRESHOLDS"

echo "=== DONE eco_id=${ECO_ID} $(date -Is) ==="
