# Legacy / piloto

Scripts del experimento **por tile** + co-asociación (E2 2015).

El flujo oficial está en `scripts/10_*` … `12_*` (eco merged).

```bash
python scripts/legacy/07_cluster_tile_thresholds.py --tile 19KCQ
python scripts/legacy/08_summarize_tile_clusters.py --eco-id 2
python scripts/legacy/09_clusters_united_coassociation.py --eco-id 2

# array SLURM (acordar recursos antes de sbatch)
N=$(wc -l < results/E2/2015/01_inventory/tiles.txt)
sbatch --array=1-${N}%8 scripts/legacy/slurm/cluster_E2_per_tile.sbatch
```

Si quedan copias viejas en `scripts/07_*` … `09_*` o `scripts/slurm/cluster_E2_per_tile.sbatch`, bórralas; la versión canónica es esta carpeta.
