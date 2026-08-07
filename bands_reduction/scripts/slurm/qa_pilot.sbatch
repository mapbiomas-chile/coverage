#!/bin/bash
#SBATCH -J br_qa_pe
#SBATCH -p main
#SBATCH -n 1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 04:00:00
#SBATCH -o /home/perazo/coverage/bands_reduction/results/QA/logs/%x_%j.out
#SBATCH -e /home/perazo/coverage/bands_reduction/results/QA/logs/%x_%j.err
#
# QA RF-CV pilot E2 + E3:
#   mkdir -p results/QA/logs
#   sbatch scripts/slurm/qa_pilot.sbatch

set -euo pipefail
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

BR_ROOT="${BR_ROOT:-/home/perazo/coverage/bands_reduction}"
cd "$BR_ROOT"
PY="${PY:-/home/perazo/.conda/envs/mb_coverage/bin/python}"

mkdir -p results/QA/logs

echo "=== QA pilot start $(date -Is) host=$(hostname) ==="

for ECO_ID in 2 3; do
  echo "--- eco_id=${ECO_ID} ---"
  "$PY" scripts/24_qa_rf_cv.py --eco-id "$ECO_ID" --n-jobs 8
done

echo "=== QA pilot done $(date -Is) ==="
