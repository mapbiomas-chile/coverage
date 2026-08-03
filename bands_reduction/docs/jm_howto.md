# feat/fs_me — JM (etapa 3) sobre muestras PE

## Flujo de prueba (tile 19KCQ, ecorregión 2)

Las muestras PE (`E2_19KCQ_2015_n50000.npz`) traen `X/rows/cols` **sin** `y`.
Primero se adjuntan etiquetas desde MapBiomas LULC 2015; luego corre JM.

```bash
cd bands_reduction

# 1) Band-list full (184) — o usa representatives del clustering de PE
python scripts/02_export_band_list.py \
  --tile 19KCQ --ecoregion 2 \
  --out /tmp/band_list_full_19KCQ.json

python scripts/02_export_band_list.py \
  --tile 19KCQ --ecoregion 2 \
  --from-representatives /home/lserey/mapbiomas_land/tmp/bands_reduction_pe/clusters/E2_19KCQ_2015_n50000_d0p10/representatives/filtered_no_const_hall_seasonal_r875/representatives.json \
  --out /tmp/band_list_cluster_19KCQ.json

# 2) Adjuntar y (proxy LULC). Usar --max-samples para smoke test.
python scripts/03_attach_labels.py \
  --tile 19KCQ \
  --out /tmp/E2_19KCQ_2015_labeled.npz \
  --max-samples 5000

# 3) JM sobre full o sobre clustering (mismo script)
python scripts/04_run_jm.py \
  --samples /tmp/E2_19KCQ_2015_labeled.npz \
  --band-list /tmp/band_list_full_19KCQ.json \
  --out-dir /tmp/jm_full_E2_19KCQ \
  --top-k 40

python scripts/04_run_jm.py \
  --samples /tmp/E2_19KCQ_2015_labeled.npz \
  --band-list /tmp/band_list_cluster_19KCQ.json \
  --out-dir /tmp/jm_cluster_E2_19KCQ \
  --top-k 40
```

Salidas (fuera de git): `jm_ranking.csv`, `band_list_jm.json`, `jm_summary.json`.
