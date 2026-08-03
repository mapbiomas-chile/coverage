# JM_184bands_ecoregion_REPORT

**Jeffries-Matusita por ecorregión — 184 bandas (sin clustering)**

| Campo | Valor |
| --- | --- |
| Rama / scripts | `feat/fs_me` · `scripts/07_run_jm_by_ecoregion.py` |
| Entrada | Matriz Chile train `184_bands_all/samples/chile_train_184.npz` |
| Muestras | Col2 `train` por ecorregión |
| Bandas | **184 full** (`source=full`), **sin clustering** |
| Método | JM univariado (mean pairwise); **no entrena modelo** |
| Ecorregiones | 15 / 15 OK |
| Resultados crudos | `/home/lserey/mapbiomas_land/tmp/JM_test_ME/184bands_ecorregion/` |

---

## 1. Overview

![Top1 JM by eco](figures/overview_top1_jm_by_eco.png)

![N samples by eco](figures/overview_nsamples_by_eco.png)

### Resumen por ecorregión

| eco_id | eco_name | n_samples | n_classes | top1_band | top1_mean_jm | status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | E1_Puna_seca_andina | 349 | 12 | ndvi_median_dry | 1.3416 | OK |
| 2 | E2_Desierto_Atacama | 362 | 12 | gv_median | 1.3412 | OK |
| 3 | E3_Matorral_norte_1 | 117 | 10 | npv_min | 1.6023 | OK |
| 4 | E4_Estepa_andina | 398 | 13 | npv_min | 1.4007 | OK |
| 5 | E5_Matorral_norte_2 | 439 | 13 | ndvi_median | 1.1335 | OK |
| 6 | E6_Andes_norte | 256 | 12 | gcvi_median | 1.2598 | OK |
| 7 | E7_Andes_central | 790 | 15 | gcvi_median | 1.2943 | OK |
| 8 | E8_Matorral_sur | 830 | 14 | gcvi_median | 1.2083 | OK |
| 9 | E9_Costa_Norte | 1205 | 13 | gcvi_median | 1.2605 | OK |
| 10 | E10_Andes_Sur | 685 | 15 | gcvi_median | 1.3297 | OK |
| 11 | E11_Costa_Sur_1 | 712 | 12 | gcvi_median | 1.3619 | OK |
| 12 | E12_Costa_Sur_2 | 118 | 8 | ndfi_median_dry | 1.7216 | OK |
| 13 | E13_Andes_Sur_Costa | 95 | 9 | gvs_median_wet | 1.9998 | OK |
| 14 | E14_Estepa_patagonica | 406 | 14 | gcvi_median | 1.4309 | OK |
| 15 | E15_Bosque_subpolar | 607 | 13 | red_median | 1.3188 | OK |

CSV: [`data/ecoregion_overview.csv`](data/ecoregion_overview.csv)

---

## 2. Top 15 JM por ecorregión

- ![E01](figures/E01_jm_top15.png) — **E1** E1_Puna_seca_andina (n=349, top1=`ndvi_median_dry`)
- ![E02](figures/E02_jm_top15.png) — **E2** E2_Desierto_Atacama (n=362, top1=`gv_median`)
- ![E03](figures/E03_jm_top15.png) — **E3** E3_Matorral_norte_1 (n=117, top1=`npv_min`)
- ![E04](figures/E04_jm_top15.png) — **E4** E4_Estepa_andina (n=398, top1=`npv_min`)
- ![E05](figures/E05_jm_top15.png) — **E5** E5_Matorral_norte_2 (n=439, top1=`ndvi_median`)
- ![E06](figures/E06_jm_top15.png) — **E6** E6_Andes_norte (n=256, top1=`gcvi_median`)
- ![E07](figures/E07_jm_top15.png) — **E7** E7_Andes_central (n=790, top1=`gcvi_median`)
- ![E08](figures/E08_jm_top15.png) — **E8** E8_Matorral_sur (n=830, top1=`gcvi_median`)
- ![E09](figures/E09_jm_top15.png) — **E9** E9_Costa_Norte (n=1205, top1=`gcvi_median`)
- ![E10](figures/E10_jm_top15.png) — **E10** E10_Andes_Sur (n=685, top1=`gcvi_median`)
- ![E11](figures/E11_jm_top15.png) — **E11** E11_Costa_Sur_1 (n=712, top1=`gcvi_median`)
- ![E12](figures/E12_jm_top15.png) — **E12** E12_Costa_Sur_2 (n=118, top1=`ndfi_median_dry`)
- ![E13](figures/E13_jm_top15.png) — **E13** E13_Andes_Sur_Costa (n=95, top1=`gvs_median_wet`)
- ![E14](figures/E14_jm_top15.png) — **E14** E14_Estepa_patagonica (n=406, top1=`gcvi_median`)
- ![E15](figures/E15_jm_top15.png) — **E15** E15_Bosque_subpolar (n=607, top1=`red_median`)

Rankings completos (184 bandas) en `data/by_ecoregion/E*/jm_ranking.csv`.

---

## 3. Cómo reproducir

```bash
cd bands_reduction
python scripts/07_run_jm_by_ecoregion.py \
  --out-dir /home/lserey/mapbiomas_land/tmp/JM_test_ME/184bands_ecorregion
```

---

## 4. Archivos

```
JM_184bands_ecoregion_REPORT/
├── README.md
├── figures/          # overview + E01..E15 top15
└── data/
    ├── ecoregion_overview.csv
    ├── ecoregion_overview.json
    └── by_ecoregion/E*/jm_ranking.csv
```
