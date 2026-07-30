# Metodología de selección de bandas — LULC por ecorregión

Reducción de bandas con mínima pérdida de información sobre un mosaico de **184 bandas** y **8 ecorregiones** (un modelo por ecorregión).

> Referencia: NotebookLM del proyecto

---

## Idea general

Las **5 etapas** son una **cadena**, no 5 métodos compitiendo. La salida de cada una alimenta a la siguiente: cada método aporta según su rol (quitar redundancia, agrupar, afinar con muestras, confirmar, consolidar). Esto permite una reducción reproducible en las 8 ecorregiones, porque el paso final es un **ensamble estable** y no depende de un solo método.

```
184 bandas
    │
    ▼
[1] Filtro base (FCBF / CFS)          → quita redundancia obvia
    │
    ▼
[2] Clustering espectral (WaLuDi + BandClust) → 1 banda por grupo
    │
    ▼
[3] Refinamiento JM (semi-supervisado) → prioriza separabilidad por ecorregión
    │  └── QA transversal
    ▼
[4] Boruta (wrapper)                   → confirma relevancia real
    │  └── QA transversal
    ▼
[5] Ensamble SHCE                      → subconjunto final estable
       └── QA transversal
```

---

## Las 5 etapas (primera ronda)

### 1 · Filtro base (no supervisado)

- **Métodos:** FCBF o CFS.
- **Rol:** quita la redundancia obvia entre bandas de forma rápida y barata. Primer recorte del espacio de 184 bandas.
- **Por qué:** ataca directamente la redundancia; no requiere etiquetas.

### 2 · Clustering espectral (no supervisado)

- **Métodos:** WaLuDi + BandClust.
- **Rol:** agrupa las bandas restantes por información mutua / divergencia y elige una banda representativa por grupo.
- **Por qué:** conserva el sentido físico de cada banda (clave para LULC) y no depende de muestras.

### 3 · Refinamiento semi-supervisado

- **Método:** separabilidad Jeffries-Matusita con las muestras etiquetadas.
- **Rol:** reordena y filtra los candidatos priorizando las bandas que mejor separan las clases presentes en cada ecorregión.
- **Por qué:** aprovecha las pocas muestras disponibles sin depender de ellas como motor principal.

### 4 · Wrapper de verificación

- **Método:** Boruta.
- **Rol:** confirma qué bandas son realmente relevantes (robusto frente a azar).
- **Por qué:** es supervisado y algo caro; se usa para **verificar**, no para seleccionar desde cero.

### 5 · Ensamble final

- **Método:** SHCE (estabilidad–heterogeneidad–correlación), que agrega Boruta, JMIM, MDA y RFE.
- **Rol:** consolida todo lo anterior en un subconjunto estable y robusto.
- **Por qué:** un ensamble reduce el riesgo de que un solo método elija bandas por azar — esencial para replicar de forma consistente en las 8 ecorregiones. Mejor apuesta para el subconjunto final.

---

## Verificación transversal (control de calidad)

No es una etapa más: se aplica **después de las etapas 3, 4 y 5** para medir la pérdida de información frente a las 184 bandas completas.

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
| BandClust / WaLuDi | Sí | Etapa 2 — motor no supervisado |
| FCBF / CFS (filtro) | Sí | Etapa 1 — línea base |
| Boruta (wrapper) | Sí | Etapa 4 — verificación |
| SHCE (ensamble) | Sí | Etapa 5 — consolidación, mejor apuesta final |
| Metaheurísticos (GA / PSO / GWO / WOA) | Opcional | Ronda 2 |
| Autoencoder (deep learning) | Opcional | Ronda 2 — solo comparación |
| Embedded (Lasso, árboles, etc.) | No | Excluido por decisión de diseño |

**Cuántos probar:** 5 en la primera ronda (etapas 1–5). Metaheurísticos y autoencoder quedan como pista opcional (ronda 2), fuera del camino principal por su costo y su riesgo de sobreajuste con pocas muestras.
