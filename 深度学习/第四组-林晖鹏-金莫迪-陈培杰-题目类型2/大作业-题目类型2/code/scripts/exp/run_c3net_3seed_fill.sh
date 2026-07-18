#!/usr/bin/env bash
# Fill missing 3-seed C3Net ablations for:
# - cumulative BCE chain: b2_context, b3_cue
# - leave-one-out: c3_loo_no_ppm, c3_loo_no_edge, c3_loo_no_deepsup
#
# Usage:
#   ./run_c3net_3seed_fill.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail

GPU_ID="${1:-0}"
WORKER_INDEX="${2:-0}"
NUM_WORKERS="${3:-1}"

ROOT_C3="runs/c3net_ablation"
ROOT_LOO="runs/loo_ablation"
IMG=352
BS=16
EPOCHS=200
LR=3e-4
PY="${PY:-python}"

# job = "split_file|root|tag|flags"
JOBS=(
  "splits/trainval_seed_3407.json|${ROOT_C3}|b2_context|--model c3net_r18 --c3net-loss bce --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "splits/trainval_seed_2026.json|${ROOT_C3}|b2_context|--model c3net_r18 --c3net-loss bce --disable-c3net-edge --disable-c3net-deepsup --disable-c3net-cscm"
  "splits/trainval_seed_3407.json|${ROOT_C3}|b3_cue|--model c3net_r18 --c3net-loss bce --disable-c3net-cscm"
  "splits/trainval_seed_2026.json|${ROOT_C3}|b3_cue|--model c3net_r18 --c3net-loss bce --disable-c3net-cscm"
  "splits/trainval_seed_3407.json|${ROOT_LOO}|c3_loo_no_ppm|--model c3net_r18 --c3net-loss bce --disable-c3net-context"
  "splits/trainval_seed_2026.json|${ROOT_LOO}|c3_loo_no_ppm|--model c3net_r18 --c3net-loss bce --disable-c3net-context"
  "splits/trainval_seed_3407.json|${ROOT_LOO}|c3_loo_no_edge|--model c3net_r18 --c3net-loss bce --disable-c3net-edge"
  "splits/trainval_seed_2026.json|${ROOT_LOO}|c3_loo_no_edge|--model c3net_r18 --c3net-loss bce --disable-c3net-edge"
  "splits/trainval_seed_3407.json|${ROOT_LOO}|c3_loo_no_deepsup|--model c3net_r18 --c3net-loss bce --disable-c3net-deepsup"
  "splits/trainval_seed_2026.json|${ROOT_LOO}|c3_loo_no_deepsup|--model c3net_r18 --c3net-loss bce --disable-c3net-deepsup"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then
    idx=$(( idx + 1 ))
    continue
  fi
  idx=$(( idx + 1 ))

  IFS='|' read -r split_file root tag flags <<< "${job}"
  split_name="$(basename "${split_file}" .json)"
  out="${root}/${split_name}/${tag}"
  echo "[gpu ${GPU_ID}] === ${split_name}/${tag} ==="

  if [ -f "${out}/best.pt" ] && [ -f "${out}/test_metrics.json" ]; then
    echo "[gpu ${GPU_ID}] skip complete: ${out}"
    continue
  fi

  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --pretrained \
      --split-file "${split_file}" \
      --image-size ${IMG} --batch-size ${BS} --epochs ${EPOCHS} --lr ${LR} \
      --device cuda --gpu-ids 0 \
      --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" \
      ${flags} || { echo "[gpu ${GPU_ID}] TRAIN FAIL: ${tag}"; continue; }
  fi

  PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
    --pretrained \
    --split-file "${split_file}" --split test \
    --image-size ${IMG} --batch-size ${BS} \
    --device cuda --gpu-ids 0 \
    --checkpoint "${out}/best.pt" \
    --output-dir "${out}" \
    ${flags} || echo "[gpu ${GPU_ID}] EVAL FAIL: ${tag}"
done

echo "[gpu ${GPU_ID}] worker ${WORKER_INDEX} done."
