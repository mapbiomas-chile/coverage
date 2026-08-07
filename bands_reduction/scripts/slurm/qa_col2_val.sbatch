#!/bin/bash
#SBATCH -J br_qa_val
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o /home/perazo/coverage/bands_reduction/results/QA/logs/%x_%j.out
#SBATCH -e /home/perazo/coverage/bands_reduction/results/QA/logs/%x_%j.err
#
# Col2 val hold-out QA (E2 + E3):
#   sbatch scripts/slurm/qa_col2_val.sbatch

set -euo pipefail
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

BR_ROOT="${BR_ROOT:-/home/perazo/coverage/bands_reduction}"
cd "$BR_ROOT"
PY="${PY:-/home/perazo/.conda/envs/mb_coverage/bin/python}"

mkdir -p results/QA/logs results/QA/samples

echo "=== Extract Col2 val E2+E3 $(date -Is) ==="
"$PY" scripts/25_extract_col2_samples.py --layer val --eco-id 2 --eco-id 3

echo "=== Col2 val QA ==="
for ECO_ID in 2 3; do
  "$PY" scripts/26_qa_col2_val.py --eco-id "$ECO_ID" --n-jobs 4
done

echo "=== Done $(date -Is) ==="
