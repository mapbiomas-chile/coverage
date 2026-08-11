#!/bin/bash
#SBATCH -J br_col2_tr
#SBATCH -p largemem
#SBATCH -n 1
#SBATCH -c 1
#SBATCH --mem=16G
#SBATCH -t 03:00:00
#SBATCH -o /home/perazo/coverage/bands_reduction/results/CIM2015/logs/col2_extract/%x_%j.out
#SBATCH -e /home/perazo/coverage/bands_reduction/results/CIM2015/logs/col2_extract/%x_%j.err
#
# Col2 train extraction @ 184 bands from CIM mosaics (all 15 ecorregions).
#
#   mkdir -p results/CIM2015/logs/col2_extract results/CIM2015/QA/samples
#   sbatch scripts/slurm/col2_extract_cim.sbatch

set -euo pipefail
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"

BR_ROOT="${BR_ROOT:-/home/perazo/coverage/bands_reduction}"
cd "$BR_ROOT"
PY="${PY:-/home/perazo/.conda/envs/mb_coverage/bin/python}"

mkdir -p results/CIM2015/logs/col2_extract results/CIM2015/QA/samples

echo "=== Col2 train extract CIM start $(date -Is) host=$(hostname) ==="

ECO_ARGS=()
for i in $(seq 1 15); do
  ECO_ARGS+=(--eco-id "$i")
done

"$PY" scripts/25_extract_col2_samples.py \
  --layer train \
  --out-dir results/CIM2015/QA/samples \
  "${ECO_ARGS[@]}"

echo "=== Col2 train extract DONE $(date -Is) ==="
