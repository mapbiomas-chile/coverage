# Leftraru cluster — SSL4EO scale300

| File | Description |
|------|-------------|
| `activate_mb_labels.sh` | Activates the `mb_labels` conda environment |
| `check_inputs.sh` | Checks inputs and creates folders |
| `run_local_characterization.sh` | Step **01** |
| `run_local_characterization.slurm` | SLURM job for step 01 |
| `run_pipeline_02_08.sh` | Steps **02–08** (4 selections + reports) |
| `run_full_pipeline.sh` | **01** + **02–08** |
| `run_full_pipeline.slurm` | SLURM job for the full pipeline |

```bash
export GRILLAS_ROOT=/home/lserey/mapbiomas_land/prod/samples
export MAPBIOMAS_LAND_ROOT=/home/lserey/mapbiomas_land

sbatch cluster/run_full_pipeline.slurm
RUN_CHAR=0 sbatch cluster/run_full_pipeline.slurm   # skip step 01
```

Monitoring: `squeue -u $USER` · logs in `/home/lserey/logs/ssl4eo_*.out`