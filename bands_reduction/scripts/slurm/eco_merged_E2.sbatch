#!/bin/bash
#SBATCH -J br_E2_eco
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 1
#SBATCH --mem=32G
#SBATCH -t 04:00:00
#SBATCH -o /home/perazo/coverage/bands_reduction/results/E2/2015/eco_merged/logs/%x_%j.out
#SBATCH -e /home/perazo/coverage/bands_reduction/results/E2/2015/eco_merged/logs/%x_%j.err
#
# Official eco-merged pipeline for E2 (after inventory exists):
#   mkdir -p results/E2/2015/eco_merged/logs
#   sbatch scripts/slurm/eco_merged_E2.sbatch
#
# Env overrides: ECO_ID, YEAR, N_PIXELS, CORR_THRESHOLDS

set -euo pipefail
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

BR_ROOT="${BR_ROOT:-/home/perazo/coverage/bands_reduction}"
cd "$BR_ROOT"
PY="${PY:-/home/perazo/.conda/envs/mb_coverage/bin/python}"
ECO_ID="${ECO_ID:-2}"
YEAR="${YEAR:-2015}"
N_PIXELS="${N_PIXELS:-100000}"
CORR_THRESHOLDS="${CORR_THRESHOLDS:-0.95,0.90,0.85}"

mkdir -p "results/E${ECO_ID}/${YEAR}/eco_merged/logs"

echo "=== 10 sample eco merged ==="
"$PY" scripts/10_sample_eco_merged.py --eco-id "$ECO_ID" --year "$YEAR" --n-pixels "$N_PIXELS"

echo "=== 11 cluster thresholds ==="
"$PY" scripts/11_cluster_eco_thresholds.py \
  --eco-id "$ECO_ID" --year "$YEAR" --corr-thresholds "$CORR_THRESHOLDS" --save-corr

echo "=== 12 representatives ==="
"$PY" scripts/12_select_eco_representatives.py \
  --eco-id "$ECO_ID" --year "$YEAR" --corr-thresholds "$CORR_THRESHOLDS"

echo "DONE eco_id=${ECO_ID}"
