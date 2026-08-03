# Selección de Bandas para Clasificación LULC por Ecorregión

Reducción de bandas con **mínima pérdida de información** para clasificación de cobertura y uso de suelo (LULC) del año **2015**, sobre un mosaico de **184 bandas** y **15 ecorregiones** (un modelo por ecorregión). Originalmente eran **8 ecorregiones**, que se dividieron y resultaron en **15**.

> **Estado:** en construcción. Los parámetros marcados con `⚙️ AJUSTAR` deben confirmarse antes de correr en producción.

Metodología detallada: [`docs/metodologia.md`](docs/metodologia.md). Hoja de ruta: [`docs/roadmap.md`](docs/roadmap.md).

---

## 1. Objetivo

Encontrar, para cada ecorregión, el subconjunto **más pequeño** de bandas que conserve la información necesaria para clasificar LULC, y consolidar un **mínimo común** (intersección) y una **unión** entre ecorregiones. Se busca:

- Máxima reducción de dimensionalidad (de 184 → N bandas, N lo menor posible).
- Mínima pérdida de información / separabilidad de clases.
- Un procedimiento **replicable e idéntico en las 15 ecorregiones**, aunque el subconjunto final pueda diferir entre ellas.
- Interpretabilidad física de cada banda seleccionada (importante para LULC).
- Núcleo común (intersección), cobertura total (unión) y diagnóstico por correlación de bandas descartadas.

---

## 2. Enfoque metodológico

Se descartan los métodos **embedded** por decisión de diseño. El foco es **no supervisado** y **semi-supervisado**, aprovechando que existen *algunas* muestras etiquetadas.

Las **3 etapas** son una cadena (no métodos compitiendo): clustering espectral → refinamiento JM → Boruta. Luego se consolidan **intersección** y **unión** entre ecorregiones. Verificación transversal tras JM, Boruta y la consolidación. Detalle en [`docs/metodologia.md`](docs/metodologia.md).

### Método principal (recomendado)

**Clustering espectral no supervisado + refinamiento JM + Boruta + consolidación entre ecorregiones.**

| Paso | Qué hace | Por qué |
|------|----------|---------|
| Clustering | Agrupa las 184 bandas por redundancia (MI / correlación) y elige una banda representativa por grupo | No depende de etiquetas; conserva el sentido físico |
| JM | Prioriza separabilidad por ecorregión sobre las 184 bandas y sobre el resultado del clustering | Contrasta set completo vs. reducido con pocas muestras |
| Boruta | Confirma relevancia real de los candidatos | Verifica frente al azar |
| Consolidación | Intersección (mínimo común), unión, correlación de bandas fuera de esos sets, evaluación de la unión | Núcleo compartido + cobertura total + diagnóstico de descartes |

Candidatos de selección (primera ronda):

- **WaLuDi** / **BandClust** — clustering espectral (etapa 1).
- **Jeffries-Matusita** — refinamiento semi-supervisado (etapa 2).
- **Boruta** — wrapper de verificación (etapa 3).

Metaheurísticos (GA / PSO / GWO / WOA) y **autoencoder** quedan como **ronda 2 opcional**.

---

## 3. Cómo verificar la pérdida de información

Tres niveles, de menos a más costoso (control de calidad tras etapas 2 y 3, y sobre intersección/unión):

1. **Redundancia / información** (sin etiquetas)
   - Matriz de correlación espectral antes vs. después.
   - Información mutua promedio del subconjunto.
   - Correlación de bandas **fuera** de la intersección / unión.
2. **Separabilidad de clases** (con muestras)
   - Distancia **Jeffries-Matusita** o **Bhattacharyya** por par de clases.
3. **Impacto en clasificación** (con muestras)
   - Random Forest con 184 bandas vs. subconjunto reducido (por ecorregión, intersección y unión).
   - Métricas: **Overall Accuracy**, **Kappa**, **Jaccard**, con validación cruzada.

Criterio de aceptación sugerido `⚙️ AJUSTAR`: conservar el subconjunto más pequeño cuya caída de OA/Kappa respecto al set completo sea `≤ 1–2 %` y cuya separabilidad JM mínima entre clases se mantenga por encima de un umbral.

---

## 4. Estructura del repositorio

En Git se versionan código, configs, docs y tests. Los rasters/muestras/resultados pesados **no** se versionan (rutas locales vía config).

```
bands_reduction/
├── README.md
├── requirements.txt
├── .gitignore
├── configs/                  ← YAML por ecorregión y config global
│   ├── global.yaml
│   └── ecoregions/
├── src/
│   ├── io/                   ← lectura de raster y muestras
│   ├── selection/            ← WaLuDi, BandClust, JM, Boruta
│   ├── evaluation/           ← MI, JM/Bhattacharyya, RF, correlación, métricas
│   ├── pipeline/             ← orquestación (etapas 1–3 + consolidación)
│   └── utils/                ← logging, config, helpers
├── scripts/                  ← entrypoints CLI
├── test/                     ← tests unitarios / de integración
├── notebooks/                ← exploración (opcional, local)
├── results/                  ← salidas locales (NO se versiona)
│   ├── figures/
│   ├── tables/
│   └── selected_bands/
└── docs/
    ├── metodologia.md
    └── roadmap.md
```

Rutas de datos (mosaico 2015, muestras, ecorregiones, interim) se declaran en `configs/global.yaml` apuntando a directorios **fuera** de este repo:

| Input | Ruta |
|-------|------|
| Mosaico 184 bandas (**año 2015**) | `/home/lserey/mapbiomas_land/test/mosaics/mosaics_184bands` |
| Ecorregiones (valores 1–15) | `/home/lserey/mapbiomas_land/ancillary_data/ecorregiones_col3_30m_alineado_lulc.tif` |

---

## 5. Hoja de ruta

- [ ] **F0 — Setup.** Repo, entorno, lectura del mosaico 2015 de 184 bandas, carga de muestras.
- [ ] **F1 — EDA espectral.** Correlación / MI sobre las 184 bandas.
- [ ] **F2 — Clustering espectral.** WaLuDi / BandClust por ecorregión (etapa 1).
- [ ] **F3 — Refinamiento JM.** Separabilidad sobre 184 y sobre clustering (etapa 2) + QA.
- [ ] **F4 — Wrapper Boruta.** Verificación (etapa 3) + QA → \(S_e\) por ecorregión.
- [ ] **F5 — Consolidación.** Intersección, unión, correlación fuera de sets, evaluación de la unión + QA.
- [ ] **F6 (opcional).** Metaheurísticos / autoencoder como comparación (ronda 2).

Detalle en [`docs/roadmap.md`](docs/roadmap.md).

---

## 6. Inicio rápido

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Inspeccionar el mosaico (ruta local vía config o flag)
python scripts/01_inspect_mosaic.py --config configs/global.yaml

# 2. EDA de redundancia
python scripts/02_spectral_eda.py --config configs/global.yaml

# 3. Selección por ecorregión (cadena etapas 1–3)
python scripts/03_run_selection.py --ecoregion configs/ecoregions/eco_01.yaml

# 4. Consolidación entre ecorregiones (intersección / unión)
python scripts/05_consolidate_ecoregions.py --config configs/global.yaml
```
