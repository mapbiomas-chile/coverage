# Boruta — etapa 3 del pipeline (verificación)

Wrapper supervisado que **confirma** bandas relevantes frente a features sombra (azar).
Va **después** de clustering / JM. No entrena el mapa LULC final.

## Script

```bash
cd bands_reduction

# Ejemplo: Boruta sobre representantes del clustering Chile (|r|≥0.9)
python scripts/09_run_boruta.py \
  --samples /home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_all/samples/chile_train_184.npz \
  --band-list /home/lserey/mapbiomas_land/tmp/JM_test_ME/all_chile_184bands/clustering/band_list_clustering.json \
  --out-dir /home/lserey/mapbiomas_land/tmp/JM_test_ME/boruta_chile_from_clustering \
  --n-jobs 4 \
  --max-iter 50

# Ejemplo: Boruta sobre las 184 (más caro; mejor sobre candidatos JM/cluster)
python scripts/09_run_boruta.py \
  --samples /home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_all/samples/chile_train_184.npz \
  --band-list /home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_all/band_lists/band_list_full_184.json \
  --out-dir /home/lserey/mapbiomas_land/tmp/JM_test_ME/boruta_chile_full184 \
  --n-jobs 4
```

## Salidas

| Archivo | Contenido |
|---------|-----------|
| `boruta_decisions.csv` | confirmed / tentative / rejected + hit_rate |
| `band_list_boruta.json` | set confirmado (contrato compartido) |
| `boruta_summary.json` | conteos y parámetros |

## Cadena sugerida

```
184 bandas
  → clustering (|r|≥0.9)     [script 08 en feat/fs_me]
  → JM refine                [04 / 06 / 07]
  → Boruta verify            [09]  ← este script
  → consolidación ecorregiones
```

## Parámetros (`configs/global.yaml` → `boruta:`)

- `max_iter` (default 50)
- `n_estimators` (default 200)
- `perc` (default 100 = umbral = max importancia sombra)
- `alpha` (default 0.05)

Usa `--include-tentative` si quieres conservar también las bandas aún indecisas.
