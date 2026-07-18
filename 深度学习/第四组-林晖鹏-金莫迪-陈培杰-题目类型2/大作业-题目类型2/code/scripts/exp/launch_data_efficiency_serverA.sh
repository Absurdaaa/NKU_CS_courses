#!/usr/bin/env bash
# Launch V1 data-efficiency on server A (4 GPUs, one worker per GPU).
set -euo pipefail
source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || true
conda activate sod
cd /home/ubuntu/lhp/deep-learning/basic
mkdir -p logs/data_efficiency
for w in 0 1 2 3; do
  nohup bash scripts/run_data_efficiency.sh "$w" "$w" 4 > "logs/data_efficiency/gpu${w}.log" 2>&1 &
  echo "WORKER_${w}:$!"
done
