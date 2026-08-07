# Jeffries-Matusita (JM) y Boruta — guía del pipeline

Complemento de [`metodologia.md`](metodologia.md) e [`INFORME_BANDAS.md`](INFORME_BANDAS.md).

Corridas de referencia (María Elisa): `/home/lserey/mapbiomas_land/tmp/JM_test_ME/`

---

## 1. Dónde entran en la cadena completa

```
184 bandas (mosaico 2015)
    │
    ▼  NO SUPERVISADO (scripts 06→10→11→12)
Muestreo por eco → |r| → clustering → representantes + family rescue
    │  (~100–130 bandas candidatas por ecorregión)
    │
    │  + muestras train Col2 (X = reflectancias, y = clase LULC)
    ▼  SUPERVISADO — Etapa 3
Jeffries-Matusita (JM): ranking por separabilidad de clases
    │
    ▼  SUPERVISADO — Etapa 4 (opcional)
Boruta: confirmación vs. variables sombra (Random Forest)
    │
    ▼  QA
Random Forest + CV → OA / Kappa (¿caída ≤ 1–2 % vs 184 bandas?)
    │
    ▼
Lista final de bandas por ecorregión
```

**Importante:** JM y Boruta **requieren etiquetas**. El clustering previo **no** las usa; reduce redundancia espectral antes de evaluar utilidad para clasificar.

---

## 2. Jeffries-Matusita (JM)

### 2.1 Intuición

Para una banda y dos clases A y B, JM responde:

> *Si miro solo los valores de esta banda, ¿qué tan fácil es distinguir A de B?*

- Distribuciones **muy separadas** y **poco solapadas** → JM **alto** (cerca de 2).
- Distribuciones **superpuestas** → JM **bajo** (cerca de 0).

En teledetección se asume a menudo que los valores por clase son **aproximadamente normales** (campana de Gauss). Con medias μₐ, μᵦ y varianzas σₐ², σᵦ² se calcula un índice por par de clases.

### 2.2 Fórmula (dos clases, una banda)

Primero el **coeficiente de Bhattacharyya** (solapamiento entre campanas):

```
BC = sqrt( 2·σₐ²·σᵦ² / (σₐ² + σᵦ²) ) · exp( -(μₐ − μᵦ)² / (4·(σₐ² + σᵦ²)) )
```

Luego la **distancia Jeffries-Matusita**:

```
JM(A,B) = sqrt( 2 · (1 − BC) )
```

**Rango:** 0 (no separables) a **√2 ≈ 1.414** en esta formulación; en muchos softwares se reporta en escala **0–2** (valores ~2 = separación excelente). En nuestros CSV aparece como `mean_jm` en ese rango ampliado.

**Qué empuja JM hacia arriba**

| Situación | Efecto |
|-----------|--------|
| \|μₐ − μᵦ\| grande (medias lejos) | ↑ JM |
| σₐ², σᵦ² pequeñas (clases compactas) | ↑ JM |
| Mucho solapamiento de colas | ↓ JM |

### 2.3 Ejemplo numérico mínimo (2 clases, 1 banda)

Clase **Salar** vs **Matorral** en banda `gv_median` (valores ficticios):

| Clase | n | media μ | varianza σ² |
|-------|--:|--------:|--------------:|
| Salar | 35 | 0.15 | 0.002 |
| Matorral | 27 | 0.45 | 0.008 |

1. Diferencia de medias: (0.45 − 0.15)² = 0.09  
2. σₐ² + σᵦ² = 0.010 → término exponencial penaliza solapamiento  
3. BC ≈ 0.55 (mucho solapamiento aún)  
4. **JM ≈ 0.95** → separación **moderada**, no excelente  

Si otra banda tiene μ = 0.14 vs 0.82 y varianzas similares, JM sube (p. ej. > 1.3) → mejor candidata para discriminar ese par.

### 2.4 Paso a paso en el pipeline (por ecorregión)

| Paso | Acción |
|------|--------|
| 1 | Cargar muestras **train** Col2 dentro de la ecorregión (máscara Col3). |
| 2 | Opcional: excluir clases 33 (agua) y 34 (hielo/nieve). |
| 3 | Construir matriz **X** (n_píxeles × n_bandas) y vector **y** (clase). |
| 4 | Para **cada banda**, para **cada par de clases** (i, j), calcular JM(i,j). |
| 5 | Resumir por banda: **mean_jm** = promedio sobre todos los pares; **min_jm** = peor par. |
| 6 | Ordenar bandas por **mean_jm** descendente → `jm_ranking.csv`. |
| 7 | Aplicar **corte** (a calibrar con QA): p. ej. mean_jm ≥ 1.0. |

**Variantes en JM_test_ME**

- `184bands_ecorregion/` — JM sobre las **184** bandas.  
- `clustering_again_pe/.../jm_from_clustering/` — JM solo sobre **representantes PE** @ 0.95 (**recomendado**: candidatos ya sin redundancia espectral).

**Salidas:** `jm_ranking.csv`, `jm_summary.json`, `band_list_jm.json`

### 2.5 Cómo leer nuestros resultados

En E2 (Desierto), top JM post-clustering:

1. gv_median (1.34)  
2. gvs_min (1.34)  
3. gv_min (1.34)  

Familia **gv/gvs** domina la separabilidad en desierto — coherente ecológicamente.

Corte **mean_jm ≥ 1.0** sobre reps @ 0.95 → ~**19 bandas** en E2, ~**26** de media nacional (vs ~123 reps de entrada).

---

## 3. Boruta

### 3.1 Intuición

Boruta pregunta:

> *¿Esta banda aporta a predecir la clase **más** que una versión aleatoria (ruido)?*

No mira solo separabilidad pairwise como JM; entrena un **Random Forest** con **todas** las bandas candidatas y compara importancias reales con **shadow features** (copias permutadas = azar).

### 3.2 Shadow features (variables sombra)

Por cada banda real **B**, Boruta crea **B_shadow**:

1. Toma los valores de **B** en las muestras.  
2. Los **baraja aleatoriamente** (rompe relación con y, mantiene la distribución marginal).  
3. Entrena RF con `[bandas reales..., B_shadow₁, B_shadow₂, ...]`.  
4. Si importancia(B_real) **≤** importancia(B_shadow) en la mayoría de iteraciones → **Rejected**.  
5. Si **>** consistentemente → **Confirmed**.  
6. Zona gris → **Tentative** (reglas extra con hit_rate).

**Idea clave:** la sombra es un **control de azar** con la misma forma estadística que la banda, pero sin información de clase.

### 3.3 Ejemplo numérico mínimo (3 bandas, pocas muestras)

4 muestras, 3 clases simplificadas:

| Muestra | Clase | band_A | band_B | band_C |
|--------:|-------|-------:|-------:|-------:|
| 1 | Salar | 0.1 | 0.5 | 0.3 |
| 2 | Salar | 0.2 | 0.6 | 0.9 |
| 3 | Matorral | 0.8 | 0.7 | 0.4 |
| 4 | Infra | 0.5 | 0.2 | 0.2 |

- **band_A:** valores distintos por clase → RF la usa → importancia **alta** → gana a su sombra → **Confirmed**.  
- **band_C:** muestra 2 (Salar) tiene 0.9, ruido; solapamiento → importancia **media** → **Tentative**.  
- **band_B:** poca relación con y → importancia similar a sombra → **Rejected**.

En la práctica hay **decenas de sombras** (una por banda) y **50+ iteraciones**; el criterio es estadístico (percentil `perc`, test `alpha`).

### 3.4 Paso a paso en el pipeline (por ecorregión)

| Paso | Acción |
|------|--------|
| 1 | Mismas muestras train que JM (X, y por eco). |
| 2 | **Input:** columnas = representantes PE @ 0.95 (no 184 bandas). |
| 3 | Inicializar RF (`n_estimators=200`, etc.). |
| 4 | Por iteración: crear sombras, entrenar, registrar importancias Z-score. |
| 5 | Clasificar cada banda: Confirmed / Rejected / Tentative. |
| 6 | Mantener tentativas con **hit_rate ≥ umbral** (0.25–0.50 según corrida). |
| 7 | Exportar `boruta_decisions.csv`, `band_list_boruta.json`. |

**Parámetros probados (JM_test_ME)**

| Run | perc | alpha | tentative min | Comportamiento |
|-----|-----:|------:|--------------:|----------------|
| boruta_1 | 100 | 0.05 | 0.50 | Muy estricto (muchos 0 kept) |
| boruta_2 | 90 | 0.10 | 0.25 | Muy relajado (E2: 110 kept) |
| boruta_3 | 95 | 0.05 | 0.40 | Intermedio, aún estricto |

**Salidas:** `E{id}/0.95/boruta_summary.json`, `boruta_decisions.csv`, `band_list_boruta.json`

### 3.5 Por qué fue inestable en nuestras pruebas

- **Pocas muestras** por ecorregión (1 punto/polígono en Col2 train).  
- Con **n pequeño**, las sombras y el RF tienen alta varianza → saltos 0 vs 110 bandas.  
- **Próximo paso:** muestras estratificadas (~293k puntos en `184_bands_stratified_train`) y re-correr Boruta.

---

## 4. JM vs Boruta — cuándo usar cada uno

| | **JM** | **Boruta** |
|---|--------|------------|
| Pregunta | ¿Separa pares de clases? | ¿Supera al azar en un RF multibanda? |
| Tipo | Filtro / ranking por separabilidad | Wrapper de confirmación |
| Costo computacional | Bajo | Alto (muchas iteraciones RF) |
| Salida | Ranking + umbral continuo | confirmed / rejected / tentative |
| Mejor momento | Justo después del clustering | Después de JM, para verificar |
| Estabilidad (nuestros datos) | Alta | Baja sin más muestras |

**Pipeline recomendado hoy:**

```
Clustering PE (@ 0.90) → JM (rank + corte) → [opcional Boruta] → QA RF
```

---

## 5. Archivos útiles para revisar

| Contenido | Ruta |
|-----------|------|
| JM por eco (184 bandas) | `JM_test_ME/184bands_ecorregion/by_ecoregion/E*/jm_ranking.csv` |
| JM post-clustering | `JM_test_ME/clustering_again_pe/E*/2015/eco_merged/0.95/jm_from_clustering/` |
| Boruta 1/2/3 | `JM_test_ME/boruta_{1,2,3}/E*/0.95/` |
| Tabla comparativa Boruta | [`boruta_comparison.csv`](boruta_comparison.csv) |
| Tabla comparativa JM | [`jm_comparison.csv`](jm_comparison.csv) |
| Informe no supervisado | [`INFORME_BANDAS.md`](INFORME_BANDAS.md) |

---

## 6. Pendientes (mosaicos en revisión)

- Repetir extracción de muestras y corridas JM/Boruta con **mosaicos 2015 corregidos**.  
- Fijar umbral JM con QA (OA/Kappa).  
- Versionar scripts JM/Boruta en el repo (`bands_reduction/scripts/`).
