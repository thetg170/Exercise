#!/usr/bin/env bash
# run_all.sh — chạy lại toàn bộ pipeline EDA theo thứ tự, ghi stdout vào logs/.
# Dùng file khác (vd. bản đã randomize):  EDA_XLSM="/đường/dẫn/file.xlsm" bash scripts/run_all.sh
set -euo pipefail
cd "$(dirname "$0")"
PY="../.venv/bin/python"
mkdir -p ../logs
for s in 00_load_and_inspect 01_structure 02_data_quality 03_univariate 04_outliers 05_bivariate \
         06_target_price 07_groups_time 08_representativeness 09_issue_log; do
  echo ">>> $s"
  "$PY" "$s.py" > "../logs/$s.log" 2>&1
done
echo "Xong. Log trong logs/, bảng trong tables/, hình trong figures/."
