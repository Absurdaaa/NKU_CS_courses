#!/usr/bin/env bash
set -euo pipefail

source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || true
conda activate DL
cd /home/ubuntu14/lhp/deep-learning/basic

mkdir -p logs/c3net_cscm_design_fill

for w in 0 1; do
  nohup bash scripts/run_c3net_cscm_design_3seed_fill.sh "$w" "$w" 2 > "logs/c3net_cscm_design_fill/gpu${w}.log" 2>&1 &
  echo "WORKER_${w}:$!"
done
