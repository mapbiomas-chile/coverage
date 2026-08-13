#!/usr/bin/env bash
set -euo pipefail
cd /home/perazo/coverage/bands_reduction
PY=/home/perazo/.conda/envs/mb_coverage/bin/python
LOG=results/CIM2015/logs/shell_eco_batch.log
WORKERS=4
CORR=0.95,0.90,0.85

echo "=== batch start $(date -Is) ===" | tee -a "$LOG"
for ECO in $(seq 1 15); do
  NTILES=$(wc -l < "results/CIM2015/E${ECO}/2015/01_inventory/tiles.txt")
  echo "" | tee -a "$LOG"
  echo "=== E${ECO} start $(date -Is) tiles=${NTILES} ===" | tee -a "$LOG"
  t0=$(date +%s)
  "$PY" scripts/10_sample_eco_merged.py --eco-id "$ECO" --year 2015 --workers "$WORKERS" \
    --out-dir "results/CIM2015/E${ECO}/2015/eco_merged" 2>&1 | tee -a "$LOG"
  "$PY" scripts/11_cluster_eco_thresholds.py --eco-id "$ECO" --year 2015 \
    --corr-thresholds "$CORR" --save-corr 2>&1 | tee -a "$LOG"
  "$PY" scripts/12_select_eco_representatives.py --eco-id "$ECO" --year 2015 \
    --corr-thresholds "$CORR" 2>&1 | tee -a "$LOG"
  t1=$(date +%s)
  echo "=== E${ECO} DONE elapsed=$((t1-t0))s $(date -Is) ===" | tee -a "$LOG"
done
echo "=== batch DONE $(date -Is) ===" | tee -a "$LOG"
