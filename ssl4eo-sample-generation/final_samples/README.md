# SSL4EO final samples — 2×2 / 3×3 rectangles (scale300)

Selecciones separadas por **huso UTM** y **tamaño de rectángulo**. Formatos: GeoJSON, GeoPackage y CSV (sin shapefile).

```text
final_samples/
├── UTM18/
│   ├── homogeneo_2x2/     ← tipos espaciales homogéneos (estable/anual homogénea)
│   │   ├── seleccion_grilla_ssl4eo_muestras_homogeneo_2x2_UTM18_scale300.geojson
│   │   ├── seleccion_grilla_ssl4eo_muestras_homogeneo_2x2_UTM18_scale300.gpkg
│   │   ├── seleccion_grilla_ssl4eo_muestras_homogeneo_2x2_UTM18_scale300.csv
│   │   └── seleccion_*_taxonomia_n3.csv
│   └── mixto_3x3/         ← tipos simple/media + transición
│       └── seleccion_grilla_ssl4eo_muestras_mixto_3x3_UTM18_scale300.*
└── UTM19/
    ├── homogeneo_2x2/
    └── mixto_3x3/
```

Generado con `scripts/02_rectangle_selection.py` + `scripts/03_annotate_grid_taxonomy.py`.

Meta nacional scale300: ~300–350 rectángulos en total (suma de las 4 selecciones por huso/tamaño).
