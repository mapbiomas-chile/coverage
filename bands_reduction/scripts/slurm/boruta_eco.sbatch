#!/bin/bash
#SBATCH -J br_boruta
#SBATCH -p main
#SBATCH -n 1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 12:00:00
#SBATCH -o /home/perazo/coverage/bands_reduction/results/Boruta_PE/logs/%x_%A_%a.out
#SBATCH -e /home/perazo/coverage/bands_reduction/results/Boruta_PE/logs/%x_%A_%a.err
#
# Boruta pilot (one eco × input mode per job):
#   mkdir -p results/Boruta_PE/logs
#   sbatch scripts/slurm/boruta_pilot_E2E3.sbatch   # E2+E3 array on NLHPC
#
# Env: ECO_ID, INPUT_BANDS (all184|reps095), MAX_SAMPLES (optional)

set -euo pipefail
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

BR_ROOT="${BR_ROOT:-/home/perazo/coverage/bands_reduction}"
cd "$BR_ROOT"
PY="${PY:-/home/perazo/.conda/envs/mb_coverage/bin/python}"
ECO_ID="${ECO_ID:-2}"
INPUT_BANDS="${INPUT_BANDS:-reps095}"
MAX_SAMPLES="${MAX_SAMPLES:-}"

mkdir -p results/Boruta_PE/logs

CMD=(
  "$PY" scripts/22_boruta_eco.py
  --eco-id "$ECO_ID"
  --input-bands "$INPUT_BANDS"
  --sample-set stratified
  --n-jobs 8
)

if [[ -n "$MAX_SAMPLES" ]]; then
  CMD+=(--max-samples "$MAX_SAMPLES")
fi

echo "Running: ${CMD[*]}"
"${CMD[@]}"
echo "DONE eco_id=${ECO_ID} input=${INPUT_BANDS}"
