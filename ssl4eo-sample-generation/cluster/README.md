# Cluster leftraru — SSL4EO scale300

| Archivo | Descripción |
|---------|-------------|
| `activate_mb_labels.sh` | Activa conda `mb_labels` |
| `check_inputs.sh` | Verifica insumos y crea carpetas |
| `run_local_characterization.sh` | Paso **01** |
| `run_local_characterization.slurm` | SLURM paso 01 |
| `run_pipeline_02_08.sh` | Pasos **02–08** (4 selecciones + reportes) |
| `run_full_pipeline.sh` | **01** + **02–08** |
| `run_full_pipeline.slurm` | SLURM pipeline completo |

```bash
export GRILLAS_ROOT=/home/lserey/mapbiomas_land/prod/samples
export MAPBIOMAS_LAND_ROOT=/home/lserey/mapbiomas_land

sbatch cluster/run_full_pipeline.slurm
RUN_CHAR=0 sbatch cluster/run_full_pipeline.slurm   # omitir paso 01
```

Monitoreo: `squeue -u $USER` · logs en `/home/lserey/logs/ssl4eo_*.out`
