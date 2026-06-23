"""Nombres de ecorregiones MapBiomas C3 (15 continentales + 2 islas)."""

from __future__ import annotations

ECO_NAMES: dict[str, str] = {
    "1": "E1_Puna_seca_andina",
    "2": "E2_Desierto_Atacama",
    "3": "E3_Matorral_norte_1",
    "4": "E4_Estepa_andina",
    "5": "E5_Matorral_norte_2",
    "6": "E6_Andes_norte",
    "7": "E7_Andes_central",
    "8": "E8_Matorral_sur",
    "9": "E9_Costa_Norte",
    "10": "E10_Andes_Sur",
    "11": "E11_Costa_Sur_1",
    "12": "E12_Costa_Sur_2",
    "13": "E13_Andes_Sur_Costa",
    "14": "E14_Estepa_patagonica",
    "15": "E15_Bosque_subpolar",
    "16": "E16_Isla_de_Pascua",
    "17": "E17_Juan_Fernandez",
}

MAINLAND_ECO_IDS = frozenset(range(1, 16))
ISLAND_ECO_IDS = frozenset({16, 17})

# Nombres LULC N1 que se confundieron con ecorregion en eco_dom_name (bug local v1).
_LULC_N1_NAMES = frozenset({
    "Formacion_boscosa", "Form_natural_no_boscosa", "Agropecuaria_silvicultura",
    "Area_sin_vegetacion", "Cuerpo_de_agua", "No_observado", "Bosque", "Humedal",
    "Pastizal", "Pastura", "Silvicultura", "Estepa", "Matorral",
})


def ecoregion_label(eco_id, eco_name: str | None = None) -> str:
    """Devuelve nombre canonico de ecorregion; corrige etiquetas LULC erroneas."""
    try:
        eid = int(eco_id)
    except (TypeError, ValueError):
        return _clean(eco_name) or "sin_nombre"

    canonical = ECO_NAMES.get(str(eid), f"E{eid}_desconocida")
    name = _clean(eco_name)
    if not name or name in _LULC_N1_NAMES or name == "sin_nombre":
        return canonical
    if name.startswith("E") and "_" in name:
        return name
    return canonical


def _clean(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() in ("nan", "none") else s


def ecoregion_sort_key(label: str) -> tuple[int, str]:
    """Orden E1..E15 para ejes de heatmap."""
    s = str(label)
    if s.startswith("E") and "_" in s:
        try:
            return int(s[1:].split("_", 1)[0]), s
        except ValueError:
            pass
    return 999, s


def sort_ecoregion_index(index) -> list:
    return sorted(index, key=ecoregion_sort_key)


def mainland_eco_mask(series) -> "pd.Series":
    import pandas as pd

    ids = pd.to_numeric(series, errors="coerce")
    return ids.isin(list(MAINLAND_ECO_IDS))
