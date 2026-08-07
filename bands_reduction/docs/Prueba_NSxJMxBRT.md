# Prueba_NSxJMxBRT — reducción de bandas (E2, E3)

**Alcance:** ecorregiones E2 (Desierto de Atacama) y E3 (Matorral del Norte 1), año 2015  
**Entrada:** 184 bandas · **Muestras supervisadas:** train Col2 estratificado, sin clases 33/34  

---

## 1. Métodos

Los tres métodos corren **de forma independiente** sobre 184 bandas. Se comparan después por intersección y unión.

### No supervisado

**Pregunta:** ¿qué bandas son espectralmente redundantes?  
**Lógica:** muestreo por eco → matriz |r| → clustering (@ 0.90 / 0.95 / 0.85) → representante por cluster → family rescue.  
**Etiquetas:** no requiere.  
**Salida:** `results/E{id}/2015/eco_merged/{0.90}/representatives/`  
**Scripts:** 06 → 10 → 11 → 12  

### Jeffries-Matusita (JM)

**Pregunta:** ¿esta banda separa pares de clases LULC?  
**Lógica:** por banda, promedio de JM pairwise sobre clases → ranking por `mean_jm`.  
**Etiquetas:** sí (Col2 train).  
**Salida:** `results/JM_test_PE/184bands_ecorregion_stratified/`  
**Script:** `20_jm_eco.py`  

### Boruta

**Pregunta:** ¿esta banda supera al azar en un Random Forest multibanda?  
**Lógica:** RF + shadow features → confirmed / tentative / rejected; ranking por `hit_rate` e importancia.  
**Etiquetas:** sí (Col2 train).  
**Salida:** `results/Boruta_PE/`  
**Script:** `22_boruta_eco.py`  

---

## 2. Resultados

**Criterio:** en cada eco, **N** = reps no supervisados @ |r|≥0.90. JM y Boruta se reportan como **top-N**.

### E2 (N = 96)

```
unsup (96) ──┐
JM top96  ───┼──∩──► Núcleo consensuado = 37 bandas
Boruta 96 ───┘
unsup ∪ JM ∪ Boruta ──► Pool ampliado = 155 bandas
```

### E3 (N = 109)

```
unsup (109) ──┐
JM top109 ────┼──∩──► Núcleo consensuado = 51 bandas
Boruta 109 ───┘
unsup ∪ JM ∪ Boruta ──► Pool ampliado = 165 bandas
```

### Entre ecorregiones

```
Núcleo(E2) ∩ Núcleo(E3)  →  21 bandas
Núcleo(E2) ∪ Núcleo(E3)  →  67 bandas
```

**21 bandas comunes:** `cai_median`, `cai_min`, `cloud_median`, `elevation`, `fns_amp`, `fns_median`, `fns_stdDev`, `gcvi_max`, `gv_median`, `gv_median_dry`, `gvs_median`, `gvs_median_wet`, `ndsi`, `sefi_median`, `sefi_median_dry`, `sefi_min`, `slope`, `soil_median`, `tpi`, `wefi_median`, `wefi_min`

| | E2 | E3 | E2 ∪ E3 |
|---|--:|--:|--:|
| **Núcleo** (unsup ∩ JM ∩ Boruta) | 37 | 51 | 67 |
| **Pool** (unsup ∪ JM ∪ Boruta) | 155 | 165 | 171 |

Listas completas por método: ver paths en §1.

---

## 3. Limitaciones

Ningún método, por sí solo, puede cerrar la lista final de bandas. Cada uno responde una pregunta distinta y tiene sesgos propios. Por eso el piloto compara **núcleo** (∩) y **pool** (∪), y la decisión fuerte queda para **QA RF-CV** (OA/Kappa vs. 184 bandas).

### No supervisado

**Qué implica usarlo como decisor:** que “no ser redundante espectralmente” = “sirve para clasificar LULC”.  
**Por qué no basta solo:** no ve etiquetas; solo correlación entre bandas. Una banda puede ser única en el cluster y aun así aportar poco a separar clases (o viceversa). Depende del mosaico, del muestreo y del umbral |r| (0.90 → 96–109 bandas en el piloto). Family rescue prioriza cobertura de familias, no utilidad discriminante.

### Jeffries-Matusita (JM)

**Qué implica usarlo como decisor:** que “separa bien pares de clases” = “es indispensable en un modelo multibanda”.  
**Por qué no basta solo:** mira **un par de clases a la vez**, no interacciones ni contexto global. Con muestras estratificadas la escala absoluta cambia (E2: ninguna banda ≥ 1.0; E3: casi ninguna). Un corte fijo no es portable entre ecos. El ranking es útil; la lista final no puede salir de JM sin validar clasificación.

### Boruta

**Qué implica usarlo como decisor:** que “gana a su shadow en RF” = “bandas imprescindibles”.  
**Por qué no basta solo:** costoso e inestable según n muestras y parámetros. En este piloto, con ~15–21k muestras/eco, casi todo quedó *confirmed* (113–120 bandas): el filtro binario **no recortó**. Conviene como **ranking** (`hit_rate`, importancia), no como lista kept tal cual.

### Por qué se necesitan los tres (+ QA)

| Método | Aporta | No resuelve |
|--------|--------|-------------|
| No supervisado | Redundancia espectral, estructura del espacio de bandas | Utilidad para clases |
| JM | Separabilidad por clase | Redundancia multibanda, interacciones |
| Boruta | Relevancia multibanda vs. azar | Estabilidad del corte binario, costo |

El **núcleo consensuado** (37 / 51 / 21 comunes) indica bandas que los tres respaldan a la misma escala (top-N = unsup), pero aún es **candidato**, no decisión final — ver **§4 QA**.

**Piloto:** solo E2/E3; mosaico unsup en `test/mosaics/`. Pendiente re-correr con mosaico CIM nacional 2015.

---

## 4. QA (Random Forest)

Comparación de listas vs. **184 bandas** (OA y Kappa). Umbral config: caída máx. **0.02** en OA/Kappa.

### 4.1 RF-CV en train estratificado (optimista)

Train Col2 estratificado (~15–21k muestras/eco, sin 33/34), 5-fold estratificado, `n_estimators=200`. Baseline ≈ **99.4% OA** (E2) / **99.9% OA** (E3).

| Lista | n | E2 ΔOA | E2 Δκ | E3 ΔOA | E3 Δκ |
|-------|--:|-------:|------:|-------:|------:|
| unsup @0.90 | 96 / 109 | +0.001 | +0.001 | +0.001 | +0.001 |
| JM top-N | 96 / 109 | −0.001 | −0.001 | +0.000 | +0.000 |
| Boruta top-N | 96 / 109 | +0.001 | +0.001 | +0.000 | +0.001 |
| núcleo triple | 37 / 51 | +0.000 | +0.000 | +0.001 | +0.001 |
| núcleo ∪ E2E3 | 67 | +0.001 | +0.001 | +0.001 | +0.001 |

Todas las listas ≈ baseline en CV interno — no discrimina bien.

Salida: `results/QA/E0{2,3}_qa_compare.csv` · job `11127707`.

### 4.2 Hold-out Col2 (train oficial → val gpkg)

Train Col2 oficial (`chile_train_184.npz`) → val gpkg (`layer=val`, representative_point @ 184B). Sin clases 33/34.

| Eco | Baseline val | Mejor reducción |
|-----|--------------|-----------------|
| E2 | OA 84.6%, κ 0.83 | JM top-N (−0.6 pp OA) |
| E3 | OA 92.2%, κ 0.91 | Boruta / núcleo∪67 (−2 pp OA) |

**E2** (361 train → 156 val · baseline OA **84.6%**, κ **0.828**)

| Lista | n | OA | κ | ΔOA | Δκ |
|-------|--:|---:|---:|----:|---:|
| baseline_184 | 184 | 0.846 | 0.828 | — | — |
| unsup @0.90 | 96 | 0.827 | 0.807 | −0.019 | −0.021 |
| JM top-N | 96 | 0.840 | 0.821 | −0.006 | −0.007 |
| Boruta top-N | 96 | 0.833 | 0.814 | −0.013 | −0.014 |
| núcleo triple | 37 | 0.833 | 0.814 | −0.013 | −0.014 |
| núcleo ∪ E2E3 | 67 | 0.833 | 0.814 | −0.013 | −0.014 |

**E3** (117 train → 51 val · baseline OA **92.2%**, κ **0.906**)

| Lista | n | OA | κ | ΔOA | Δκ |
|-------|--:|---:|---:|----:|---:|
| baseline_184 | 184 | 0.922 | 0.906 | — | — |
| unsup @0.90 | 109 | 0.882 | 0.859 | −0.039 | −0.047 |
| JM top-N | 109 | 0.843 | 0.813 | −0.078 | −0.094 |
| Boruta top-N | 109 | 0.902 | 0.883 | −0.020 | −0.023 |
| núcleo triple | 51 | 0.882 | 0.859 | −0.039 | −0.047 |
| núcleo ∪ E2E3 | 67 | 0.902 | 0.883 | −0.020 | −0.024 |

**Resumen Δ (misma tablita compacta)**

| Lista | n | E2 ΔOA | E2 Δκ | E3 ΔOA | E3 Δκ |
|-------|--:|-------:|------:|-------:|------:|
| unsup @0.90 | 96 / 109 | −0.019 | −0.021 | −0.039 | −0.047 |
| JM top-N | 96 / 109 | −0.006 | −0.007 | −0.078 | −0.094 |
| Boruta top-N | 96 / 109 | −0.013 | −0.014 | −0.020 | −0.023 |
| núcleo triple | 37 / 51 | −0.013 | −0.014 | −0.039 | −0.047 |
| núcleo ∪ E2E3 | 67 | −0.013 | −0.014 | −0.020 | −0.024 |

**Lectura:** E2 — todas ≤ 2 pp OA (pasa umbral); JM top-N cae menos. E3 — JM top-N fuera de umbral (~8 pp); Boruta top-N y núcleo ∪ E2E3 ~−2 pp.

Salida: `results/QA/E0{2,3}_qa_col2_val_compare.csv` · val NPZ: `results/QA/samples/chile_val_184.npz` · job `11127787`.
