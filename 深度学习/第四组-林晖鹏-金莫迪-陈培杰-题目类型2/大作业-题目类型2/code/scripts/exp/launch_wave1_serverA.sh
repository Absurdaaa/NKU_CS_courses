#!/usr/bin/env bash
# Launch Wave-1 on server A AFTER V1 finishes (needs the 4 GPUs free).
# Each GPU worker runs its share of V2-fixed (data-efficiency arm) then the
# method-enhancement runs.
set -euo pipefail
source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || true
conda activate sod
cd /home/ubuntu/lhp/deep-learning/basic
mkdir -p logs/wave1
for w in 0 1 2 3; do
  nohup bash -c "bash scripts/run_v2_fixed.sh $w $w 4; bash scripts/run_method_enh.sh $w $w 4" \
    > "logs/wave1/gpu${w}.log" 2>&1 &
  echo "WORKER_${w}:$!"
done
