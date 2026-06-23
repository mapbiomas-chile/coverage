#!/bin/bash
#SBATCH -J ssl4eo-full
#SBATCH -p main
#SBATCH -n 1
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH --mail-user=lissette.cortes@uchile.cl
#SBATCH --mail-type=ALL
#SBATCH -t 48:00:00
#SBATCH -o /home/lserey/logs/ssl4eo_full_pipeline_%j.out
#SBATCH -e /home/lserey/logs/ssl4eo_full_pipeline_%j.err

# Pipeline SSL4EO scale300 completo en cluster (sin Earth Engine).
#   sbatch cluster/run_full_pipeline.slurm
#
# Solo pasos 02-08 (caracterizacion ya hecha):
#   RUN_CHAR=0 sbatch cluster/run_full_pipeline.slurm

set -eo pipefail

echo "Host: $(hostname)"
echo "Inicio: $(date)"
echo "Job ID: ${SLURM_JOB_ID:-local}"

bash /home/lserey/repositorio/coverage/ssl4eo-sample-generation/cluster/run_full_pipeline.sh

echo "Fin: $(date)"
