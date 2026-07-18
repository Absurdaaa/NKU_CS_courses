#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${1:-data/ECSSD}"
SPLIT_FILE="${2:-splits/trainval_seed_42.json}"
DEVICE="${3:-cuda}"
GPU_IDS="${4:-0,1}"
OUTPUT_DIR="${5:-runs/uncertainty_zoom/fullrefine}"
ZOOM_TOPK="${6:-5}"

ACTION="$(python scripts/run_guard.py \
  --output-dir "${OUTPUT_DIR}" \
  --expect model=resnet18_uncertainty_zoom_fullrefine \
  --expect pretrained=true \
  --expect split_file="${SPLIT_FILE}" \
  --expect image_size=352 \
  --expect batch_size=16 \
  --expect epochs=200 \
  --expect lr=0.0003 \
  --expect selection_metric=max_f_measure \
  --expect augment_mode=basic \
  --expect zoom_topk="${ZOOM_TOPK}" \
  --expect zoom_patch_size=128 \
  --expect zoom_grid_size=32 \
  --expect zoom_coarse_weight=0.4 \
  --expect zoom_patch_weight=1.0 \
  --expect zoom_delta_weight=0.001 \
  --expect zoom_loss=hybrid)"

if [ "${ACTION}" = "skip" ]; then
  echo "Skip training: ${OUTPUT_DIR} already has matching config and best.pt"
else
  python train.py \
    --data-root "${DATA_ROOT}" \
    --split-file "${SPLIT_FILE}" \
    --model resnet18_uncertainty_zoom_fullrefine \
    --pretrained \
    --image-size 352 \
    --batch-size 16 \
    --epochs 200 \
    --lr 3e-4 \
    --device "${DEVICE}" \
    --gpu-ids "${GPU_IDS}" \
    --selection-metric max_f_measure \
    --augment-mode basic \
    --zoom-topk "${ZOOM_TOPK}" \
    --zoom-patch-size 128 \
    --zoom-grid-size 32 \
    --zoom-coarse-weight 0.4 \
    --zoom-patch-weight 1.0 \
    --zoom-loss hybrid \
    --zoom-vis-every 5 \
    --zoom-vis-count 3 \
    --output-dir "${OUTPUT_DIR}"
fi

python eval.py \
  --data-root "${DATA_ROOT}" \
  --split-file "${SPLIT_FILE}" \
  --split test \
  --model resnet18_uncertainty_zoom_fullrefine \
  --pretrained \
  --image-size 352 \
  --batch-size 16 \
  --device "${DEVICE}" \
  --gpu-ids "${GPU_IDS}" \
  --zoom-topk "${ZOOM_TOPK}" \
  --zoom-patch-size 128 \
  --zoom-grid-size 32 \
  --zoom-coarse-weight 0.4 \
  --zoom-patch-weight 1.0 \
  --zoom-loss hybrid \
  --checkpoint "${OUTPUT_DIR}/best.pt" \
  --output-dir "${OUTPUT_DIR}"
