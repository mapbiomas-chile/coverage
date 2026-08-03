# Hoja de ruta — bands_reduction

Alineada a la cadena de 3 etapas + consolidación entre ecorregiones ([`metodologia.md`](metodologia.md)) y al README.

---

## Primera ronda (camino principal)

| Fase | Qué | Etapa método | Entregable |
|------|-----|--------------|------------|
| **F0 — Setup** | Entorno, configs, I/O mosaico 2015 (184 bandas) + ecorregiones + muestras (rutas locales) | — | `src/io`, `configs/global.yaml`, scripts de inspección |
| **F1 — EDA espectral** | Correlación / MI sobre las 184 bandas | — | Reportes EDA de redundancia |
| **F2 — Clustering espectral** | WaLuDi + BandClust por ecorregión | **1** | 1 banda representativa por cluster |
| **F3 — Refinamiento JM** | Separabilidad sobre 184 bandas y sobre el resultado del clustering + QA | **2** + QA | Ranking / filtro por ecorregión |
| **F4 — Boruta** | Verificación wrapper + QA | **3** + QA | Set \(S_e\) confirmado por ecorregión |
| **F5 — Consolidación** | Intersección (mínimo común), unión, correlación de bandas fuera de esos sets, evaluación de la unión | post | Núcleo común, unión global, reportes de correlación y QA |

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
  03_run_selection.py           # orquesta etapas 1–3 por ecorregión
  04_run_qa.py                  # verificación transversal (post 2/3 y consolidación)
  05_consolidate_ecoregions.py  # intersección, unión, correlación fuera de sets
  06_export_selected_bands.py
```

## Criterios a fijar antes de producción

- [ ] Umbral OA/Kappa `⚙️ AJUSTAR` (propuesta: caída ≤ 1–2 %).
- [ ] Umbral JM mínima entre pares de clases.
- [ ] Lista canónica de las 15 ecorregiones (originalmente 8, luego divididas) y YAMLs en `configs/ecoregions/`.
- [ ] Rutas locales de mosaico, ecorregiones y muestras en `configs/global.yaml`.
