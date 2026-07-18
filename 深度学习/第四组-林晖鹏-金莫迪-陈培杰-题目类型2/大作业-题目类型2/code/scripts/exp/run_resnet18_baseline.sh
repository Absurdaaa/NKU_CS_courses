#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${1:-data/ECSSD}"
SPLIT_FILE="${2:-splits/trainval_seed_42.json}"
DEVICE="${3:-cuda}"
GPU_IDS="${4:-0,1}"
OUTPUT_DIR="${5:-runs/main_comparison/00_resnet18_baseline}"

ACTION="$(python scripts/run_guard.py \
  --output-dir "${OUTPUT_DIR}" \
  --expect model=resnet18 \
  --expect pretrained=true \
  --expect split_file="${SPLIT_FILE}" \
  --expect image_size=352 \
  --expect batch_size=16 \
  --expect epochs=100 \
  --expect lr=0.0003 \
  --expect scheduler=auto \
  --expect min_lr=0.000001 \
  --expect grad_clip=1.0 \
  --expect selection_metric=max_f_measure \
  --expect augment_mode=basic)"

if [ "${ACTION}" = "skip" ]; then
  echo "Skip training: ${OUTPUT_DIR} already has matching config and best.pt"
else
  python train.py \
    --data-root "${DATA_ROOT}" \
    --split-file "${SPLIT_FILE}" \
    --model resnet18 \
    --pretrained \
    --image-size 352 \
    --batch-size 16 \
    --epochs 100 \
    --lr 3e-4 \
    --device "${DEVICE}" \
    --gpu-ids "${GPU_IDS}" \
    --scheduler auto \
    --min-lr 1e-6 \
    --grad-clip 1.0 \
    --selection-metric max_f_measure \
    --augment-mode basic \
    --output-dir "${OUTPUT_DIR}"
fi

python eval.py \
  --data-root "${DATA_ROOT}" \
  --split-file "${SPLIT_FILE}" \
  --split test \
  --model resnet18 \
  --pretrained \
  --image-size 352 \
  --batch-size 16 \
  --device "${DEVICE}" \
  --gpu-ids "${GPU_IDS}" \
  --pretrained \
  --checkpoint "${OUTPUT_DIR}/best.pt" \
  --output-dir "${OUTPUT_DIR}"
