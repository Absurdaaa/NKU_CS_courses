#!/usr/bin/env bash
# Task 3: zoom variants to test the residual-collapse hypothesis.
# Baseline penalises |delta| (pushes it to 0); the "noreg" / "strong" variants
# remove that penalty and up-weight the patch loss so the refiner is forced to
# do useful work in the uncertain patches.
#   ./run_zoom_variants.sh <gpu_id> <worker_index> <num_workers>
set -uo pipefail
GPU_ID="${1:-0}"; WORKER_INDEX="${2:-0}"; NUM_WORKERS="${3:-1}"
SPLIT="splits/trainval_seed_42.json"; IMG=352; BS=16; EP=200; PY="${PY:-python}"
ROOT="runs/zoom_variants/trainval_seed_42"
COMMON="--zoom-patch-size 128 --zoom-grid-size 32 --zoom-coarse-weight 0.4 --zoom-loss hybrid"

# job = "tag|flags"
JOBS=(
  "zoom_baseline|--zoom-topk 5 --zoom-patch-weight 0.5 --zoom-delta-weight 0.001"
  "zoom_noreg|--zoom-topk 5 --zoom-patch-weight 1.0 --zoom-delta-weight 0.0"
  "zoom_strong|--zoom-topk 8 --zoom-patch-weight 1.0 --zoom-delta-weight 0.0"
)

idx=0
for job in "${JOBS[@]}"; do
  if [ $(( idx % NUM_WORKERS )) -ne "${WORKER_INDEX}" ]; then idx=$(( idx + 1 )); continue; fi
  idx=$(( idx + 1 ))
  IFS='|' read -r tag flags <<< "${job}"
  out="${ROOT}/${tag}"
  echo "[gpu ${GPU_ID}] === ${tag} ==="
  if [ -f "${out}/best.pt" ] && [ -f "${out}/test_metrics.json" ]; then echo "[gpu ${GPU_ID}] skip"; continue; fi
  if [ ! -f "${out}/best.pt" ]; then
    PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} train.py \
      --model resnet18_uncertainty_zoom --pretrained --split-file "${SPLIT}" \
      --image-size ${IMG} --batch-size ${BS} --epochs ${EP} --lr 3e-4 \
      --device cuda --gpu-ids 0 --selection-metric max_f_measure --augment-mode basic \
      --output-dir "${out}" ${COMMON} ${flags} || { echo "[gpu ${GPU_ID}] TRAIN FAIL ${tag}"; continue; }
  fi
  PYTHONPATH=. CUDA_VISIBLE_DEVICES="${GPU_ID}" ${PY} eval.py \
    --model resnet18_uncertainty_zoom --pretrained --split-file "${SPLIT}" --split test \
    --image-size ${IMG} --batch-size ${BS} --device cuda --gpu-ids 0 \
    --checkpoint "${out}/best.pt" --output-dir "${out}" ${COMMON} ${flags} \
    || echo "[gpu ${GPU_ID}] EVAL FAIL ${tag}"
done
echo "[gpu ${GPU_ID}] zoom-variants worker ${WORKER_INDEX} done."
