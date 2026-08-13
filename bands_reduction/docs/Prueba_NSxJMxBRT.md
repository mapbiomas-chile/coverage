# Prueba_NSxJMxBRT — reducción de bandas (E1–E15)

**Alcance:** 15 ecorregiones (E01–E15), mosaico CIM nacional 2015  
**Entrada:** 184 bandas · **Muestras supervisadas:** entrenamiento y validación Col2 (hold-out), sin clases 33/34 (cuerpos de agua)  

---

## 1. Métodos

Este informe compara **tres formas distintas** de elegir bandas espectrales útiles para clasificar cobertura del suelo (LULC, *Land Use Land Cover*). Los tres métodos se aplican **por separado** sobre el mismo mosaico nacional de **184 bandas** (año 2015, corrección CIM). Luego se combinan por ecorregión mediante intersección (**núcleo consensuado**) o unión (**pool ampliado**).

En la **Prueba 1**, Jeffries-Matusita y Boruta no usan un corte binario propio para fijar cuántas bandas quedan: se toman las **N bandas mejor rankeadas**, donde **N** es el número de representantes que salió del método no supervisado con correlación **|r| ≥ 0.95** (ver abajo).

### No supervisado

**Pregunta que responde:** ¿qué bandas se parecen entre sí espectralmente y cuáles son redundantes?  
**Idea general:** se muestrean píxeles dentro de cada **ecorregión** (unidad biogeográfica del mapa de ecorregiones), se calcula qué tan correlacionadas están las bandas y se agrupan las muy parecidas en **clusters**. De cada cluster se elige **un representante**; si una banda no se parece a ninguna otra, forma un cluster de tamaño 1 (banda suelta).  
**¿Necesita clases de cobertura del suelo?** No.  
**Umbral principal de este informe:** correlación **|r| ≥ 0.95** (bandas con |r| por debajo de 0.95 no se fusionan en el mismo cluster).  
**Archivos de salida:** `results/CIM2015/E{id}/2015/eco_merged/0.95/` (listado de clusters y lista de representantes en `representatives/representatives.json`).  
**Scripts del pipeline:** inventario de tiles → muestreo por ecorregión → clustering → selección de representantes (`06` → `10` → `11` → `12`).

### Jeffries-Matusita (JM)

**Pregunta que responde:** ¿esta banda ayuda a **separar pares de clases** de cobertura del suelo?  
**Idea general:** para cada banda se mide, en promedio, qué tan bien distingue cada par de clases del entrenamiento (distancia de Jeffries-Matusita). Las bandas se ordenan de mayor a menor separabilidad (`mean_jm` en el ranking). En este mosaico **casi ninguna banda alcanza el valor 1.0** que a veces se usa como corte en otros estudios; por eso aquí se reportan las **N mejores del ranking**, con la misma **N** que en el no supervisado.  
**¿Necesita clases de cobertura del suelo?** Sí (muestras de entrenamiento Col2).  
**Archivo de salida:** `results/CIM2015/JM/184bands_ecorregion/E{NN}/jm_ranking.csv`  
**Script:** `20_jm_eco.py`

### Boruta

**Pregunta que responde:** ¿esta banda aporta información **real** a un clasificador **Random Forest**, por encima de una variable aleatoria de referencia (“sombra”)?  
**Idea general:** Boruta entrena Random Forest muchas veces comparando cada banda con copias aleatorias; clasifica bandas como confirmadas, tentativas o rechazadas, y permite ordenarlas por tasa de acierto (`hit_rate`) e importancia. Con el volumen de muestras de este trabajo, muchas bandas quedan “confirmadas”; igual que en JM, en la Prueba 1 se toman las **N mejor rankeadas** para comparar en igualdad de condiciones.  
**¿Necesita clases de cobertura del suelo?** Sí (muestras de entrenamiento Col2).  
**Archivo de salida:** `results/CIM2015/Boruta/E{NN}_all184/boruta_decisions.csv`  
**Script:** `22_boruta_eco.py`

**Muestras con clases (entrenamiento y validación):** reflectancia en 184 bandas extraída en puntos Col2 — entrenamiento: `results/CIM2015/QA/samples/chile_train_184.npz`; validación: `chile_val_184.npz`. Se excluyen las clases 33 y 34 (cuerpos de agua).

---

## 2. Limitaciones

Ninguno de los tres métodos, usado solo, puede fijar la lista final de bandas. Cada uno responde una pregunta distinta y arrastra sesgos propios. Por eso este informe combina **núcleo consensuado** (intersección de las tres listas) y **pool ampliado** (unión), y reserva la decisión fuerte para la **validación con clasificador** (§4).

### No supervisado

**Qué implica usarlo como único criterio:** asumir que “no ser redundante espectralmente” equivale a “sirve para clasificar cobertura del suelo”.  
**Por qué no basta solo:** no usa etiquetas de clases; solo mide similitud entre bandas. Una banda puede ser la única de su grupo y aun así aportar poco a separar clases (o al revés). El resultado depende del mosaico, del muestreo de píxeles y del umbral de correlación (aquí **|r| ≥ 0.95**). El rescate por familias de bandas prioriza cobertura de tipos espectrales, no utilidad discriminante para clases.

### Jeffries-Matusita

**Qué implica usarlo como único criterio:** asumir que “separa bien pares de clases” equivale a “es indispensable en un modelo con muchas bandas”.  
**Por qué no basta solo:** evalúa **un par de clases a la vez**, no interacciones ni el contexto multibanda completo. En el mosaico CIM 2015 **ninguna banda alcanza distancia 1.0** en ninguna ecorregión, así que un corte absoluto no es portable. El ranking sí es útil; la lista final no puede salir solo de Jeffries-Matusita sin validar clasificación.

### Boruta

**Qué implica usarlo como único criterio:** asumir que “supera a una variable sombra aleatoria en **Random Forest**” equivale a “bandas imprescindibles”.  
**Por qué no basta solo:** es costoso y sensible al número de muestras y a los parámetros. Con las muestras Col2 de este trabajo, la decisión binaria confirmada/rechazada **casi no recorta** (la mayoría de las 184 bandas queda confirmada). Conviene como **ranking** (tasa de acierto e importancia), no como lista final sin recorte adicional.

### Por qué se necesitan los tres (más validación)

| Método | Aporta | No resuelve |
|--------|--------|-------------|
| No supervisado | Redundancia espectral, estructura del espacio de bandas | Utilidad para clases concretas |
| Jeffries-Matusita | Separabilidad entre pares de clases | Redundancia multibanda, interacciones |
| Boruta | Relevancia multibanda frente al azar | Estabilidad del corte binario, costo computacional |

El **núcleo consensuado** local (intersección de los tres métodos con la misma **N**) señala bandas respaldadas por todos a igual escala, pero sigue siendo **candidato**, no decisión final — ver **§4**. En la práctica el núcleo local es muy pequeño (2–21 bandas) y en validación suele quedar por debajo del baseline; el **pool ampliado** local conserva mejor la exactitud.

---

## 3. Resultados

**Criterio común (Prueba 1):** en cada ecorregión, **N** = número de representantes del no supervisado con **|r| ≥ 0.95**. Jeffries-Matusita y Boruta aportan las **N bandas mejor rankeadas** de sus respectivos rankings sobre las 184 bandas.

### 3.1 Selección por ecorregión

En cada fila: **N** (representantes no supervisados), **Núcleo** (intersección no supervisado ∩ Jeffries-Matusita ∩ Boruta) y **Pool** (unión de las tres listas).

| Ecorregión | Nombre | N | Núcleo | Pool |
|---|---|--:|--:|--:|
| E01 | Puna seca andina | 59 | 2 | 134 |
| E02 | Desierto de Atacama | 80 | 11 | 156 |
| E03 | Matorral norte 1 | 67 | 9 | 145 |
| E04 | Estepa andina | 51 | 10 | 109 |
| E05 | Matorral norte 2 | 76 | 21 | 142 |
| E06 | Andes norte | 57 | 5 | 121 |
| E07 | Andes central | 46 | 2 | 104 |
| E08 | Matorral sur | 66 | 11 | 134 |
| E09 | Costa norte | 47 | 2 | 114 |
| E10 | Andes sur | 46 | 5 | 104 |
| E11 | Costa sur 1 | 15 | 0 | 43 |
| E12 | Costa sur 2 | 53 | 12 | 114 |
| E13 | Andes sur costa | 51 | 3 | 115 |
| E14 | Estepa patagónica | 39 | 2 | 97 |
| E15 | Bosque subpolar | 34 | 3 | 87 |

### 3.2 Consenso entre ecorregiones

Al cruzar los núcleos y pools **locales** de las 15 ecorregiones:

| Agregación | Bandas | Interpretación |
|---|---:|---|
| Núcleo ∩ 15 ecorregiones | **0** | Ninguna banda está en el núcleo local de **todas** las ecorregiones |
| Núcleo ∪ 15 ecorregiones | **42** | Unión de todos los núcleos locales |
| Pool ∩ 15 ecorregiones | **18** | Bandas presentes en el pool local de **cada** ecorregión |
| Pool ∪ 15 ecorregiones | **183** | Casi el mosaico completo (solo falta 1 banda) |

**Lectura breve:** con umbral estricto (0.95) el no supervisado ya reduce fuerte (N entre 15 y 80). El núcleo triple local es pequeño; en E11 (Costa sur 1) es **vacío** (N = 15). Los pools locales quedan entre 43 y 156 bandas.

Listas completas por método: rutas en §1 · agregados cross-eco: `results/CIM2015/QA/col2_val_cross_eco/cross_eco_band_lists.json`

### 3.3 Resumen de validación (vista rápida)

Validación hold-out Col2 (§4): umbral de aceptación = caída máxima **0.05** en exactitud (OA) y Kappa frente a 184 bandas.

| Lista (local por ecorregión) | Ecorregiones que pasan / 15 |
|---|---:|
| No supervisado @0.95 | 12 |
| Jeffries-Matusita top-N | 11 |
| Boruta top-N | 12 |
| Núcleo triple local | 4 |
| Pool ampliado local | 14 |

El núcleo local casi no sirve en validación; el pool local es el combinado más robusto a nivel nacional.


---

## 4. Validación (Random Forest, hold-out Col2)

Se entrena un **Random Forest** con las muestras Col2 de entrenamiento (`chile_train_184.npz`) y se evalúa en validación independiente (`chile_val_184.npz`), por ecorregión. Referencia: **184 bandas** (baseline). **Pasa** si la caída en OA y Kappa es ≤ **0.05** (5 puntos porcentuales en OA).

### 4.1 Resumen nacional

| Lista | Pass / 15 | Ecorregiones que no pasan |
|---|---:|---|
| No supervisado @0.95 | 12 | E11, E12, E15 |
| Jeffries-Matusita top-N | 11 | E01, E11, E13, E15 |
| Boruta top-N | 12 | E12, E13, E15 |
| Núcleo triple local | 4 | E01, E06, E07, E08, E09, E10, E11, E12, E13, E14, E15 |
| Pool ampliado local | 14 | E13 |

Salida por ecorregión: `results/CIM2015/QA/col2_val/E{NN}_qa_col2_val_compare.csv`

### 4.2 Detalle por ecorregión

#### E01 — Puna seca andina (296 entrenamiento → 129 validación · baseline OA 86.0%, κ 0.844)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.860 | 0.844 | — | — | — |
| unsup_095 | 59 | 0.876 | 0.861 | +0.016 | +0.017 | ✓ |
| jm_topN | 59 | 0.791 | 0.765 | -0.070 | -0.078 | ✗ |
| boruta_topN | 59 | 0.845 | 0.826 | -0.016 | -0.018 | ✓ |
| nucleo_triple | 2 | 0.713 | 0.680 | -0.147 | -0.163 | ✗ |
| pool_union | 134 | 0.876 | 0.861 | +0.016 | +0.017 | ✓ |

#### E02 — Desierto de Atacama (359 entrenamiento → 155 validación · baseline OA 78.7%, κ 0.762)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.787 | 0.762 | — | — | — |
| unsup_095 | 80 | 0.839 | 0.820 | +0.052 | +0.058 | ✓ |
| jm_topN | 80 | 0.819 | 0.798 | +0.032 | +0.036 | ✓ |
| boruta_topN | 80 | 0.819 | 0.798 | +0.032 | +0.036 | ✓ |
| nucleo_triple | 11 | 0.813 | 0.791 | +0.026 | +0.029 | ✓ |
| pool_union | 156 | 0.819 | 0.799 | +0.032 | +0.036 | ✓ |

#### E03 — Matorral norte 1 (117 entrenamiento → 51 validación · baseline OA 86.3%, κ 0.835)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.863 | 0.835 | — | — | — |
| unsup_095 | 67 | 0.882 | 0.859 | +0.020 | +0.023 | ✓ |
| jm_topN | 67 | 0.824 | 0.787 | -0.039 | -0.048 | ✓ |
| boruta_topN | 67 | 0.882 | 0.859 | +0.020 | +0.024 | ✓ |
| nucleo_triple | 9 | 0.863 | 0.835 | +0.000 | +0.000 | ✓ |
| pool_union | 145 | 0.863 | 0.836 | +0.000 | +0.001 | ✓ |

#### E04 — Estepa andina (331 entrenamiento → 140 validación · baseline OA 66.4%, κ 0.629)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.664 | 0.629 | — | — | — |
| unsup_095 | 51 | 0.707 | 0.677 | +0.043 | +0.047 | ✓ |
| jm_topN | 51 | 0.664 | 0.629 | +0.000 | -0.000 | ✓ |
| boruta_topN | 51 | 0.686 | 0.653 | +0.021 | +0.024 | ✓ |
| nucleo_triple | 10 | 0.643 | 0.605 | -0.021 | -0.024 | ✓ |
| pool_union | 109 | 0.679 | 0.645 | +0.014 | +0.016 | ✓ |

#### E05 — Matorral norte 2 (396 entrenamiento → 169 validación · baseline OA 85.2%, κ 0.835)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.852 | 0.835 | — | — | — |
| unsup_095 | 76 | 0.846 | 0.828 | -0.006 | -0.007 | ✓ |
| jm_topN | 76 | 0.864 | 0.848 | +0.012 | +0.013 | ✓ |
| boruta_topN | 76 | 0.852 | 0.835 | +0.000 | -0.000 | ✓ |
| nucleo_triple | 21 | 0.870 | 0.855 | +0.018 | +0.020 | ✓ |
| pool_union | 142 | 0.840 | 0.822 | -0.012 | -0.013 | ✓ |

#### E06 — Andes norte (183 entrenamiento → 79 validación · baseline OA 86.1%, κ 0.842)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.861 | 0.842 | — | — | — |
| unsup_095 | 57 | 0.911 | 0.899 | +0.051 | +0.057 | ✓ |
| jm_topN | 57 | 0.823 | 0.798 | -0.038 | -0.044 | ✓ |
| boruta_topN | 57 | 0.873 | 0.856 | +0.013 | +0.014 | ✓ |
| nucleo_triple | 5 | 0.722 | 0.682 | -0.139 | -0.160 | ✗ |
| pool_union | 121 | 0.886 | 0.870 | +0.025 | +0.028 | ✓ |

#### E07 — Andes central (627 entrenamiento → 270 validación · baseline OA 84.1%, κ 0.812)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.841 | 0.812 | — | — | — |
| unsup_095 | 46 | 0.848 | 0.819 | +0.007 | +0.007 | ✓ |
| jm_topN | 46 | 0.811 | 0.778 | -0.030 | -0.034 | ✓ |
| boruta_topN | 46 | 0.837 | 0.807 | -0.004 | -0.005 | ✓ |
| nucleo_triple | 2 | 0.437 | 0.369 | -0.404 | -0.443 | ✗ |
| pool_union | 104 | 0.848 | 0.821 | +0.007 | +0.009 | ✓ |

#### E08 — Matorral sur (760 entrenamiento → 324 validación · baseline OA 82.7%, κ 0.802)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.827 | 0.802 | — | — | — |
| unsup_095 | 66 | 0.824 | 0.798 | -0.003 | -0.004 | ✓ |
| jm_topN | 66 | 0.793 | 0.764 | -0.034 | -0.038 | ✓ |
| boruta_topN | 66 | 0.818 | 0.791 | -0.009 | -0.011 | ✓ |
| nucleo_triple | 11 | 0.722 | 0.685 | -0.105 | -0.117 | ✗ |
| pool_union | 134 | 0.827 | 0.802 | +0.000 | +0.001 | ✓ |

#### E09 — Costa norte (1070 entrenamiento → 459 validación · baseline OA 85.0%, κ 0.758)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.850 | 0.758 | — | — | — |
| unsup_095 | 47 | 0.861 | 0.774 | +0.011 | +0.016 | ✓ |
| jm_topN | 47 | 0.843 | 0.747 | -0.007 | -0.011 | ✓ |
| boruta_topN | 47 | 0.845 | 0.753 | -0.004 | -0.005 | ✓ |
| nucleo_triple | 2 | 0.412 | 0.274 | -0.438 | -0.484 | ✗ |
| pool_union | 114 | 0.863 | 0.778 | +0.013 | +0.021 | ✓ |

#### E10 — Andes sur (430 entrenamiento → 183 validación · baseline OA 86.9%, κ 0.855)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.869 | 0.855 | — | — | — |
| unsup_095 | 46 | 0.847 | 0.830 | -0.022 | -0.025 | ✓ |
| jm_topN | 46 | 0.858 | 0.842 | -0.011 | -0.012 | ✓ |
| boruta_topN | 46 | 0.847 | 0.830 | -0.022 | -0.024 | ✓ |
| nucleo_triple | 5 | 0.781 | 0.757 | -0.087 | -0.097 | ✗ |
| pool_union | 104 | 0.885 | 0.873 | +0.016 | +0.018 | ✓ |

#### E11 — Costa sur 1 (570 entrenamiento → 244 validación · baseline OA 79.9%, κ 0.718)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.799 | 0.718 | — | — | — |
| unsup_095 | 15 | 0.705 | 0.597 | -0.094 | -0.121 | ✗ |
| jm_topN | 15 | 0.672 | 0.560 | -0.127 | -0.158 | ✗ |
| boruta_topN | 15 | 0.807 | 0.730 | +0.008 | +0.012 | ✓ |
| nucleo_triple | 0 | — | — | — | — | — |
| pool_union | 43 | 0.807 | 0.730 | +0.008 | +0.011 | ✓ |

#### E12 — Costa sur 2 (103 entrenamiento → 45 validación · baseline OA 82.2%, κ 0.762)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.822 | 0.762 | — | — | — |
| unsup_095 | 53 | 0.778 | 0.700 | -0.044 | -0.062 | ✗ |
| jm_topN | 53 | 0.800 | 0.730 | -0.022 | -0.033 | ✓ |
| boruta_topN | 53 | 0.756 | 0.672 | -0.067 | -0.090 | ✗ |
| nucleo_triple | 12 | 0.711 | 0.614 | -0.111 | -0.149 | ✗ |
| pool_union | 114 | 0.822 | 0.760 | +0.000 | -0.002 | ✓ |

#### E13 — Andes sur costa (70 entrenamiento → 32 validación · baseline OA 84.4%, κ 0.790)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.844 | 0.790 | — | — | — |
| unsup_095 | 51 | 0.844 | 0.789 | +0.000 | -0.001 | ✓ |
| jm_topN | 51 | 0.750 | 0.662 | -0.094 | -0.128 | ✗ |
| boruta_topN | 51 | 0.750 | 0.673 | -0.094 | -0.117 | ✗ |
| nucleo_triple | 3 | 0.656 | 0.561 | -0.188 | -0.230 | ✗ |
| pool_union | 115 | 0.781 | 0.712 | -0.062 | -0.079 | ✗ |

#### E14 — Estepa patagónica (286 entrenamiento → 121 validación · baseline OA 85.1%, κ 0.835)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.851 | 0.835 | — | — | — |
| unsup_095 | 39 | 0.810 | 0.790 | -0.041 | -0.046 | ✓ |
| jm_topN | 39 | 0.835 | 0.817 | -0.017 | -0.018 | ✓ |
| boruta_topN | 39 | 0.868 | 0.854 | +0.017 | +0.019 | ✓ |
| nucleo_triple | 2 | 0.603 | 0.563 | -0.248 | -0.273 | ✗ |
| pool_union | 97 | 0.851 | 0.835 | +0.000 | +0.000 | ✓ |

#### E15 — Bosque subpolar (396 entrenamiento → 169 validación · baseline OA 75.7%, κ 0.728)

| Lista | n | OA | κ | ΔOA | Δκ | Pasa @0.05 |
|-------|--:|---:|---:|----:|---:|:--:|
| baseline_184 | 184 | 0.757 | 0.728 | — | — | — |
| unsup_095 | 34 | 0.698 | 0.662 | -0.059 | -0.066 | ✗ |
| jm_topN | 34 | 0.704 | 0.669 | -0.053 | -0.060 | ✗ |
| boruta_topN | 34 | 0.704 | 0.669 | -0.053 | -0.059 | ✗ |
| nucleo_triple | 3 | 0.456 | 0.394 | -0.302 | -0.334 | ✗ |
| pool_union | 87 | 0.751 | 0.722 | -0.006 | -0.007 | ✓ |

### 4.3 Nota interpretativa

A nivel nacional, la validación no muestra una caída sistemática al recortar bandas: el **pool ampliado local** pasa en 14 de 15 ecorregiones y el no supervisado y Boruta en 12. El **núcleo triple local** casi no funciona (solo 4 ecorregiones pasan), coherente con listas demasiado cortas (2–21 bandas) que dejan fuera información que el Random Forest sí explotaba con 184 entradas.

Los casos más claros de **mejora con menos bandas** aparecen con el no supervisado @0.95. En **E02 (Desierto de Atacama)**, 80 bandas suben la OA de 78.7% a 83.9% (+5.2 pp); en **E06 (Andes norte)**, 57 bandas pasan de 86.1% a 91.1% (+5.1 pp); en **E04 (Estepa andina)**, 51 bandas mejoran un baseline ya bajo (66.4% → 70.7%). No es que “menos bandas siempre sea mejor”: en **E15 (Bosque subpolar)** y **E11–E12 (Costa sur)** las listas reducidas caen por debajo del umbral, y en **E13** el pool local también falla — sobre todo donde hay pocas muestras de validación (E13: 32 puntos) o el recorte es muy agresivo (E11: N = 15).

**Por qué a veces rinde igual o mejor con menos bandas:**

1. Muchas de las 184 bandas son **redundantes** entre sí; meter variables casi duplicadas no añade señal útil al clasificador.

2. Las listas reducidas no son un subconjunto al azar, sino representantes espectrales o bandas rankeadas por separabilidad/relevancia — se conserva información condensada.

3. Con menos columnas correlacionadas, el Random Forest puede **generalizar mejor** en el hold-out, sin repartir splits en detalle ruidoso del entrenamiento.

4. El baseline de 184 bandas es la **referencia del mosaico completo**, no el óptimo garantizado de clasificación.

A la inversa, **Jeffries-Matusita top-N** puede empeorar aunque use la misma N (p. ej. E01 −7 pp, E13 −9 pp): prioriza separación par a par de clases y puede descartar bandas que en conjunto multibanda sí aportan. Por eso la lectura prudente es: **la reducción es viable cuando el subconjunto mantiene (o mejora ligeramente) OA/Kappa en validación independiente**, pero las ganancias positivas deben tomarse con cautela — en hold-outs pequeños, unos pocos puntos más o menos pueden mezclar señal real con variabilidad muestral. El pool local es el combinado más estable; el núcleo local no es candidato operativo.

---

## Anexo — Listas de bandas recomendadas por ecorregión

Criterio: **mejor OA en validación Col2** (hold-out §4) entre las cinco listas reducidas. Si dos o más empatan, se listan todas. Índices de banda (`0`–`183`) del mosaico CIM 2015.

### Ecorregión E01: "Puna seca andina"

**Método 1:** No supervisado @0.95 (59 bandas)

`0, 4, 5, 8, 9, 10, 12, 13, 14, 22, 28, 38, 39, 40, 41, 42, 45, 46, 48, 65, 71, 72, 79, 80, 89, 90, 91, 94, 96, 97, 98, 99, 100, 101, 102, 103, 104, 106, 107, 108, 109, 119, 120, 121, 122, 123, 124, 125, 131, 132, 134, 137, 154, 162, 164, 166, 167, 168, 170`

**Método 2:** Pool ampliado (134 bandas)

`0, 2, 3, 4, 5, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 36, 38, 39, 40, 41, 42, 45, 46, 47, 48, 51, 52, 53, 54, 55, 56, 58, 59, 60, 61, 62, 63, 65, 71, 72, 79, 80, 82, 83, 84, 85, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 106, 107, 108, 109, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 127, 129, 131, 132, 133, 134, 135, 136, 137, 140, 141, 142, 143, 144, 145, 146, 148, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 164, 166, 167, 168, 170, 176, 177, 178, 179, 180, 181, 183`

### Ecorregión E02: "Desierto de Atacama"

**Método 1:** No supervisado @0.95 (80 bandas)

`0, 1, 2, 3, 5, 7, 8, 9, 12, 13, 14, 22, 25, 27, 28, 29, 38, 40, 41, 42, 47, 49, 51, 64, 66, 67, 68, 70, 71, 74, 77, 78, 80, 81, 82, 83, 85, 86, 90, 91, 92, 93, 95, 96, 97, 98, 99, 100, 102, 103, 104, 105, 106, 107, 108, 111, 119, 120, 121, 122, 123, 124, 130, 136, 140, 141, 142, 144, 145, 146, 148, 154, 156, 162, 163, 164, 165, 166, 168, 183`

### Ecorregión E03: "Matorral norte 1"

**Método 1:** No supervisado @0.95 (67 bandas)

`0, 2, 3, 5, 8, 9, 11, 12, 13, 14, 22, 23, 24, 27, 28, 29, 38, 39, 41, 43, 47, 70, 71, 72, 78, 79, 80, 81, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 106, 107, 108, 119, 120, 121, 122, 123, 124, 125, 126, 130, 131, 132, 147, 154, 162, 163, 164, 165, 166, 167, 168`

**Método 2:** Boruta top-N (67 bandas)

`22, 2, 45, 94, 3, 107, 127, 46, 106, 17, 16, 128, 1, 126, 24, 40, 92, 101, 11, 44, 4, 75, 135, 14, 25, 99, 144, 9, 93, 27, 120, 37, 74, 62, 8, 58, 90, 166, 134, 12, 15, 38, 137, 13, 105, 170, 146, 122, 29, 178, 51, 102, 154, 57, 6, 68, 67, 10, 85, 77, 39, 143, 129, 156, 100, 95, 171`

### Ecorregión E04: "Estepa andina"

**Método 1:** No supervisado @0.95 (51 bandas)

`0, 8, 9, 10, 12, 14, 22, 28, 37, 38, 39, 40, 41, 47, 48, 49, 62, 71, 72, 79, 80, 89, 90, 91, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 119, 120, 121, 122, 123, 124, 125, 127, 128, 132, 154, 164, 166, 167, 172`

### Ecorregión E05: "Matorral norte 2"

**Método 1:** Núcleo triple (21 bandas)

`8, 9, 11, 12, 17, 22, 23, 24, 26, 40, 81, 89, 90, 91, 92, 93, 94, 99, 101, 143, 154`

### Ecorregión E06: "Andes norte"

**Método 1:** No supervisado @0.95 (57 bandas)

`0, 8, 9, 10, 12, 14, 22, 27, 28, 29, 30, 38, 39, 40, 41, 42, 45, 47, 48, 71, 80, 81, 89, 90, 91, 92, 93, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 106, 108, 109, 119, 120, 121, 122, 123, 124, 125, 128, 131, 132, 136, 154, 162, 164, 166, 167, 170`

### Ecorregión E07: "Andes central"

**Método 1:** No supervisado @0.95 (46 bandas)

`0, 8, 9, 10, 12, 14, 28, 38, 39, 40, 41, 42, 45, 47, 49, 57, 71, 72, 80, 89, 90, 93, 94, 96, 97, 98, 99, 100, 102, 103, 106, 108, 109, 119, 120, 121, 122, 123, 124, 125, 128, 132, 134, 154, 169, 171`

**Método 2:** Pool ampliado (104 bandas)

`0, 1, 6, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 32, 35, 37, 38, 39, 40, 41, 42, 43, 45, 47, 49, 51, 52, 53, 55, 57, 58, 60, 62, 69, 71, 72, 80, 89, 90, 91, 92, 93, 94, 96, 97, 98, 99, 100, 101, 102, 103, 106, 108, 109, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 128, 129, 132, 133, 134, 136, 137, 138, 139, 146, 148, 149, 150, 154, 157, 158, 159, 161, 164, 169, 170, 171, 172, 178, 180`

### Ecorregión E08: "Matorral sur"

**Método 1:** Pool ampliado (134 bandas)

`0, 2, 3, 4, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27, 28, 29, 33, 37, 38, 39, 40, 41, 42, 45, 46, 47, 48, 50, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 67, 69, 71, 74, 76, 80, 83, 85, 86, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 127, 128, 129, 130, 131, 133, 134, 135, 136, 139, 141, 143, 144, 148, 149, 150, 151, 153, 154, 156, 158, 159, 161, 162, 163, 164, 165, 166, 167, 168, 170, 171, 172, 173, 177, 178, 179, 180, 181, 182, 183`

### Ecorregión E09: "Costa norte"

**Método 1:** Pool ampliado (114 bandas)

`0, 2, 4, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 28, 31, 32, 36, 38, 39, 40, 41, 42, 44, 45, 47, 52, 53, 55, 57, 58, 60, 61, 62, 63, 67, 69, 71, 72, 74, 76, 78, 79, 80, 81, 83, 84, 86, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 105, 106, 108, 109, 110, 112, 113, 114, 115, 116, 117, 118, 119, 120, 122, 123, 124, 125, 127, 129, 133, 134, 135, 136, 139, 141, 142, 144, 151, 154, 155, 156, 157, 158, 159, 161, 163, 164, 169, 170, 172, 177, 178, 180, 183`

### Ecorregión E10: "Andes sur"

**Método 1:** Pool ampliado (104 bandas)

`0, 2, 8, 9, 10, 11, 12, 13, 14, 16, 18, 19, 21, 22, 23, 24, 26, 28, 30, 31, 33, 35, 37, 38, 39, 40, 41, 42, 45, 46, 47, 49, 50, 52, 53, 55, 58, 59, 60, 61, 62, 67, 69, 71, 72, 74, 76, 78, 80, 81, 82, 83, 89, 90, 91, 92, 93, 94, 96, 97, 98, 99, 100, 101, 102, 103, 105, 106, 107, 108, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 127, 129, 133, 134, 136, 140, 148, 154, 156, 158, 159, 161, 163, 165, 170, 172, 177, 178, 180, 181`

### Ecorregión E11: "Costa sur 1"

**Método 1:** Boruta top-N (15 bandas)

`22, 38, 45, 127, 92, 9, 99, 163, 94, 80, 170, 40, 106, 24, 101`

**Método 2:** Pool ampliado (43 bandas)

`0, 9, 13, 14, 16, 18, 19, 22, 24, 31, 38, 39, 40, 41, 42, 45, 58, 60, 71, 72, 78, 80, 87, 92, 94, 99, 101, 103, 106, 113, 115, 116, 123, 124, 127, 141, 142, 156, 157, 158, 159, 163, 170`

### Ecorregión E12: "Costa sur 2"

**Método 1:** Pool ampliado (114 bandas)

`0, 2, 4, 8, 9, 10, 11, 12, 13, 14, 16, 18, 19, 21, 22, 24, 25, 26, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 44, 45, 46, 47, 50, 53, 55, 56, 60, 61, 62, 67, 69, 71, 78, 79, 80, 81, 83, 85, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 105, 106, 107, 109, 110, 115, 116, 118, 119, 120, 121, 122, 123, 124, 125, 127, 129, 134, 135, 137, 139, 141, 143, 144, 145, 146, 148, 149, 151, 154, 155, 156, 157, 158, 159, 161, 162, 163, 164, 169, 170, 172, 178, 179, 180, 181`

### Ecorregión E13: "Andes sur costa"

**Método 1:** No supervisado @0.95 (51 bandas)

`0, 8, 9, 10, 11, 12, 13, 14, 17, 24, 27, 28, 38, 39, 40, 41, 42, 46, 49, 50, 71, 72, 78, 80, 89, 90, 91, 92, 93, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 107, 110, 119, 120, 121, 122, 123, 124, 125, 154, 169`

### Ecorregión E14: "Estepa patagónica"

**Método 1:** Boruta top-N (39 bandas)

`22, 154, 51, 74, 38, 67, 99, 2, 163, 11, 12, 165, 45, 69, 177, 127, 76, 172, 40, 92, 80, 24, 134, 37, 23, 106, 133, 123, 170, 26, 136, 52, 180, 77, 81, 94, 101, 89, 9`

### Ecorregión E15: "Bosque subpolar"

**Método 1:** Pool ampliado (87 bandas)

`0, 8, 9, 10, 11, 12, 13, 14, 16, 18, 19, 21, 22, 23, 30, 31, 33, 37, 38, 39, 41, 45, 46, 48, 50, 51, 59, 60, 61, 62, 67, 69, 71, 74, 76, 77, 78, 80, 81, 83, 85, 89, 90, 91, 92, 93, 94, 96, 97, 98, 102, 103, 104, 108, 112, 113, 114, 115, 116, 117, 118, 119, 120, 122, 123, 124, 125, 127, 129, 131, 133, 141, 143, 154, 155, 156, 157, 158, 159, 162, 163, 165, 170, 172, 177, 178, 180`

