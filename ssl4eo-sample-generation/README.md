# SSL4EO-L Sample Generation for Land Cover Chile

Workflow for generating, selecting, reviewing, and auditing sampling rectangles (2×2 and 3×3, `scale300`) for SSL4EO-L/Landsat multitemporal chips. Designed for annual land cover and land use classification of Chile (target 1996–2025), with MapBiomas Chile Collection 2 as reference for 1999–2024.

**Cluster path:** local rasterio characterization on leftraru — no Google Earth Engine.

Run all commands from the root of this directory (`ssl4eo-sample-generation/`).

## Quick start (cluster)

```bash
export GRILLAS_ROOT=/home/lserey/mapbiomas_land/prod/samples
export MAPBIOMAS_LAND_ROOT=/home/lserey/mapbiomas_land

bash cluster/check_inputs.sh
sbatch cluster/run_full_pipeline.slurm          # 01 + 02–08
# RUN_CHAR=0 sbatch cluster/run_full_pipeline.slurm   # skip 01 if ZIPs exist
```

Details: [cluster/README.md](cluster/README.md) · Script reference: [scripts/README.md](scripts/README.md)

## Script pipeline (01–08)

| Step | Script | What it does | Output |
|------|--------|--------------|--------|
| 01 | `01_local_grid_characterization.py` | Characterize candidate grids (rasterio) | `intermediate_files/grid_characterization/*.zip` |
| 02 | `02_rectangle_selection.py` | Select samples; **4 runs** (UTM18/19 × 2×2/3×3); global anti-overlap | `final_samples/UTM*/{homogeneo_2x2\|mixto_3x3}/seleccion_*` |
| 03 | `03_annotate_grid_taxonomy.py` | N1/N2/N3 taxonomy on selection CSV | `*_taxonomia_n3.csv` |
| 04 | `04_rectangle_selection_review.py` | Review tables and text report | `intermediate_files/review/` |
| 05 | `05_balance_audit.py` | Balancing checklist (14 criteria) | `AUDITORIA_BALANCEO.txt` |
| 06 | `06_visualize_reports.py` | Streamlit dashboard / HTML export | `revision_dashboard.html` |
| 07 | `07_generate_rectangle_review_plan.py` | Review-year plan per rectangle | `plan_revision_UTM*_*_scale300.csv` |
| 08 | `08_consolidate_national_review_plan.py` | National plan consolidation | `plan_revision_nacional_scale300.csv` |

### Support modules

`local_grid_characterization.py`, `cluster_config.py`, `project_paths.py`, `selection_balancing.py`, `ecoregion_names.py`, `critical_classes.py`, `taxonomy_classes.py` — see [scripts/README.md](scripts/README.md).

## Repository layout

```text
ssl4eo-sample-generation/
├── README.md
├── requirements.txt
├── environment.yml
├── .gitignore
├── cluster/
│   ├── README.md
│   ├── run_full_pipeline.slurm
│   ├── run_pipeline_02_08.sh
│   └── check_inputs.sh
├── scripts/
│   ├── README.md
│   ├── 01_local_grid_characterization.py
│   ├── 02_rectangle_selection.py … 08_consolidate_national_review_plan.py
│   └── *.py                    ← helpers
├── intermediate_files/
│   ├── grid_characterization/  ← [01]
│   └── review/                 ← [04–08]
└── final_samples/              ← [02–03], by UTM + grid size
```

Derived data are not committed (see `.gitignore`). On cluster: `$GRILLAS_ROOT` → `/home/lserey/mapbiomas_land/prod/samples`.

## Methodology (summary)

1. **Candidate grid** — all valid rectangles per UTM zone and size.
2. **Selected rectangles** — ~300–350 nationally; balanced by type, ecoregion (E1–E15), critical classes.
3. **No geometric overlap** — each step 02 run excludes all prior selections (any huso, any size).
4. **Chips** — same `split` (train/val/test) for all chips in a rectangle.

## Quality control (step 05)

- **[14] Global overlap:** zero geometric pairs across all four selection files.
- National total ~300–350; see `AUDITORIA_BALANCEO.txt`.

## Dependencies

```bash
pip install -r requirements.txt
```

On cluster: `conda activate mb_labels`.

## Visualization

```bash
export GRILLAS_ROOT=/home/lserey/mapbiomas_land/prod/samples
streamlit run scripts/06_visualize_reports.py
python scripts/06_visualize_reports.py \
  --export-html intermediate_files/review/revision_dashboard.html
```
