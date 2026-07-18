#!/usr/bin/env bash
# V1 data-efficiency curve (tests H1: the contrast prior helps MORE with less data).
#   base / +CSCM / full  x  train sizes {100,200,400,600}  x  seeds {42,3407}
# Trains on a deterministic subset of the seed-42 train pool (subset fixed across seeds),
# evaluates on ECSSD-300 (held-out test) AND DUTS-TE (external).
# All three configs use the same structure loss so the ONLY variable is architecture.
#
# Usage:  ./run_data_efficiency.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"
PY="${PY:-python}"
ROOT="runs/data_efficiency"
SPLIT="splits/trainval_seed_42.json"
IMG=352; BS=16; EPOCHS=60; LR=3e-4; SUBSET_SEED=1234
SIZES=(100 200 400 600)
SEEDS=(42 3407 2026)

# cfg = "name|flags"  (base=all off, cscm=only CSCM on, full=all on; loss=structure for all)
CFGS=(
  "base|--disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "cscm|--disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup"
  "full|"
)

JOBS=()
for seed in "${SEEDS[@]}"; do
  for size in "${SIZES[@]}"; do
    for cfg in "${CFGS[@]}"; do
      JOBS+=("${seed}|${size}|${cfg}")
    done
  done
done

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r seed size name flags <<< "${job}"
  out="${ROOT}/seed${seed}/${name}_n${size}"
  echo "[gpu ${GPU_ID}] === seed${seed} ${name} n${size} ==="

  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --model c3net_r18 --pretrained \
      --split-file "${SPLIT}" \
      --train-subset ${size} --train-subset-seed ${SUBSET_SEED} \
      --image-size ${IMG} --batch-size ${BS} --epochs ${EPOCHS} --lr ${LR} --seed ${seed} \
      --device cuda --gpu-ids 0 \
      --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" \
      ${flags} || { echo "[gpu ${GPU_ID}] TRAIN FAIL ${name} n${size} seed${seed}"; continue; }
  fi

  if [ ! -f "${out}/test_metrics.json" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
      --model c3net_r18 --pretrained --split-file "${SPLIT}" --split test \
      --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
      --checkpoint "${out}/best.pt" --output-dir "${out}" ${flags} \
      || echo "[gpu ${GPU_ID}] EVAL FAIL ecssd ${name} n${size} seed${seed}"
  fi

  if [ ! -f "${out}/duts/test_metrics.json" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
      --model c3net_r18 --pretrained --data-root data/DUTS-TE --split-file splits/duts_te.json --split test \
      --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
      --checkpoint "${out}/best.pt" --output-dir "${out}/duts" ${flags} \
      || echo "[gpu ${GPU_ID}] EVAL FAIL duts ${name} n${size} seed${seed}"
  fi
done
echo "[gpu ${GPU_ID}] data-efficiency worker ${WORKER_INDEX} done."
