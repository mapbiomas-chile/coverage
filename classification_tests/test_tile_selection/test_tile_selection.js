// =============================================================================
// MapBiomas Chile - Selección de Tiles de Prueba
// Colección 3 | MGRS Grid | tiles representativos
//
// Parámetros editables por el usuario:
// - NUM_TILES_SELECCIONAR: número de tiles a seleccionar.
// - UMBRAL_OVERLAP_PCT: porcentaje mínimo de solapamiento con Landcover.
// =============================================================================


// ── 0. PARÁMETROS EDITABLES POR EL USUARIO ───────────────────────────────────

// Número de tiles que quieres seleccionar.
// Ejemplos: 5, 10, 15, 20.
var NUM_TILES_SELECCIONAR = 6;

// Porcentaje mínimo de solapamiento del tile con el Landcover.
// Ejemplos:
// 10 = acepta tiles con baja cobertura terrestre.
// 30 = valor recomendado para excluir tiles muy oceánicos.
// 50 = selección más estricta.
// 80 = solo tiles muy cubiertos por Landcover.
var UMBRAL_OVERLAP_PCT = 50;

// Año de referencia del Landcover.
var YEAR_REF = 2024;

// Escala de análisis para calcular área por clase.
// 300 m es rápido. 30 m es más preciso, pero mucho más lento.
var ANALYSIS_SCALE = 300;

// Carpeta de exportación en Google Drive.
var DRIVE_FOLDER = 'MapBiomas_Chile';

// Nombre base de exportación.
var EXPORT_PREFIX =
  'MapBiomas_C03_TestTiles_' +
  NUM_TILES_SELECCIONAR +
  '_overlap_' +
  UMBRAL_OVERLAP_PCT +
  'pct';


// ── 1. ASSETS ────────────────────────────────────────────────────────────────

var tilesRaw = ee.FeatureCollection(
  'projects/mapbiomas-chile/assets/LULC/COLLECTION-03/ANCILLARY_DATA/Tiles_Chile_Sentinel'
);

var lulc = ee.Image(
  'projects/mapbiomas-chile/assets/LULC/COLLECTION-02/CLASSIFICATIONS/classification-final/clasificacion-final-2'
);

var BAND_NAME = 'classification_' + YEAR_REF;

var lulc2024 = lulc.select(BAND_NAME).rename('lulc');

print('Tiles totales originales:', tilesRaw.size());
print('Bandas LULC disponibles:', lulc.bandNames());
print('Banda usada:', BAND_NAME);
print('Número de tiles solicitado:', NUM_TILES_SELECCIONAR);
print('Umbral mínimo de overlap LULC (%):', UMBRAL_OVERLAP_PCT);


// ── 2. PALETA Y LEYENDA MAPBIOMAS CHILE ──────────────────────────────────────

var clasesValidas = [
  3,  59, 60, 67,
  11, 12, 63, 66,
  15, 18,  9, 23,
  61, 29, 24, 25,
  33, 34, 27
];

// Para calcular el porcentaje de clases cubiertas,
// se excluye 27 porque corresponde a "Sin observación / No clasificado".
var clasesEvaluables = [
  3,  59, 60, 67,
  11, 12, 63, 66,
  15, 18,  9, 23,
  61, 29, 24, 25,
  33, 34
];

var mapbiomasPalette = [
  '#1f8d49', // 3  Bosque
  '#1f8d49', // 59 Bosque primario
  '#5cb85d', // 60 Bosque secundario
  '#c8ffb4', // 67 Bosque achaparrado
  '#519799', // 11 Humedal
  '#d6bc74', // 12 Pastizal
  '#ebf8b5', // 63 Estepa
  '#a89358', // 66 Matorral
  '#edde8e', // 15 Pastura
  '#E974ED', // 18 Agricultura
  '#7a5900', // 9  Silvicultura
  '#ffa07a', // 23 Arena, playa y duna
  '#f5d5d5', // 61 Salar
  '#ffaa5f', // 29 Afloramiento rocoso
  '#d4271e', // 24 Infraestructura
  '#db4d4f', // 25 Otra área sin vegetación
  '#2532e4', // 33 Río, lago u océano
  '#93dfe6', // 34 Hielo y nieve
  '#ffffff'  // 27 Sin observación / No clasificado
];

var CLASS_NAMES = ee.Dictionary({
  '3':  'Bosque',
  '59': 'Bosque primario',
  '60': 'Bosque secundario',
  '67': 'Bosque achaparrado',
  '11': 'Humedal',
  '12': 'Pastizal',
  '63': 'Estepa',
  '66': 'Matorral',
  '15': 'Pastura',
  '18': 'Agricultura',
  '9':  'Silvicultura',
  '23': 'Arena, playa y duna',
  '61': 'Salar',
  '29': 'Afloramiento rocoso',
  '24': 'Infraestructura',
  '25': 'Otra área sin vegetación',
  '33': 'Río, lago u océano',
  '34': 'Hielo y nieve',
  '27': 'Sin observación / No clasificado'
});

var lulc2024Vis = lulc2024
  .remap(
    clasesValidas,
    ee.List.sequence(1, clasesValidas.length)
  )
  .rename('lulc_vis');

var paletaLULC = {
  min: 1,
  max: clasesValidas.length,
  palette: mapbiomasPalette
};


// ── 3. DETECTAR / CREAR ID ROBUSTO PARA TILE ─────────────────────────────────

var TILE_ID_CANDIDATE_FIELDS = [
  'name',
  'Name',
  'tile',
  'Tile',
  'id',
  'ID',
  'TILE_ID',
  'tile_id',
  'MGRS_TILE',
  'mgrs_tile',
  'MGRS',
  'mgrs'
];

function addTileId(feature) {
  var props = feature.propertyNames();

  var init = ee.Dictionary({
    value: feature.id(),
    field: 'system:index',
    found: 0
  });

  var result = ee.Dictionary(
    ee.List(TILE_ID_CANDIDATE_FIELDS).iterate(function(field, acc) {
      field = ee.String(field);
      acc = ee.Dictionary(acc);

      var alreadyFound = ee.Number(acc.get('found')).eq(1);
      var exists = props.contains(field);

      var newValue = ee.Algorithms.If(
        alreadyFound,
        acc.get('value'),
        ee.Algorithms.If(exists, feature.get(field), acc.get('value'))
      );

      var newField = ee.Algorithms.If(
        alreadyFound,
        acc.get('field'),
        ee.Algorithms.If(exists, field, acc.get('field'))
      );

      var newFound = ee.Algorithms.If(
        alreadyFound,
        1,
        ee.Algorithms.If(exists, 1, 0)
      );

      return ee.Dictionary({
        value: newValue,
        field: newField,
        found: newFound
      });
    }, init)
  );

  return feature.set({
    tile_id: result.get('value'),
    tile_id_field_used: result.get('field')
  });
}

var tilesConId = tilesRaw.map(addTileId);

// Elimina duplicados por ID de tile.
var tilesAsset = tilesConId.distinct(['tile_id']);

print('Tiles únicos por tile_id:', tilesAsset.size());
print('Ejemplo tiles con ID:', tilesAsset.limit(5));


// ── 4. ELIMINAR TILES CON BAJA SUPERPOSICIÓN CON LANDCOVER ───────────────────

var lulcMask = lulc2024.unmask(0).neq(0).rename('valid');
var ones = ee.Image.constant(1).rename('total');

var tilesConOverlap = tilesAsset.map(function(tile) {
  var geom = tile.geometry();

  var totalResult = ones.reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: geom,
    scale: 500,
    maxPixels: 1e9,
    tileScale: 4
  });

  var validResult = lulcMask.reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: geom,
    scale: 500,
    maxPixels: 1e9,
    tileScale: 4
  });

  var totalPix = ee.Number(totalResult.get('total')).max(1);
  var validPix = ee.Number(validResult.get('valid'));
  var overlapPct = validPix.divide(totalPix).multiply(100);

  return tile
    .set('total_pixels', totalPix)
    .set('valid_pixels', validPix)
    .set('overlap_pct', overlapPct);
});

var tilesValidos = tilesConOverlap
  .filter(ee.Filter.gte('overlap_pct', UMBRAL_OVERLAP_PCT));

print('Tiles totales únicos:', tilesAsset.size());
print(
  'Tiles descartados overlap < ' + UMBRAL_OVERLAP_PCT + ' %:',
  tilesAsset.size().subtract(tilesValidos.size())
);
print(
  'Tiles válidos overlap ≥ ' + UMBRAL_OVERLAP_PCT + ' %:',
  tilesValidos.size()
);


// ── 5. CALCULAR MÉTRICAS Y DESCRIPCIÓN DE CLASES POR TILE ────────────────────

var N_TOTAL_CLASES_POSIBLES = ee.List(clasesEvaluables).length();

function getClassName(k) {
  k = ee.String(k);

  return ee.String(
    ee.Algorithms.If(
      CLASS_NAMES.contains(k),
      CLASS_NAMES.get(k),
      ee.String('Clase ').cat(k)
    )
  );
}

function getClassLabel(k) {
  k = ee.String(k);

  return ee.String('ID ')
    .cat(k)
    .cat(' - ')
    .cat(getClassName(k));
}

function addClassMetricsAndDescription(tile) {
  var geom = tile.geometry();

  var tileAreaHa = geom.area(1).divide(10000);

  var areaByClassImg = ee.Image.pixelArea()
    .divide(10000)
    .rename('area_ha')
    .addBands(lulc2024.rename('class'));

  var areaResult = areaByClassImg.reduceRegion({
    reducer: ee.Reducer.sum().group({
      groupField: 1,
      groupName: 'class'
    }),
    geometry: geom,
    scale: ANALYSIS_SCALE,
    maxPixels: 1e9,
    tileScale: 4,
    bestEffort: true
  });

  var groups = ee.List(
    ee.Algorithms.If(
      ee.Dictionary(areaResult).get('groups'),
      ee.Dictionary(areaResult).get('groups'),
      ee.List([])
    )
  );

  var areaDict = ee.Dictionary(
    groups.iterate(function(item, acc) {
      item = ee.Dictionary(item);
      acc = ee.Dictionary(acc);

      var classId = ee.Number(item.get('class')).format('%.0f');
      var areaHa = ee.Number(item.get('sum'));

      return acc.set(classId, areaHa);
    }, ee.Dictionary({}))
  );

  var keys = areaDict.keys();
  var values = areaDict.values();
  var nClases = keys.size();

  var validLulcAreaHa = ee.Number(
    ee.Algorithms.If(
      nClases.gt(0),
      values.reduce(ee.Reducer.sum()),
      0
    )
  );

  var sortedKeys = ee.List(
    ee.Algorithms.If(
      nClases.gt(0),
      keys.sort(values.map(function(v) {
        return ee.Number(v).multiply(-1);
      })),
      ee.List([])
    )
  );

  var maxClass = ee.Algorithms.If(
    nClases.gt(0),
    sortedKeys.get(0),
    null
  );

  var maxAreaHa = ee.Number(
    ee.Algorithms.If(
      nClases.gt(0),
      areaDict.get(maxClass),
      0
    )
  );

  var dominancia = ee.Number(
    ee.Algorithms.If(
      validLulcAreaHa.gt(0),
      maxAreaHa.divide(validLulcAreaHa),
      0
    )
  );

  var dominantClassName = ee.String(
    ee.Algorithms.If(
      nClases.gt(0),
      getClassName(ee.String(maxClass)),
      'Sin datos'
    )
  );

  var dominantClassLabel = ee.String(
    ee.Algorithms.If(
      nClases.gt(0),
      getClassLabel(ee.String(maxClass)),
      'Sin datos'
    )
  );

  var coveredClassFlags = ee.List(clasesEvaluables).map(function(classId) {
    classId = ee.Number(classId);
    var k = classId.format();

    return ee.Number(
      ee.Algorithms.If(
        areaDict.contains(k),
        1,
        0
      )
    );
  });

  var nClassesCovered = ee.Number(
    coveredClassFlags.reduce(ee.Reducer.sum())
  );

  var classCoveragePct = nClassesCovered
    .divide(N_TOTAL_CLASES_POSIBLES)
    .multiply(100);

  var classNamesList = sortedKeys.map(function(k) {
    k = ee.String(k);
    return getClassLabel(k);
  });

  var classesPresentNames = ee.String(classNamesList.join(', '));

  var classPctTileSummaryList = sortedKeys.map(function(k) {
    k = ee.String(k);

    var areaHa = ee.Number(areaDict.get(k));

    var pctTile = ee.Number(
      ee.Algorithms.If(
        tileAreaHa.gt(0),
        areaHa.divide(tileAreaHa).multiply(100),
        0
      )
    );

    return getClassLabel(k)
      .cat('=')
      .cat(pctTile.format('%.2f'))
      .cat('% del tile');
  });

  var classPctTileSummary = ee.String(classPctTileSummaryList.join(' ; '));

  var classPctValidSummaryList = sortedKeys.map(function(k) {
    k = ee.String(k);

    var areaHa = ee.Number(areaDict.get(k));

    var pctValid = ee.Number(
      ee.Algorithms.If(
        validLulcAreaHa.gt(0),
        areaHa.divide(validLulcAreaHa).multiply(100),
        0
      )
    );

    return getClassLabel(k)
      .cat('=')
      .cat(pctValid.format('%.2f'))
      .cat('% del LULC válido');
  });

  var classPctValidSummary = ee.String(classPctValidSummaryList.join(' ; '));

  var classSummaryList = sortedKeys.map(function(k) {
    k = ee.String(k);

    var areaHa = ee.Number(areaDict.get(k));

    var pctTile = ee.Number(
      ee.Algorithms.If(
        tileAreaHa.gt(0),
        areaHa.divide(tileAreaHa).multiply(100),
        0
      )
    );

    var pctValid = ee.Number(
      ee.Algorithms.If(
        validLulcAreaHa.gt(0),
        areaHa.divide(validLulcAreaHa).multiply(100),
        0
      )
    );

    return getClassLabel(k)
      .cat(': ')
      .cat(pctTile.format('%.2f'))
      .cat('% del tile | ')
      .cat(pctValid.format('%.2f'))
      .cat('% del LULC válido | ')
      .cat(areaHa.format('%.1f'))
      .cat(' ha');
  });

  var classSummary = ee.String(classSummaryList.join(' ; '));

  var classProps = ee.Dictionary(
    ee.List(clasesValidas).iterate(function(classId, acc) {
      classId = ee.Number(classId);
      acc = ee.Dictionary(acc);

      var k = classId.format();

      var areaHa = ee.Number(
        ee.Algorithms.If(
          areaDict.contains(k),
          areaDict.get(k),
          0
        )
      );

      var pctTile = ee.Number(
        ee.Algorithms.If(
          tileAreaHa.gt(0),
          areaHa.divide(tileAreaHa).multiply(100),
          0
        )
      );

      var pctValid = ee.Number(
        ee.Algorithms.If(
          validLulcAreaHa.gt(0),
          areaHa.divide(validLulcAreaHa).multiply(100),
          0
        )
      );

      return acc
        .set(ee.String('pct_tile_c').cat(k), pctTile)
        .set(ee.String('pct_valid_c').cat(k), pctValid)
        .set(ee.String('ha_c').cat(k), areaHa);
    }, ee.Dictionary({}))
  );

  var centroid = geom.centroid(100);
  var lon = centroid.coordinates().get(0);
  var lat = centroid.coordinates().get(1);

  return tile
    .set(classProps)
    .set({
      tile_area_ha: tileAreaHa,
      valid_lulc_area_ha_analysis_scale: validLulcAreaHa,
      n_classes: nClases,
      n_classes_possible: N_TOTAL_CLASES_POSIBLES,
      n_classes_covered: nClassesCovered,
      class_coverage_pct: classCoveragePct,
      dom_class: maxClass,
      dom_class_name: dominantClassName,
      dom_class_label: dominantClassLabel,
      dominancia: dominancia,
      classes_present: sortedKeys.join(','),
      classes_present_names: classesPresentNames,
      class_pct_tile_summary: classPctTileSummary,
      class_pct_valid_summary: classPctValidSummary,
      class_summary: classSummary,
      analysis_scale_m: ANALYSIS_SCALE,
      centroid_lon: lon,
      centroid_lat: lat
    });
}

var tilesConMetricas = tilesValidos.map(addClassMetricsAndDescription);

print('Ejemplo métricas primer tile:', tilesConMetricas.first());


// ── 6. SELECCIONAR TILES REPRESENTATIVOS ─────────────────────────────────────
// La cantidad de franjas latitudinales se ajusta automáticamente al número
// de tiles solicitado por el usuario.

var latMin = -56.0;
var latMax = -17.5;
var nFranjas = NUM_TILES_SELECCIONAR;
var paso = (latMax - latMin) / nFranjas;

var tilesPorFranja = ee.List.sequence(0, nFranjas - 1).map(function(i) {
  i = ee.Number(i);

  var latInf = ee.Number(latMin).add(i.multiply(paso));
  var latSup = latInf.add(paso);

  var enFranja = tilesConMetricas
    .filter(ee.Filter.and(
      ee.Filter.gte('centroid_lat', latInf),
      ee.Filter.lt('centroid_lat', latSup)
    ))
    .sort('dominancia', true)
    .sort('overlap_pct', false)
    .sort('n_classes', false);

  return enFranja.limit(1).first();
});

tilesPorFranja = tilesPorFranja.removeAll([null]);

var tilesSeleccionados = ee.FeatureCollection(tilesPorFranja);

// Si hay menos tiles que los solicitados, se complementa con los siguientes
// más diversos del conjunto válido.
var n = tilesSeleccionados.size();

var idsTilesSeleccionados = tilesSeleccionados.aggregate_array('tile_id');

var filtroNoSeleccionados = ee.Filter.inList(
  'tile_id',
  idsTilesSeleccionados
).not();

var complemento = tilesConMetricas
  .filter(filtroNoSeleccionados)
  .sort('dominancia', true)
  .sort('overlap_pct', false)
  .sort('n_classes', false)
  .limit(ee.Number(NUM_TILES_SELECCIONAR).subtract(n).max(0));

var tilesSeleccionFinal = ee.FeatureCollection(
  tilesSeleccionados
    .merge(complemento)
    .limit(NUM_TILES_SELECCIONAR)
);

print(
  'Tiles de prueba seleccionados (' + NUM_TILES_SELECCIONAR + '):',
  tilesSeleccionFinal
);
print('IDs seleccionados:', tilesSeleccionFinal.aggregate_array('tile_id'));


// ── 7. TABLA DESCRIPTIVA FINAL ───────────────────────────────────────────────

var pctTileFields = [
  'pct_tile_c3', 'pct_tile_c59', 'pct_tile_c60', 'pct_tile_c67',
  'pct_tile_c11', 'pct_tile_c12', 'pct_tile_c63', 'pct_tile_c66',
  'pct_tile_c15', 'pct_tile_c18', 'pct_tile_c9', 'pct_tile_c23',
  'pct_tile_c61', 'pct_tile_c29', 'pct_tile_c24', 'pct_tile_c25',
  'pct_tile_c33', 'pct_tile_c34', 'pct_tile_c27'
];

var pctValidFields = [
  'pct_valid_c3', 'pct_valid_c59', 'pct_valid_c60', 'pct_valid_c67',
  'pct_valid_c11', 'pct_valid_c12', 'pct_valid_c63', 'pct_valid_c66',
  'pct_valid_c15', 'pct_valid_c18', 'pct_valid_c9', 'pct_valid_c23',
  'pct_valid_c61', 'pct_valid_c29', 'pct_valid_c24', 'pct_valid_c25',
  'pct_valid_c33', 'pct_valid_c34', 'pct_valid_c27'
];

var haFields = [
  'ha_c3', 'ha_c59', 'ha_c60', 'ha_c67',
  'ha_c11', 'ha_c12', 'ha_c63', 'ha_c66',
  'ha_c15', 'ha_c18', 'ha_c9', 'ha_c23',
  'ha_c61', 'ha_c29', 'ha_c24', 'ha_c25',
  'ha_c33', 'ha_c34', 'ha_c27'
];

var baseFields = [
  'tile_id',
  'tile_id_field_used',
  'centroid_lon',
  'centroid_lat',
  'tile_area_ha',
  'overlap_pct',
  'valid_lulc_area_ha_analysis_scale',
  'n_classes',
  'n_classes_possible',
  'n_classes_covered',
  'class_coverage_pct',
  'dom_class',
  'dom_class_name',
  'dom_class_label',
  'dominancia',
  'classes_present',
  'classes_present_names',
  'class_pct_tile_summary',
  'class_pct_valid_summary',
  'class_summary',
  'analysis_scale_m'
];

var selectedTable = tilesSeleccionFinal.select(
  baseFields
    .concat(pctTileFields)
    .concat(pctValidFields)
    .concat(haFields)
);

print('Descripción de tiles seleccionados:', selectedTable);

print('── Métricas de los tiles seleccionados ──');
print('N° de clases por tile:', tilesSeleccionFinal.aggregate_array('n_classes'));
print('N° de clases cubiertas:', tilesSeleccionFinal.aggregate_array('n_classes_covered'));
print('Porcentaje de clases cubiertas:', tilesSeleccionFinal.aggregate_array('class_coverage_pct'));
print('Clase dominante ID:', tilesSeleccionFinal.aggregate_array('dom_class'));
print('Clase dominante nombre:', tilesSeleccionFinal.aggregate_array('dom_class_name'));
print('Dominancia 0-1:', tilesSeleccionFinal.aggregate_array('dominancia'));
print('Superposición LULC %:', tilesSeleccionFinal.aggregate_array('overlap_pct'));
print('Resumen % sobre superficie total del tile:', tilesSeleccionFinal.aggregate_array('class_pct_tile_summary'));


// ── 8. VISUALIZACIÓN ─────────────────────────────────────────────────────────

Map.addLayer(
  lulc2024Vis,
  paletaLULC,
  'LULC ' + YEAR_REF + ' - Colección 2',
  true,
  0.8
);

Map.addLayer(
  tilesAsset.style({
    color: '#888888',
    fillColor: '00000000',
    width: 0.5
  }),
  {},
  'Todos los tiles MGRS únicos',
  false
);

Map.addLayer(
  tilesValidos.style({
    color: '#3b82f6',
    fillColor: '3b82f610',
    width: 0.8
  }),
  {},
  'Tiles válidos overlap ≥ ' + UMBRAL_OVERLAP_PCT + '%',
  false
);

Map.addLayer(
  tilesSeleccionFinal.style({
    color: '#dc2626',
    fillColor: 'dc262625',
    width: 2
  }),
  {},
  NUM_TILES_SELECCIONAR + ' tiles de prueba seleccionados',
  true
);

var puntosTilesSeleccionados = tilesSeleccionFinal.map(function(tile) {
  var centroid = tile.geometry().centroid(100);

  var label = ee.String(tile.get('tile_id'))
    .cat(' | C:')
    .cat(ee.Number(tile.get('n_classes_covered')).int().format('%d'))
    .cat('/')
    .cat(ee.Number(tile.get('n_classes_possible')).int().format('%d'))
    .cat(' | Dom:')
    .cat(ee.String(tile.get('dom_class_name')));

  return ee.Feature(centroid, {
    tile_id: tile.get('tile_id'),
    label: label,
    class_pct_tile_summary: tile.get('class_pct_tile_summary')
  });
});

Map.addLayer(
  puntosTilesSeleccionados.style({
    color: '#7c2d12',
    pointSize: 5
  }),
  {},
  'Centroides tiles seleccionados',
  true
);

var tilesDescartados = tilesConOverlap
  .filter(ee.Filter.lt('overlap_pct', UMBRAL_OVERLAP_PCT));

Map.addLayer(
  tilesDescartados.style({
    color: '#aaaaaa',
    fillColor: 'aaaaaa15',
    width: 0.8
  }),
  {},
  'Tiles descartados overlap < ' + UMBRAL_OVERLAP_PCT + '%',
  false
);

Map.setCenter(-70.5, -35.0, 5);
Map.setOptions('SATELLITE');


// ── 9. PANEL DE INFORMACIÓN GENERAL ──────────────────────────────────────────

var panel = ui.Panel({
  style: {
    position: 'bottom-right',
    padding: '10px',
    width: '315px',
    backgroundColor: 'rgba(255,255,255,0.92)'
  }
});

panel.add(ui.Label('MapBiomas Chile — Tiles de Prueba', {
  fontWeight: 'bold',
  fontSize: '14px',
  margin: '0 0 6px'
}));

panel.add(ui.Label('Colección 03 | Selección automática', {
  fontSize: '12px',
  color: '#555',
  margin: '0 0 10px'
}));

var info = [
  'Tiles solicitados: ' + NUM_TILES_SELECCIONAR,
  'Overlap mínimo LULC: ' + UMBRAL_OVERLAP_PCT + ' %',
  'Año referencia LULC: ' + YEAR_REF,
  'Escala de análisis: ' + ANALYSIS_SCALE + ' m',
  'Distribución latitudinal automática',
  'Panel izquierdo: resumen simplificado por tile'
];

info.forEach(function(txt) {
  panel.add(ui.Label(txt, {
    fontSize: '12px',
    margin: '2px 0'
  }));
});

panel.add(ui.Button({
  label: 'Imprimir IDs en consola',
  onClick: function() {
    tilesSeleccionFinal.aggregate_array('tile_id').evaluate(function(ids) {
      print('IDs de los tiles seleccionados:', ids);
    });
  },
  style: {
    margin: '10px 0 0',
    width: '100%'
  }
}));

panel.add(ui.Button({
  label: 'Imprimir descripción completa',
  onClick: function() {
    print('Descripción completa de tiles seleccionados:', selectedTable);
  },
  style: {
    margin: '5px 0 0',
    width: '100%'
  }
}));

Map.add(panel);


// ── 10. PANEL DE DESCRIPCIÓN DE CADA TILE ────────────────────────────────────

var panelDesc = ui.Panel({
  style: {
    position: 'bottom-left',
    padding: '10px',
    width: '620px',
    height: '500px',
    backgroundColor: 'rgba(255,255,255,0.94)'
  }
});

panelDesc.add(ui.Label('Descripción de tiles seleccionados', {
  fontWeight: 'bold',
  fontSize: '14px',
  margin: '0 0 8px'
}));

selectedTable.evaluate(function(fc) {
  if (!fc || !fc.features) {
    panelDesc.add(ui.Label('No se pudo cargar la tabla de descripción.'));
    return;
  }

  fc.features.forEach(function(feature, index) {
    var p = feature.properties;

    var classCoveragePct = Math.round(p.class_coverage_pct * 100) / 100;
    var overlapPct = Math.round(p.overlap_pct * 100) / 100;
    var tileAreaHa = Math.round(p.tile_area_ha * 10) / 10;

    panelDesc.add(ui.Label(
      (index + 1) + '. Tile: ' + p.tile_id,
      {
        fontWeight: 'bold',
        fontSize: '12px',
        margin: '8px 0 2px'
      }
    ));

    panelDesc.add(ui.Label(
      'Área total tile: ' + tileAreaHa + ' ha | Overlap LULC: ' + overlapPct + '%',
      {
        fontSize: '11px',
        margin: '0 0 2px'
      }
    ));

    panelDesc.add(ui.Label(
      'Cobertura de clases: ' +
      p.n_classes_covered + '/' + p.n_classes_possible +
      ' clases (' + classCoveragePct + '% del total posible)',
      {
        fontSize: '11px',
        margin: '0 0 8px'
      }
    ));

    panelDesc.add(ui.Label(
      'Proporción por clase sobre superficie total del tile: ' +
      p.class_pct_tile_summary,
      {
        fontSize: '11px',
        color: '#333',
        margin: '0 0 14px'
      }
    ));
  });
});

Map.add(panelDesc);


// ── 11. EXPORTAR TILES SELECCIONADOS ─────────────────────────────────────────

Export.table.toDrive({
  collection: tilesSeleccionFinal,
  description: EXPORT_PREFIX + '_GeoJSON',
  fileFormat: 'GeoJSON',
  folder: DRIVE_FOLDER
});

Export.table.toDrive({
  collection: selectedTable,
  description: EXPORT_PREFIX + '_Descripcion_CSV',
  fileFormat: 'CSV',
  folder: DRIVE_FOLDER
});

// Exporta como asset.
// Si cambias NUM_TILES_SELECCIONAR o UMBRAL_OVERLAP_PCT,
// el nombre del asset también cambia para evitar sobrescribir resultados.

Export.table.toAsset({
  collection: tilesSeleccionFinal,
  description: EXPORT_PREFIX + '_Asset',
  assetId:
    'projects/mapbiomas-chile/assets/LULC/COLLECTION-03/ANCILLARY_DATA/' +
    EXPORT_PREFIX
});