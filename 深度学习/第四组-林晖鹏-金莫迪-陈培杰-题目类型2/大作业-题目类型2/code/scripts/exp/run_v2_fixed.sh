#!/usr/bin/env bash
# V2 fixed-vs-learned arm: a parameter-free CSCM gate across the data-efficiency
# sizes, written into the same runs/data_efficiency tree as V1 so the summarizer
# compares base / cscm(learned) / cscmfix / full. Tests H2 (prior, not capacity).
#   ./run_v2_fixed.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"
PY="${PY:-python}"
ROOT="runs/data_efficiency"
SPLIT="splits/trainval_seed_42.json"
IMG=352; BS=16; EPOCHS=60; LR=3e-4; SUBSET_SEED=1234
SIZES=(100 200 400 600)
SEEDS=(42 3407 2026)
NAME="cscmfix"
FLAGS="--disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup --c3net-cscm-fixed"

JOBS=()
for seed in "${SEEDS[@]}"; do
  for size in "${SIZES[@]}"; do JOBS+=("${seed}|${size}"); done
done

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r seed size <<< "${job}"
  out="${ROOT}/seed${seed}/${NAME}_n${size}"
  echo "[gpu ${GPU_ID}] === seed${seed} ${NAME} n${size} ==="

  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --model c3net_r18 --pretrained --split-file "${SPLIT}" \
      --train-subset ${size} --train-subset-seed ${SUBSET_SEED} \
      --image-size ${IMG} --batch-size ${BS} --epochs ${EPOCHS} --lr ${LR} --seed ${seed} \
      --device cuda --gpu-ids 0 --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" ${FLAGS} \
      || { echo "[gpu ${GPU_ID}] TRAIN FAIL ${NAME} n${size} seed${seed}"; continue; }
  fi
  if [ ! -f "${out}/test_metrics.json" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
      --model c3net_r18 --pretrained --split-file "${SPLIT}" --split test \
      --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
      --checkpoint "${out}/best.pt" --output-dir "${out}" ${FLAGS} \
      || echo "[gpu ${GPU_ID}] EVAL FAIL ecssd ${NAME} n${size}"
  fi
  if [ ! -f "${out}/duts/test_metrics.json" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
      --model c3net_r18 --pretrained --data-root data/DUTS-TE --split-file splits/duts_te.json --split test \
      --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
      --checkpoint "${out}/best.pt" --output-dir "${out}/duts" ${FLAGS} \
      || echo "[gpu ${GPU_ID}] EVAL FAIL duts ${NAME} n${size}"
  fi
done
echo "[gpu ${GPU_ID}] v2-fixed worker ${WORKER_INDEX} done."
