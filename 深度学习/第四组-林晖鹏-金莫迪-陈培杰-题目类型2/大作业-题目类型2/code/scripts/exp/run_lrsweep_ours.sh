#!/usr/bin/env bash
# Task 2 (server A): lr sweep for our two methods (C3Net b4_full, CTD-lite ctd_sem).
# lr 3e-4 already trained elsewhere; this sweeps the rest. Single GPU per job.
#   ./run_lrsweep_ours.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"
SPLIT="splits/trainval_seed_42.json"; IMG=352; BS=16; EP=200; PY="${PY:-python}"
ROOT="runs/lrsweep_ours/trainval_seed_42"

# job = "tag|model|lr|flags"
JOBS=(
  "c3net_1em4|c3net_r18|1e-4|--c3net-loss bce"
  "c3net_5em4|c3net_r18|5e-4|--c3net-loss bce"
  "c3net_1em3|c3net_r18|1e-3|--c3net-loss bce"
  "ctd_1em4|ctdnet_r18|1e-4|--ctdnet-loss bce --disable-ctdnet-boundary"
  "ctd_5em4|ctdnet_r18|5e-4|--ctdnet-loss bce --disable-ctdnet-boundary"
  "ctd_1em3|ctdnet_r18|1e-3|--ctdnet-loss bce --disable-ctdnet-boundary"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r tag model lr flags <<< "${job}"
  out="${ROOT}/${tag}"
  echo "[gpu ${GPU_ID}] === ${tag} (${model} ${lr}) ==="
  if [ -f "${out}/best.pt" ] && [ -f "${out}/test_metrics.json" ]; then echo "[gpu ${GPU_ID}] skip"; continue; fi
  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --model "${model}" --pretrained --split-file "${SPLIT}" \
      --image-size ${IMG} --batch-size ${BS} --epochs ${EP} --lr "${lr}" \
      --device cuda --gpu-ids 0 --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" ${flags} || { echo "[gpu ${GPU_ID}] TRAIN FAIL ${tag}"; continue; }
  fi
  PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
    --model "${model}" --pretrained --split-file "${SPLIT}" --split test \
    --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
    --checkpoint "${out}/best.pt" --output-dir "${out}" ${flags} \
    || echo "[gpu ${GPU_ID}] EVAL FAIL ${tag}"
done
echo "[gpu ${GPU_ID}] lrsweep-ours worker ${WORKER_INDEX} done."
