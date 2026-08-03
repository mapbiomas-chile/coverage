# Metodología de selección de bandas — LULC por ecorregión

Reducción de bandas con mínima pérdida de información para LULC del año **2015**, sobre un mosaico de **184 bandas** y **15 ecorregiones** (un modelo por ecorregión). Originalmente eran **8 ecorregiones**, que se dividieron y resultaron en **15**.

> Referencia: NotebookLM del proyecto

---

## Idea general

Las **3 etapas** son una **cadena**, no métodos compitiendo. La salida de cada una alimenta a la siguiente: cada método aporta según su rol (agrupar redundancia, afinar con muestras, confirmar relevancia). El procedimiento es **idéntico en las 15 ecorregiones**, aunque el subconjunto final pueda diferir entre ellas.

Al cerrar la cadena por ecorregión se consolidan resultados entre todas:

| Producto | Qué es |
|----------|--------|
| **Selección por ecorregión** \(S_e\) | Subconjunto de bandas elegido en la ecorregión \(e\) |
| **Intersección (mínimo común)** \(\bigcap_e S_e\) | Bandas presentes en **todas** las ecorregiones |
| **Unión** \(\bigcup_e S_e\) | Bandas presentes en **al menos una** ecorregión |

Además:

- Evaluar con **correlación** las bandas que **no** están en la intersección ni en la unión (respecto al espacio de 184), para entender qué se descartó y si era redundante.
- Evaluar la **unión** entre todas las ecorregiones (separabilidad, impacto en clasificación y redundancia residual).

```
184 bandas
    │
    ▼
[1] Clustering espectral (WaLuDi + BandClust)
    → 1 banda representativa por grupo
    │
    ▼
[2] Refinamiento JM (semi-supervisado)
    → prioriza separabilidad por ecorregión
    → se aplica sobre las 184 bandas y sobre el resultado del clustering
    │  └── QA transversal
    ▼
[3] Boruta (wrapper)
    → confirma relevancia real
    │  └── QA transversal
    ▼
Selección por ecorregión S_e
    │
    ▼
Consolidación entre ecorregiones
    ├── intersección (mínimo común)
    ├── unión
    ├── correlación de bandas fuera de intersección / unión
    └── evaluación de la unión global
         └── QA transversal
```

---

## Las 3 etapas (por ecorregión)

### 1 · Clustering espectral (no supervisado)

- **Métodos:** WaLuDi + BandClust.
- **Rol:** agrupa las 184 bandas por información mutua / divergencia y elige **una banda representativa por grupo**.
- **Por qué:** reduce redundancia conservando el sentido físico de cada banda (clave para LULC) y no depende de muestras.

### 2 · Refinamiento semi-supervisado (Jeffries-Matusita)

- **Método:** separabilidad Jeffries-Matusita con las muestras etiquetadas.
- **Rol:** prioriza las bandas que mejor separan las clases presentes en cada ecorregión.
- **Entradas comparadas:**
  1. las **184 bandas** completas, y
  2. el subconjunto resultante del **clustering** (etapa 1).
- **Por qué:** aprovecha las pocas muestras disponibles sin depender de ellas como motor principal; permite contrastar el aporte del clustering frente al set completo.

### 3 · Wrapper de verificación (Boruta)

- **Método:** Boruta.
- **Rol:** confirma qué bandas son realmente relevantes (robusto frente al azar) a partir de los candidatos priorizados en JM.
- **Por qué:** es supervisado y algo caro; se usa para **verificar**, no para seleccionar desde cero.

Salida de esta cadena por ecorregión: el conjunto \(S_e\).

---

## Consolidación entre ecorregiones

Tras obtener \(S_e\) para \(e = 1,\ldots,15\):

1. **Intersección (mínimo común)** — \(\bigcap_e S_e\): núcleo de bandas compartido por todas las ecorregiones.
2. **Unión** — \(\bigcup_e S_e\): cobertura total de bandas seleccionadas en al menos una ecorregión.
3. **Bandas fuera de intersección / unión** — respecto a las 184:
   - fuera de la unión = descartadas en todas las ecorregiones;
   - en la unión pero fuera de la intersección = bandas específicas de algunas ecorregiones.
   Evaluarlas con **correlación / información mutua** frente a las bandas retenidas, para verificar si el descarte es por redundancia o por irrelevancia local.
4. **Evaluación de la unión global** — medir pérdida de información y desempeño de clasificación del set unión vs. 184 bandas (y vs. intersección), con el mismo QA transversal.

---

## Verificación transversal (control de calidad)

No es una etapa más: se aplica **después de las etapas 2 y 3**, y también sobre la **intersección** y la **unión** consolidadas, para medir la pérdida de información frente a las 184 bandas completas.

| Nivel | Qué mide | Cómo |
|-------|----------|------|
| Redundancia / información | Correlación e información mutua antes vs. después | Sin etiquetas |
| Separabilidad de clases | Jeffries-Matusita / Bhattacharyya por par de clases | Con muestras |
| Impacto en clasificación | Random Forest + CV → OA, Kappa, Jaccard | Con muestras |

**Criterio de aceptación sugerido** `⚙️ AJUSTAR`: conservar el subconjunto más pequeño cuya caída de OA/Kappa sea **≤ 1–2 %**.

---

## Resumen de métodos

| Método | ¿Entra? | Rol |
|--------|---------|-----|
| BandClust / WaLuDi | Sí | Etapa 1 — clustering no supervisado |
| Jeffries-Matusita | Sí | Etapa 2 — refinamiento semi-supervisado (184 y post-clustering) |
| Boruta (wrapper) | Sí | Etapa 3 — verificación de relevancia |
| Intersección / unión entre ecorregiones | Sí | Consolidación post-selección + evaluación |
| Metaheurísticos (GA / PSO / GWO / WOA) | Opcional | Ronda 2 |
| Autoencoder (deep learning) | Opcional | Ronda 2 — solo comparación |
| FCBF / CFS (filtro base) | No | Fuera del camino principal (reemplazado por clustering directo) |
| SHCE (ensamble) | No | Fuera del camino principal; consolidación vía intersección/unión |
| Embedded (Lasso, árboles, etc.) | No | Excluido por decisión de diseño |

**Cuántos probar:** 3 etapas en la primera ronda, más consolidación intersección/unión. Metaheurísticos y autoencoder quedan como pista opcional (ronda 2), fuera del camino principal por su costo y su riesgo de sobreajuste con pocas muestras.
