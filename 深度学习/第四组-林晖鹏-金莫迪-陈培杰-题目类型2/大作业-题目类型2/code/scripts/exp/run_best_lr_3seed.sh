#!/usr/bin/env bash
# Task 1 (server B): train each comparison model at its seed-42-optimal lr on the
# two extra seeds (3407, 2026) to obtain 3-seed results.  Single GPU per job.
#   ./run_best_lr_3seed.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"
DATA="data/ECSSD"; IMG=352; BS=16; EP=200; PY="${PY:-python}"

# job = "model|lr|lrtag|seed"
JOBS=(
  "egnet_r18|5e-5|lr_5em5|3407"   "egnet_r18|5e-5|lr_5em5|2026"
  "pfa_r18|5e-2|lr_5em2|3407"     "pfa_r18|5e-2|lr_5em2|2026"
  "sinet_r18|1e-4|lr_1em4|3407"   "sinet_r18|1e-4|lr_1em4|2026"
  "poolnet_r18|1e-4|lr_1em4|3407" "poolnet_r18|1e-4|lr_1em4|2026"
  "dss_r18|5e-2|lr_5em2|3407"     "dss_r18|5e-2|lr_5em2|2026"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r model lr lrtag seed <<< "${job}"
  split="splits/trainval_seed_${seed}.json"
  out="runs/main_lr_sweep/trainval_seed_${seed}/${model}/${lrtag}"
  echo "[gpu ${GPU_ID}] === ${model} ${lr} seed${seed} ==="
  if [ -f "${out}/best.pt" ] && [ -f "${out}/test_metrics.json" ]; then echo "[gpu ${GPU_ID}] skip"; continue; fi
  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --data-root "${DATA}" --split-file "${split}" --model "${model}" --pretrained \
      --image-size ${IMG} --batch-size ${BS} --epochs ${EP} --lr "${lr}" \
      --device cuda --gpu-ids 0 --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" || { echo "[gpu ${GPU_ID}] TRAIN FAIL ${model} seed${seed}"; continue; }
  fi
  PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
    --data-root "${DATA}" --split-file "${split}" --split test --model "${model}" --pretrained \
    --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
    --checkpoint "${out}/best.pt" --output-dir "${out}" \
    || echo "[gpu ${GPU_ID}] EVAL FAIL ${model} seed${seed}"
done
echo "[gpu ${GPU_ID}] best-lr-3seed worker ${WORKER_INDEX} done."
