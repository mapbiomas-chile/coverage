# JM_184_bands_REPORT

**Jeffries-Matusita band ranking — Chile, Landsat mosaic 2015, 184 bands**

| Field | Value |
| --- | --- |
| Scope | All Chile (15 ecoregions combined) |
| Year / mosaic | 2015 · 184-band MapBiomas tiles |
| Method | Univariate Jeffries-Matusita (mean pairwise JM); **no model training** |
| Band set | Full 184 (`source=full`), **no clustering** |
| Samples | Col2 `train` layers only |
| Samples path | `/home/lserey/mapbiomas_land/Muestras_Col2/particion_tv_col2/` |
| n labeled / n used JM | 7369 / **5996** |
| exclude_classes | **[33, 34]** (33=agua, 34=hielo/nieve) |
| n classes in JM | 17 |
| Extraction | Polygon representative point → `rasterio.sample` |
| Git scripts | `scripts/05_build_train_matrix_chile.py`, `06_run_jm_chile_184.py`, `04_run_jm.py` |
| Raw outputs (cluster FS) | `/home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_JM/` |
| Previous (all classes) | `.../results/jm_chile_184_all_classes/` |

---

## 1. Pipeline

![Pipeline](figures/pipeline_jm_chile_184.png)

1. Load **train** layer from each `E*.gpkg` (15 ecoregions).
2. Assign each sample to an MGRS mosaic tile; extract 184-band spectrum.
3. Build matrix `X (n×184)`, labels `y` (LULC class).
4. Drop classes in `exclude_classes` (agua/hielo) for the **core** ranking.
5. Rank every band by **mean pairwise JM** across remaining class pairs.
6. Export CSV/JSON + figures (this report).

JM does **not** train a classifier. The name `train` only means the sample split (vs `val`).

---

## 2. Sample coverage

### Per ecoregion (matrix, before exclude)

![Ecoregion counts](figures/eco_counts_chile_train.png)

| eco_id | eco_name | n_samples |
| --- | --- | --- |
| 1 | E1_Puna_seca_andina | 349 |
| 2 | E2_Desierto_Atacama | 362 |
| 3 | E3_Matorral_norte_1 | 117 |
| 4 | E4_Estepa_andina | 398 |
| 5 | E5_Matorral_norte_2 | 439 |
| 6 | E6_Andes_norte | 256 |
| 7 | E7_Andes_central | 790 |
| 8 | E8_Matorral_sur | 830 |
| 9 | E9_Costa_Norte | 1205 |
| 10 | E10_Andes_Sur | 685 |
| 11 | E11_Costa_Sur_1 | 712 |
| 12 | E12_Costa_Sur_2 | 118 |
| 13 | E13_Andes_Sur_Costa | 95 |
| 14 | E14_Estepa_patagonica | 406 |
| 15 | E15_Bosque_subpolar | 607 |

### Per LULC class (after exclude 33, 34)

![Class counts](figures/class_counts_chile_train.png)

Nombres según leyenda MapBiomas Chile Col2. **33** y **34** excluidas del JM núcleo.
**79** = Coníferas · **80** = Latifoliadas.
**62** no está en la leyenda Col2 (34 muestras, solo E2); *Sin nombre en leyenda*.

See [`data/class_counts.csv`](data/class_counts.csv).

---

## 3. JM score distribution

![Histogram](figures/jm_hist_chile_184.png)

Scores are mean JM over class pairs (theoretical range 0–2). Higher = better average class separability for that single band.

---

## 4. Top bands

### Top 15

![Top 15](figures/jm_top15_chile_184.png)

### Top 40

![Top 40](figures/jm_top40_chile_184.png)

### Top 20 (table)

| rank | band_index | band_name | mean_jm | min_jm | n_classes_used |
| --- | --- | --- | --- | --- | --- |
| 1 | 71 | hallcover_amp | 1.235603 | 0.000000 | 17 |
| 2 | 78 | hallheigth_amp | 1.137989 | 0.000000 | 17 |
| 3 | 94 | ndvi_median_wet | 1.081075 | 0.000303 | 17 |
| 4 | 92 | ndvi_median | 1.052787 | 0.001702 | 17 |
| 5 | 38 | gcvi_median | 1.035804 | 0.001979 | 17 |
| 6 | 133 | savi_max | 1.025612 | 0.004266 | 17 |
| 7 | 23 | evi2_max | 1.017007 | 0.002611 | 17 |
| 8 | 62 | gvs_median_wet | 0.996198 | 0.004000 | 17 |
| 9 | 136 | savi_median_wet | 0.996064 | 0.002197 | 17 |
| 10 | 40 | gcvi_median_wet | 0.986661 | 0.031315 | 17 |
| 11 | 26 | evi2_median_wet | 0.984133 | 0.002486 | 17 |
| 12 | 60 | gvs_median | 0.946945 | 0.002585 | 17 |
| 13 | 134 | savi_median | 0.930035 | 0.021851 | 17 |
| 14 | 55 | gv_median_wet | 0.921404 | 0.005600 | 17 |
| 15 | 24 | evi2_median | 0.920489 | 0.021101 | 17 |
| 16 | 85 | ndfi_median_wet | 0.915295 | 0.000712 | 17 |
| 17 | 14 | cai_stdDev | 0.909850 | 0.003740 | 17 |
| 18 | 129 | red_median_wet | 0.906566 | 0.013615 | 17 |
| 19 | 16 | cloud_median | 0.900043 | 0.002686 | 17 |
| 20 | 45 | green_median | 0.897990 | 0.000102 | 17 |

Full ranking CSV: [`data/jm_ranking_full.csv`](data/jm_ranking_full.csv)

---

## 5. Interpretation notes

- National pooled JM with **agua (33) and hielo/nieve (34) excluded** so they do not dominate separability.
- Some bands show `min_jm ≈ 0`: at least one remaining class pair is not separable with that band alone.
- Previous all-classes ranking kept under `jm_chile_184_all_classes/` on the cluster FS.

---

## 6. Reproducibility

```bash
cd bands_reduction
python scripts/06_run_jm_chile_184.py \
  --base-dir /home/lserey/mapbiomas_land/tmp/JM_test_ME/184_bands_JM \
  --exclude-classes 33 34 \
  --out-subdir jm_chile_184
```

---

## Appendix A — Full ranking of all 184 bands

| rank | band_index | band_name | mean_jm | min_jm | n_pairs | n_classes_used |
| ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 1 | 71 | `hallcover_amp` | 1.235603 | 0.000000 | 136 | 17 |
| 2 | 78 | `hallheigth_amp` | 1.137989 | 0.000000 | 136 | 17 |
| 3 | 94 | `ndvi_median_wet` | 1.081075 | 0.000303 | 136 | 17 |
| 4 | 92 | `ndvi_median` | 1.052787 | 0.001702 | 136 | 17 |
| 5 | 38 | `gcvi_median` | 1.035804 | 0.001979 | 136 | 17 |
| 6 | 133 | `savi_max` | 1.025612 | 0.004266 | 136 | 17 |
| 7 | 23 | `evi2_max` | 1.017007 | 0.002611 | 136 | 17 |
| 8 | 62 | `gvs_median_wet` | 0.996198 | 0.004000 | 136 | 17 |
| 9 | 136 | `savi_median_wet` | 0.996064 | 0.002197 | 136 | 17 |
| 10 | 40 | `gcvi_median_wet` | 0.986661 | 0.031315 | 136 | 17 |
| 11 | 26 | `evi2_median_wet` | 0.984133 | 0.002486 | 136 | 17 |
| 12 | 60 | `gvs_median` | 0.946945 | 0.002585 | 136 | 17 |
| 13 | 134 | `savi_median` | 0.930035 | 0.021851 | 136 | 17 |
| 14 | 55 | `gv_median_wet` | 0.921404 | 0.005600 | 136 | 17 |
| 15 | 24 | `evi2_median` | 0.920489 | 0.021101 | 136 | 17 |
| 16 | 85 | `ndfi_median_wet` | 0.915295 | 0.000712 | 136 | 17 |
| 17 | 14 | `cai_stdDev` | 0.909850 | 0.003740 | 136 | 17 |
| 18 | 129 | `red_median_wet` | 0.906566 | 0.013615 | 136 | 17 |
| 19 | 16 | `cloud_median` | 0.900043 | 0.002686 | 136 | 17 |
| 20 | 45 | `green_median` | 0.897990 | 0.000102 | 136 | 17 |
| 21 | 125 | `pri_stdDev` | 0.896689 | 0.000454 | 136 | 17 |
| 22 | 47 | `green_median_wet` | 0.893626 | 0.003891 | 136 | 17 |
| 23 | 91 | `ndvi_max` | 0.892449 | 0.000917 | 136 | 17 |
| 24 | 2 | `blue_median` | 0.887669 | 0.002301 | 136 | 17 |
| 25 | 52 | `gv_max` | 0.881236 | 0.006306 | 136 | 17 |
| 26 | 39 | `gcvi_median_dry` | 0.878262 | 0.000141 | 136 | 17 |
| 27 | 101 | `ndwi_median_wet` | 0.876208 | 0.001415 | 136 | 17 |
| 28 | 17 | `cloud_median_dry` | 0.876038 | 0.002016 | 136 | 17 |
| 29 | 83 | `ndfi_median` | 0.874288 | 0.005156 | 136 | 17 |
| 30 | 53 | `gv_median` | 0.867246 | 0.006853 | 136 | 17 |
| 31 | 127 | `red_median` | 0.867141 | 0.011015 | 136 | 17 |
| 32 | 4 | `blue_median_wet` | 0.862805 | 0.005699 | 136 | 17 |
| 33 | 3 | `blue_median_dry` | 0.861222 | 0.000385 | 136 | 17 |
| 34 | 93 | `ndvi_median_dry` | 0.854656 | 0.003333 | 136 | 17 |
| 35 | 11 | `cai_median_wet` | 0.853144 | 0.002512 | 136 | 17 |
| 36 | 18 | `cloud_median_wet` | 0.847872 | 0.002771 | 136 | 17 |
| 37 | 143 | `sefi_median_wet` | 0.845248 | 0.001000 | 136 | 17 |
| 38 | 97 | `ndvi_stdDev` | 0.842644 | 0.000955 | 136 | 17 |
| 39 | 46 | `green_median_dry` | 0.839921 | 0.004199 | 136 | 17 |
| 40 | 180 | `wefi_median_wet` | 0.839722 | 0.007268 | 136 | 17 |
| 41 | 9 | `cai_median` | 0.828607 | 0.002127 | 136 | 17 |
| 42 | 128 | `red_median_dry` | 0.815910 | 0.009635 | 136 | 17 |
| 43 | 37 | `gcvi_max` | 0.806372 | 0.011990 | 136 | 17 |
| 44 | 59 | `gvs_max` | 0.803240 | 0.002104 | 136 | 17 |
| 45 | 81 | `ndbi` | 0.797142 | 0.001287 | 136 | 17 |
| 46 | 89 | `ndmi` | 0.797117 | 0.001287 | 136 | 17 |
| 47 | 99 | `ndwi_median` | 0.797117 | 0.001287 | 136 | 17 |
| 48 | 178 | `wefi_median` | 0.796448 | 0.005168 | 136 | 17 |
| 49 | 141 | `sefi_median` | 0.793088 | 0.000623 | 136 | 17 |
| 50 | 172 | `swir2_median_wet` | 0.768955 | 0.024937 | 136 | 17 |
| 51 | 67 | `hallcover_median` | 0.762583 | 0.011842 | 136 | 17 |
| 52 | 90 | `ndsi` | 0.759027 | 0.001565 | 136 | 17 |
| 53 | 61 | `gvs_median_dry` | 0.758357 | 0.002517 | 136 | 17 |
| 54 | 135 | `savi_median_dry` | 0.757411 | 0.003115 | 136 | 17 |
| 55 | 25 | `evi2_median_dry` | 0.752959 | 0.003213 | 136 | 17 |
| 56 | 130 | `red_min` | 0.749452 | 0.004572 | 136 | 17 |
| 57 | 170 | `swir2_median` | 0.746258 | 0.020346 | 136 | 17 |
| 58 | 19 | `cloud_min` | 0.741887 | 0.000626 | 136 | 17 |
| 59 | 82 | `ndfi_max` | 0.738865 | 0.001118 | 136 | 17 |
| 60 | 42 | `gcvi_amp` | 0.720061 | 0.022614 | 136 | 17 |
| 61 | 63 | `gvs_min` | 0.718427 | 0.001009 | 136 | 17 |
| 62 | 43 | `gcvi_stdDev` | 0.713919 | 0.002792 | 136 | 17 |
| 63 | 54 | `gv_median_dry` | 0.709242 | 0.002228 | 136 | 17 |
| 64 | 56 | `gv_min` | 0.706316 | 0.000438 | 136 | 17 |
| 65 | 140 | `sefi_max` | 0.699364 | 0.003798 | 136 | 17 |
| 66 | 163 | `swir1_median` | 0.696841 | 0.005283 | 136 | 17 |
| 67 | 48 | `green_min` | 0.696231 | 0.004177 | 136 | 17 |
| 68 | 165 | `swir1_median_wet` | 0.695734 | 0.018057 | 136 | 17 |
| 69 | 84 | `ndfi_median_dry` | 0.695633 | 0.000673 | 136 | 17 |
| 70 | 58 | `gv_stdDev` | 0.682361 | 0.001512 | 136 | 17 |
| 71 | 116 | `npv_min` | 0.677880 | 0.000077 | 136 | 17 |
| 72 | 5 | `blue_min` | 0.676516 | 0.009642 | 136 | 17 |
| 73 | 86 | `ndfi_min` | 0.664878 | 0.000698 | 136 | 17 |
| 74 | 177 | `wefi_max` | 0.662711 | 0.001930 | 136 | 17 |
| 75 | 120 | `pri_median` | 0.649609 | 0.000425 | 136 | 17 |
| 76 | 158 | `soil_median_wet` | 0.647761 | 0.002491 | 136 | 17 |
| 77 | 33 | `fns_median_wet` | 0.647395 | 0.005145 | 136 | 17 |
| 78 | 41 | `gcvi_min` | 0.643707 | 0.003428 | 136 | 17 |
| 79 | 80 | `mbi` | 0.641747 | 0.004611 | 136 | 17 |
| 80 | 181 | `wefi_min` | 0.629726 | 0.000168 | 136 | 17 |
| 81 | 12 | `cai_min` | 0.628062 | 0.031396 | 136 | 17 |
| 82 | 29 | `evi2_stdDev` | 0.627660 | 0.000733 | 136 | 17 |
| 83 | 144 | `sefi_min` | 0.620908 | 0.002311 | 136 | 17 |
| 84 | 57 | `gv_amp` | 0.616962 | 0.001782 | 136 | 17 |
| 85 | 156 | `soil_median` | 0.614482 | 0.004073 | 136 | 17 |
| 86 | 95 | `ndvi_min` | 0.606731 | 0.003959 | 136 | 17 |
| 87 | 31 | `fns_median` | 0.605243 | 0.001062 | 136 | 17 |
| 88 | 142 | `sefi_median_dry` | 0.598526 | 0.003247 | 136 | 17 |
| 89 | 171 | `swir2_median_dry` | 0.581364 | 0.017694 | 136 | 17 |
| 90 | 115 | `npv_median_wet` | 0.580918 | 0.000025 | 136 | 17 |
| 91 | 10 | `cai_median_dry` | 0.577600 | 0.002493 | 136 | 17 |
| 92 | 114 | `npv_median_dry` | 0.576373 | 0.001286 | 136 | 17 |
| 93 | 139 | `savi_stdDev` | 0.574463 | 0.002453 | 136 | 17 |
| 94 | 108 | `nir_median_wet` | 0.571557 | 0.006039 | 136 | 17 |
| 95 | 122 | `pri_median_wet` | 0.562748 | 0.006364 | 136 | 17 |
| 96 | 106 | `nir_median` | 0.558800 | 0.007260 | 136 | 17 |
| 97 | 104 | `ndwi_stdDev` | 0.557966 | 0.001831 | 136 | 17 |
| 98 | 21 | `cloud_stdDev` | 0.554251 | 0.000965 | 136 | 17 |
| 99 | 154 | `slope` | 0.543931 | 0.001240 | 136 | 17 |
| 100 | 179 | `wefi_median_dry` | 0.540115 | 0.000725 | 136 | 17 |
| 101 | 126 | `red_max` | 0.537954 | 0.002589 | 136 | 17 |
| 102 | 121 | `pri_median_dry` | 0.537698 | 0.014966 | 136 | 17 |
| 103 | 13 | `cai_amp` | 0.536982 | 0.000584 | 136 | 17 |
| 104 | 27 | `evi2_min` | 0.533083 | 0.005867 | 136 | 17 |
| 105 | 28 | `evi2_amp` | 0.532562 | 0.002992 | 136 | 17 |
| 106 | 137 | `savi_min` | 0.530540 | 0.008714 | 136 | 17 |
| 107 | 96 | `ndvi_amp` | 0.526656 | 0.000732 | 136 | 17 |
| 108 | 119 | `pri_max` | 0.524290 | 0.003169 | 136 | 17 |
| 109 | 22 | `elevation` | 0.522904 | 0.008387 | 136 | 17 |
| 110 | 15 | `cloud_max` | 0.514734 | 0.000437 | 136 | 17 |
| 111 | 162 | `swir1_max` | 0.512466 | 0.002186 | 136 | 17 |
| 112 | 7 | `blue_stdDev` | 0.511260 | 0.001475 | 136 | 17 |
| 113 | 44 | `green_max` | 0.511223 | 0.002462 | 136 | 17 |
| 114 | 164 | `swir1_median_dry` | 0.507479 | 0.002639 | 136 | 17 |
| 115 | 8 | `cai_max` | 0.503053 | 0.002394 | 136 | 17 |
| 116 | 113 | `npv_median` | 0.502631 | 0.000777 | 136 | 17 |
| 117 | 173 | `swir2_min` | 0.501295 | 0.009488 | 136 | 17 |
| 118 | 118 | `npv_stdDev` | 0.501090 | 0.001668 | 136 | 17 |
| 119 | 50 | `green_stdDev` | 0.500106 | 0.000782 | 136 | 17 |
| 120 | 98 | `ndwi_max` | 0.495309 | 0.003563 | 136 | 17 |
| 121 | 1 | `blue_max` | 0.488211 | 0.002326 | 136 | 17 |
| 122 | 102 | `ndwi_min` | 0.488123 | 0.000037 | 136 | 17 |
| 123 | 107 | `nir_median_dry` | 0.486307 | 0.000313 | 136 | 17 |
| 124 | 150 | `shade_median_wet` | 0.485278 | 0.004212 | 136 | 17 |
| 125 | 132 | `red_stdDev` | 0.481252 | 0.001128 | 136 | 17 |
| 126 | 169 | `swir2_max` | 0.478382 | 0.008834 | 136 | 17 |
| 127 | 183 | `wefi_stdDev` | 0.478327 | 0.002149 | 136 | 17 |
| 128 | 138 | `savi_amp` | 0.476244 | 0.000562 | 136 | 17 |
| 129 | 20 | `cloud_amp` | 0.467351 | 0.000124 | 136 | 17 |
| 130 | 157 | `soil_median_dry` | 0.467118 | 0.000150 | 136 | 17 |
| 131 | 124 | `pri_amp` | 0.464602 | 0.000696 | 136 | 17 |
| 132 | 105 | `nir_max` | 0.463527 | 0.003915 | 136 | 17 |
| 133 | 159 | `soil_min` | 0.460690 | 0.003481 | 136 | 17 |
| 134 | 32 | `fns_median_dry` | 0.460245 | 0.000765 | 136 | 17 |
| 135 | 30 | `fns_max` | 0.459126 | 0.002476 | 136 | 17 |
| 136 | 112 | `npv_max` | 0.457830 | 0.002573 | 136 | 17 |
| 137 | 148 | `shade_median` | 0.446456 | 0.001722 | 136 | 17 |
| 138 | 151 | `shade_min` | 0.444451 | 0.001410 | 136 | 17 |
| 139 | 100 | `ndwi_median_dry` | 0.443869 | 0.000960 | 136 | 17 |
| 140 | 6 | `blue_amp` | 0.423440 | 0.002441 | 136 | 17 |
| 141 | 182 | `wefi_amp` | 0.419199 | 0.000340 | 136 | 17 |
| 142 | 103 | `ndwi_amp` | 0.416589 | 0.001476 | 136 | 17 |
| 143 | 117 | `npv_amp` | 0.411570 | 0.003609 | 136 | 17 |
| 144 | 51 | `green_median_texture` | 0.411070 | 0.001223 | 136 | 17 |
| 145 | 49 | `green_amp` | 0.407204 | 0.000160 | 136 | 17 |
| 146 | 155 | `soil_max` | 0.396440 | 0.008117 | 136 | 17 |
| 147 | 34 | `fns_min` | 0.388389 | 0.004404 | 136 | 17 |
| 148 | 131 | `red_amp` | 0.386700 | 0.000006 | 136 | 17 |
| 149 | 123 | `pri_min` | 0.377430 | 0.007254 | 136 | 17 |
| 150 | 111 | `nir_stdDev` | 0.375996 | 0.005826 | 136 | 17 |
| 151 | 79 | `hallheigth_stdDev` | 0.361202 | 0.002223 | 136 | 17 |
| 152 | 166 | `swir1_min` | 0.352531 | 0.000932 | 136 | 17 |
| 153 | 149 | `shade_median_dry` | 0.329407 | 0.002677 | 136 | 17 |
| 154 | 176 | `tpi` | 0.312998 | 0.000248 | 136 | 17 |
| 155 | 146 | `sefi_stdDev` | 0.295166 | 0.000080 | 136 | 17 |
| 156 | 110 | `nir_amp` | 0.289922 | 0.003896 | 136 | 17 |
| 157 | 153 | `shade_stdDev` | 0.271213 | 0.001953 | 136 | 17 |
| 158 | 109 | `nir_min` | 0.269550 | 0.001003 | 136 | 17 |
| 159 | 145 | `sefi_amp` | 0.262742 | 0.001310 | 136 | 17 |
| 160 | 65 | `gvs_stdDev` | 0.260863 | 0.000541 | 136 | 17 |
| 161 | 36 | `fns_stdDev` | 0.229359 | 0.002122 | 136 | 17 |
| 162 | 161 | `soil_stdDev` | 0.216129 | 0.000636 | 136 | 17 |
| 163 | 160 | `soil_amp` | 0.214516 | 0.000741 | 136 | 17 |
| 164 | 35 | `fns_amp` | 0.210544 | 0.000268 | 136 | 17 |
| 165 | 88 | `ndfi_stdDev` | 0.209002 | 0.000089 | 136 | 17 |
| 166 | 147 | `shade_max` | 0.202327 | 0.000549 | 136 | 17 |
| 167 | 168 | `swir1_stdDev` | 0.199387 | 0.003585 | 136 | 17 |
| 168 | 174 | `swir2_amp` | 0.198606 | 0.000041 | 136 | 17 |
| 169 | 167 | `swir1_amp` | 0.194693 | 0.001132 | 136 | 17 |
| 170 | 175 | `swir2_stdDev` | 0.184896 | 0.000572 | 136 | 17 |
| 171 | 64 | `gvs_amp` | 0.182615 | 0.001073 | 136 | 17 |
| 172 | 152 | `shade_amp` | 0.160167 | 0.000424 | 136 | 17 |
| 173 | 72 | `hallcover_stdDev` | 0.152238 | 0.000178 | 136 | 17 |
| 174 | 87 | `ndfi_amp` | 0.150719 | 0.001587 | 136 | 17 |
| 175 | 0 | `aspect` | 0.090790 | 0.000167 | 136 | 17 |
| 176 | 66 | `hallcover_max` | 0.000000 | 0.000000 | 136 | 17 |
| 177 | 68 | `hallcover_median_dry` | 0.000000 | 0.000000 | 136 | 17 |
| 178 | 69 | `hallcover_median_wet` | 0.000000 | 0.000000 | 136 | 17 |
| 179 | 70 | `hallcover_min` | 0.000000 | 0.000000 | 136 | 17 |
| 180 | 73 | `hallheigth_max` | 0.000000 | 0.000000 | 136 | 17 |
| 181 | 74 | `hallheigth_median` | 0.000000 | 0.000000 | 136 | 17 |
| 182 | 75 | `hallheigth_median_dry` | 0.000000 | 0.000000 | 136 | 17 |
| 183 | 76 | `hallheigth_median_wet` | 0.000000 | 0.000000 | 136 | 17 |
| 184 | 77 | `hallheigth_min` | 0.000000 | 0.000000 | 136 | 17 |
