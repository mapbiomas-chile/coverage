#!/bin/bash
#SBATCH -J ssl4eo-local-char
#SBATCH -p main
#SBATCH -n 1
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH --mail-user=lissette.cortes@uchile.cl
#SBATCH --mail-type=ALL
#SBATCH -t 24:00:00
#SBATCH -o /home/lserey/logs/ssl4eo_local_characterization_%j.out
#SBATCH -e /home/lserey/logs/ssl4eo_local_characterization_%j.err

set -eo pipefail

echo "Host: $(hostname)"
echo "Inicio: $(date)"
echo "Job ID: ${SLURM_JOB_ID:-local}"

bash /home/lserey/repositorio/coverage/ssl4eo-sample-generation/cluster/run_local_characterization.sh

echo "Fin: $(date)"
