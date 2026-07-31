# Hoja de ruta — bands_reduction

Alineada a la cadena de 5 etapas ([`metodologia.md`](metodologia.md)) y al README.

---

## Primera ronda (camino principal)

| Fase | Qué | Etapa método | Entregable |
|------|-----|--------------|------------|
| **F0 — Setup** | Entorno, configs, I/O mosaico 2015 (184 bandas) + ecorregiones + muestras (rutas locales) | — | `src/io`, `configs/global.yaml`, scripts de inspección |
| **F1 — EDA + filtro base** | Correlación / MI; primer recorte | **1** FCBF/CFS | Bandas candidatas post-filtro + reportes EDA |
| **F2 — Clustering espectral** | WaLuDi + BandClust por ecorregión | **2** | 1 banda representativa por cluster |
| **F3 — Refinamiento JM** | Separabilidad con muestras + QA | **3** + QA | Ranking / filtro por ecorregión |
| **F4 — Boruta** | Verificación wrapper + QA | **4** + QA | Set confirmado vs. azar |
| **F5 — Ensamble SHCE** | Consolidación Boruta+JMIM+MDA+RFE + QA | **5** + QA | `results/selected_bands/` por ecorregión + núcleo común |

## Segunda ronda (opcional)

| Fase | Qué | Nota |
|------|-----|------|
| **F6** | Metaheurísticos (GA/PSO/GWO/WOA) y/o autoencoder | Solo comparación; fuera del camino principal |

---

## Scripts CLI previstos

```
scripts/
  01_inspect_mosaic.py
  02_spectral_eda.py
  03_run_selection.py      # orquesta etapas 1–5 por ecorregión
  04_run_qa.py             # verificación transversal (post 3/4/5)
  05_export_selected_bands.py
```

## Criterios a fijar antes de producción

- [ ] Umbral OA/Kappa `⚙️ AJUSTAR` (propuesta: caída ≤ 1–2 %).
- [ ] Umbral JM mínima entre pares de clases.
- [ ] Lista canónica de las 15 ecorregiones (originalmente 8, luego divididas) y YAMLs en `configs/ecoregions/`.
- [ ] Rutas locales de mosaico, ecorregiones y muestras en `configs/global.yaml`.
