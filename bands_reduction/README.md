# Selección de Bandas para Clasificación LULC por Ecorregión

Reducción de bandas con **mínima pérdida de información** para clasificación de cobertura y uso de suelo (LULC), sobre un mosaico de **184 bandas** y **8 ecorregiones** (un modelo por ecorregión).

> **Estado:** en construcción. Los parámetros marcados con `⚙️ AJUSTAR` deben confirmarse antes de correr en producción.

Metodología detallada: [`docs/metodologia.md`](docs/metodologia.md). Hoja de ruta: [`docs/roadmap.md`](docs/roadmap.md).

---

## 1. Objetivo

Encontrar, para cada ecorregión, el subconjunto **más pequeño** de bandas que conserve la información necesaria para clasificar LULC, verificando explícitamente la pérdida de información. Se busca:

- Máxima reducción de dimensionalidad (de 184 → N bandas, N lo menor posible).
- Mínima pérdida de información / separabilidad de clases.
- Un procedimiento **replicable e idéntico en las 8 ecorregiones**, aunque el subconjunto final pueda diferir entre ellas.
- Interpretabilidad física de cada banda seleccionada (importante para LULC).

---

## 2. Enfoque metodológico

Se descartan los métodos **embedded** por decisión de diseño. El foco es **no supervisado** y **semi-supervisado**, aprovechando que existen *algunas* muestras etiquetadas.

Las **5 etapas** son una cadena (no métodos compitiendo): filtro base → clustering espectral → refinamiento JM → Boruta → ensamble SHCE. Verificación transversal tras las etapas 3, 4 y 5. Detalle en [`docs/metodologia.md`](docs/metodologia.md).

### Método principal (recomendado)

**Clustering espectral no supervisado + verificación semi-supervisada.**

| Paso | Qué hace | Por qué |
|------|----------|---------|
| Selección | Agrupa las 184 bandas por redundancia (información mutua / correlación) y elige una banda representativa por grupo | No depende de etiquetas; conserva el sentido físico de la banda |
| Verificación | Usa las muestras etiquetadas para medir separabilidad antes/después | Cierra el loop: confirma que la reducción no degrada las clases |

Candidatos de selección (primera ronda):

- **FCBF / CFS** — filtro base (etapa 1).
- **WaLuDi** / **BandClust** — clustering espectral (etapa 2).
- **Jeffries-Matusita** — refinamiento semi-supervisado (etapa 3).
- **Boruta** — wrapper de verificación (etapa 4).
- **SHCE** — ensamble final (etapa 5).

Metaheurísticos (GA / PSO / GWO / WOA) y **autoencoder** quedan como **ronda 2 opcional**.

---

## 3. Cómo verificar la pérdida de información

Tres niveles, de menos a más costoso (control de calidad tras etapas 3, 4 y 5):

1. **Redundancia / información** (sin etiquetas)
   - Matriz de correlación espectral antes vs. después.
   - Información mutua promedio del subconjunto.
2. **Separabilidad de clases** (con muestras)
   - Distancia **Jeffries-Matusita** o **Bhattacharyya** por par de clases.
3. **Impacto en clasificación** (con muestras)
   - Random Forest con 184 bandas vs. subconjunto reducido.
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
│   ├── selection/            ← FCBF/CFS, WaLuDi, BandClust, JM, Boruta, SHCE
│   ├── evaluation/           ← MI, JM/Bhattacharyya, RF, métricas
│   ├── pipeline/             ← orquestación end-to-end (etapas 1–5)
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

Rutas de datos (mosaico, muestras, interim) se declaran en `configs/global.yaml` apuntando a un directorio **fuera** de este repo.

---

## 5. Hoja de ruta

- [ ] **F0 — Setup.** Repo, entorno, lectura del mosaico de 184 bandas, carga de muestras.
- [ ] **F1 — EDA espectral + filtro base.** Correlación / MI; etapa 1 (FCBF/CFS).
- [ ] **F2 — Clustering espectral.** WaLuDi / BandClust por ecorregión (etapa 2).
- [ ] **F3 — Refinamiento semi-supervisado.** Separabilidad JM con muestras (etapa 3) + QA.
- [ ] **F4 — Wrapper Boruta.** Verificación (etapa 4) + QA.
- [ ] **F5 — Ensamble SHCE.** Consolidación final por ecorregión (etapa 5) + QA.
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

# 3. Selección por ecorregión (cadena etapas 1–5)
python scripts/03_run_selection.py --ecoregion configs/ecoregions/eco_01.yaml
```
