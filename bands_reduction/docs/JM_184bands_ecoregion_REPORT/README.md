# JM_184bands_ecoregion_REPORT

**Jeffries-Matusita por ecorregión — 184 bandas (sin clustering)**

| Campo | Valor |
| --- | --- |
| Rama / scripts | `feat/fs_me` · `scripts/07_run_jm_by_ecoregion.py` |
| Entrada | Matriz Chile train `184_bands_JM/samples/chile_train_184.npz` |
| Muestras | Col2 `train` por ecorregión |
| Bandas | **184 full** (`source=full`), **sin clustering** |
| Método | JM univariado (mean pairwise); **no entrena modelo** |
| exclude_classes | **[33, 34]** (agua, hielo/nieve) |
| Ecorregiones | 15 / 15 OK |
| Resultados crudos | `/home/lserey/mapbiomas_land/tmp/JM_test_ME/184bands_ecorregion/` |
| Previo (todas las clases) | `.../184bands_ecorregion_all_classes/` |

---

## 1. Overview

![Top1 JM by eco](figures/overview_top1_jm_by_eco.png)

![N samples by eco](figures/overview_nsamples_by_eco.png)

### Resumen por ecorregión

| eco_id | eco_name | n_samples | n_classes | top1_band | top1_mean_jm | status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | E1_Puna_seca_andina | 296 | 10 | gv_min | 1.3160 | OK |
| 2 | E2_Desierto_Atacama | 361 | 11 | gv_median | 1.3412 | OK |
| 3 | E3_Matorral_norte_1 | 117 | 10 | npv_min | 1.6023 | OK |
| 4 | E4_Estepa_andina | 331 | 11 | npv_min | 1.3696 | OK |
| 5 | E5_Matorral_norte_2 | 396 | 12 | cloud_min | 1.1634 | OK |
| 6 | E6_Andes_norte | 183 | 10 | elevation | 1.2018 | OK |
| 7 | E7_Andes_central | 627 | 13 | npv_min | 1.1613 | OK |
| 8 | E8_Matorral_sur | 760 | 13 | npv_min | 1.1667 | OK |
| 9 | E9_Costa_Norte | 1070 | 12 | cai_median | 1.1809 | OK |
| 10 | E10_Andes_Sur | 430 | 13 | hallheigth_amp | 1.2305 | OK |
| 11 | E11_Costa_Sur_1 | 570 | 11 | ndvi_median | 1.2528 | OK |
| 12 | E12_Costa_Sur_2 | 103 | 7 | gv_median | 1.6140 | OK |
| 13 | E13_Andes_Sur_Costa | 70 | 7 | sefi_median_wet | 1.9995 | OK |
| 14 | E14_Estepa_patagonica | 286 | 12 | ndvi_median | 1.2648 | OK |
| 15 | E15_Bosque_subpolar | 396 | 11 | gvs_max | 1.2229 | OK |

CSV: [`data/ecoregion_overview.csv`](data/ecoregion_overview.csv)

---

## 2. Top 15 JM por ecorregión

- ![E01](figures/E01_jm_top15.png) — **E1** E1_Puna_seca_andina (n=296, top1=`gv_min`)
- ![E02](figures/E02_jm_top15.png) — **E2** E2_Desierto_Atacama (n=361, top1=`gv_median`)
- ![E03](figures/E03_jm_top15.png) — **E3** E3_Matorral_norte_1 (n=117, top1=`npv_min`)
- ![E04](figures/E04_jm_top15.png) — **E4** E4_Estepa_andina (n=331, top1=`npv_min`)
- ![E05](figures/E05_jm_top15.png) — **E5** E5_Matorral_norte_2 (n=396, top1=`cloud_min`)
- ![E06](figures/E06_jm_top15.png) — **E6** E6_Andes_norte (n=183, top1=`elevation`)
- ![E07](figures/E07_jm_top15.png) — **E7** E7_Andes_central (n=627, top1=`npv_min`)
- ![E08](figures/E08_jm_top15.png) — **E8** E8_Matorral_sur (n=760, top1=`npv_min`)
- ![E09](figures/E09_jm_top15.png) — **E9** E9_Costa_Norte (n=1070, top1=`cai_median`)
- ![E10](figures/E10_jm_top15.png) — **E10** E10_Andes_Sur (n=430, top1=`hallheigth_amp`)
- ![E11](figures/E11_jm_top15.png) — **E11** E11_Costa_Sur_1 (n=570, top1=`ndvi_median`)
- ![E12](figures/E12_jm_top15.png) — **E12** E12_Costa_Sur_2 (n=103, top1=`gv_median`)
- ![E13](figures/E13_jm_top15.png) — **E13** E13_Andes_Sur_Costa (n=70, top1=`sefi_median_wet`)
- ![E14](figures/E14_jm_top15.png) — **E14** E14_Estepa_patagonica (n=286, top1=`ndvi_median`)
- ![E15](figures/E15_jm_top15.png) — **E15** E15_Bosque_subpolar (n=396, top1=`gvs_max`)

Rankings completos (184 bandas) en `data/by_ecoregion/E*/jm_ranking.csv`.

---

## 3. Cómo reproducir

```bash
cd bands_reduction
python scripts/07_run_jm_by_ecoregion.py \
  --out-dir /home/lserey/mapbiomas_land/tmp/JM_test_ME/184bands_ecorregion \
  --exclude-classes 33 34
```

---

## 4. Archivos

- `data/ecoregion_overview.csv` / `.json`
- `data/by_ecoregion/E*/jm_ranking.csv`, `jm_summary.json`
- `figures/E*_jm_top15.png`, `overview_*.png`
