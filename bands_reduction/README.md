# bands_reduction

Reducción de bandas (184B) por ecorregión MapBiomas Chile, con **mínima pérdida de información** para clasificación LULC (**2015**, **15 ecorregiones**).

> **Estado:** en construcción. Los parámetros marcados con `⚙️ AJUSTAR` deben confirmarse antes de correr en producción.

Metodología detallada: [`docs/metodologia.md`](docs/metodologia.md). Hoja de ruta: [`docs/roadmap.md`](docs/roadmap.md).

## Pipeline oficial (eco unificada)

```
inventario tiles ∩ eco
    → muestreo merged (100k, balanceado por tile)
    → |r| + clustering (0.95 / 0.90 / 0.85)
    → representante central por cluster
    → rescate de familias sin cobertura
    → lista de bandas por ecorregión × umbral
```

### Requisitos

- Python env con: `numpy`, `scipy`, `pandas`, `rasterio`, `pyyaml`, `tqdm`, `geopandas` (solo inventario)
- Mosaicos 184B y TIF de ecorregiones (rutas en config)

### Config

1. Revisar `configs/global.yaml` (parámetros científicos).
2. Copiar `configs/local.yaml.example` → `configs/local.yaml` y poner rutas de la máquina  
   (`local.yaml` está en `.gitignore`).

Parámetros clave:

| Clave | Valor acordado |
|-------|----------------|
| `sampling.n_pixels_eco` | 100000 |
| `sampling.balance` | `equal_per_tile` |
| `clustering.corr_thresholds` | `[0.95, 0.90, 0.85]` |
| `representatives.method` | `central_mean_abs_r` |
| `representatives.family_rescue` | `true` |

### Cómo correr (E2)

```bash
cd bands_reduction
# opcional: conda activate mb_coverage

python scripts/06_inventory_eco_tiles.py --eco-id 2
python scripts/10_sample_eco_merged.py --eco-id 2
python scripts/11_cluster_eco_thresholds.py --eco-id 2
python scripts/12_select_eco_representatives.py --eco-id 2
```

NLHPC (después del inventario):

```bash
mkdir -p results/E2/2015/eco_merged/logs
sbatch scripts/slurm/eco_merged_E2.sbatch
```

### Outputs

```
results/E{id}/{year}/
  01_inventory/tiles.csv
  eco_merged/
    sample.npz
    sample_meta.json
    0.95|0.90|0.85/
      clusters.json
      band_cluster_assignment.csv
      representatives/
        representatives.json          # índices finales
        representatives_named.csv     # nombres + familia + source
        family_rescue.csv
        family_coverage.csv
```

`results/` no se versiona.

### Scripts legacy (piloto por tile)

En `scripts/legacy/`:

- `07_cluster_tile_thresholds.py` — clusters por tile
- `08_summarize_tile_clusters.py`
- `09_clusters_united_coassociation.py` — consenso co-asociación
- `slurm/cluster_E2_per_tile.sbatch`

Útiles para sensibilidad espacial; **no** son el flujo de producción.

---

## Cadena semi-supervisada (JM / Boruta / consolidación)

Tras el clustering no supervisado, el flujo ME añade refinamiento JM, Boruta y consolidación entre ecorregiones (intersección / unión). Detalle en [`docs/metodologia.md`](docs/metodologia.md).

```bash
python scripts/01_inspect_mosaic.py --config configs/global.yaml --ecoregion configs/ecoregions/eco_02_desierto.yaml
python scripts/08_cluster_and_jm_chile.py
python scripts/09_run_boruta.py
# consolidación entre ecorregiones cuando esté disponible
```

---

## Estructura `src/`

- `src/io` — mosaicos, máscara eco, muestreo (tile y merged), band lists, labels
- `src/evaluation` — `|r|`, MI, JM/Bhattacharyya, RF, métricas
- `src/selection` — clustering corr, representantes, family rescue, JM, Boruta, coasoc (legacy)
- `src/pipeline` — orquestación
- `src/utils` — logging, config, helpers
