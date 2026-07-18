#!/usr/bin/env bash
set -euo pipefail

source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || true
conda activate sod
cd /home/ubuntu/lhp/deep-learning/basic

mkdir -p logs/c3net_3seed_fill

for w in 0 1 2 3; do
  nohup bash scripts/run_c3net_3seed_fill.sh "$w" "$w" 4 > "logs/c3net_3seed_fill/gpu${w}.log" 2>&1 &
  echo "WORKER_${w}:$!"
done
