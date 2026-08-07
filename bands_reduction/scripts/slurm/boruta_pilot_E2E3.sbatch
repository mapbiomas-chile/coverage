#!/bin/bash
#SBATCH -J br_boruta_pe
#SBATCH -p main
#SBATCH -n 1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 12:00:00
#SBATCH --array=0-3
#SBATCH -o /home/perazo/coverage/bands_reduction/results/Boruta_PE/logs/%x_%A_%a.out
#SBATCH -e /home/perazo/coverage/bands_reduction/results/Boruta_PE/logs/%x_%A_%a.err
#
# Boruta pilot E2/E3 on NLHPC (stratified Col2 train, full sample count):
#   mkdir -p results/Boruta_PE/logs
#   sbatch scripts/slurm/boruta_pilot_E2E3.sbatch
#
# Array map:
#   0 = E2 reps095
#   1 = E3 reps095
#   2 = E2 all184
#   3 = E3 all184

set -euo pipefail
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

BR_ROOT="${BR_ROOT:-/home/perazo/coverage/bands_reduction}"
cd "$BR_ROOT"
PY="${PY:-/home/perazo/.conda/envs/mb_coverage/bin/python}"

mkdir -p results/Boruta_PE/logs

case "${SLURM_ARRAY_TASK_ID}" in
  0) ECO_ID=2; INPUT_BANDS=reps095 ;;
  1) ECO_ID=3; INPUT_BANDS=reps095 ;;
  2) ECO_ID=2; INPUT_BANDS=all184 ;;
  3) ECO_ID=3; INPUT_BANDS=all184 ;;
  *)
    echo "Unknown SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID}"
    exit 1
    ;;
esac

echo "=== NLHPC Boruta pilot ==="
echo "host=$(hostname) job=${SLURM_JOB_ID} array=${SLURM_ARRAY_TASK_ID}"
echo "eco_id=${ECO_ID} input_bands=${INPUT_BANDS}"
echo "start=$(date -Is)"

"$PY" scripts/22_boruta_eco.py \
  --eco-id "$ECO_ID" \
  --input-bands "$INPUT_BANDS" \
  --sample-set stratified \
  --n-jobs 8

echo "end=$(date -Is)"
echo "DONE eco_id=${ECO_ID} input=${INPUT_BANDS}"
