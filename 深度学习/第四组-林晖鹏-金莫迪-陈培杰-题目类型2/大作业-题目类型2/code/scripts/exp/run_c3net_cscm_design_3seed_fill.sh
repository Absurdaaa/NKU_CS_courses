#!/usr/bin/env bash
# Fill missing 3-seed CSCM-design ablations for C3Net:
# - b_cscm_only
# - b4_norm
# - b4_ug
# - c_single7
# - c_pure
#
# Usage:
#   ./run_c3net_cscm_design_3seed_fill.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail

GPU_ID="${1:-0}"
WORKER_INDEX="${2:-0}"
NUM_WORKERS="${3:-1}"

ROOT="runs/c3net_ablation"
IMG=352
BS=16
EPOCHS=200
LR=3e-4
PY="${PY:-python}"

JOBS=(
  "splits/trainval_seed_3407.json|b_cscm_only|--model c3net_r18 --c3net-loss bce --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup"
  "splits/trainval_seed_2026.json|b_cscm_only|--model c3net_r18 --c3net-loss bce --disable-c3net-context --disable-c3net-edge --disable-c3net-deepsup"
  "splits/trainval_seed_3407.json|b4_norm|--model c3net_r18 --c3net-loss bce --c3net-cscm-variant norm"
  "splits/trainval_seed_2026.json|b4_norm|--model c3net_r18 --c3net-loss bce --c3net-cscm-variant norm"
  "splits/trainval_seed_3407.json|b4_ug|--model c3net_r18 --c3net-loss bce --c3net-cscm-gate uncertainty"
  "splits/trainval_seed_2026.json|b4_ug|--model c3net_r18 --c3net-loss bce --c3net-cscm-gate uncertainty"
  "splits/trainval_seed_3407.json|c_single7|--model c3net_r18 --c3net-loss structure --c3net-cscm-scales 7"
  "splits/trainval_seed_2026.json|c_single7|--model c3net_r18 --c3net-loss structure --c3net-cscm-scales 7"
  "splits/trainval_seed_3407.json|c_pure|--model c3net_r18 --c3net-loss structure --c3net-cscm-gating pure"
  "splits/trainval_seed_2026.json|c_pure|--model c3net_r18 --c3net-loss structure --c3net-cscm-gating pure"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then
    idx=$(( idx + 1 ))
    continue
  fi
  idx=$(( idx + 1 ))

  IFS='|' read -r split_file tag flags <<< "${job}"
  split_name="$(basename "${split_file}" .json)"
  out="${ROOT}/${split_name}/${tag}"
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
