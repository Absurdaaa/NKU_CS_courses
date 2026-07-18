#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${1:-data/ECSSD}"
SPLIT_FILE="${2:-splits/trainval_seed_42.json}"
DEVICE="${3:-cuda}"
GPU_IDS="${4:-0,1,2,3}"
OUTPUT_DIR="${5:-runs/poolnet_uncertainty_route_r18/main}"

ACTION="$(python scripts/run_guard.py \
  --output-dir "${OUTPUT_DIR}" \
  --expect model=poolnet_uncertainty_route_r18 \
  --expect pretrained=true \
  --expect split_file="${SPLIT_FILE}" \
  --expect image_size=352 \
  --expect batch_size=16 \
  --expect epochs=200 \
  --expect lr=0.0003 \
  --expect selection_metric=max_f_measure \
  --expect augment_mode=basic \
  --expect hybrid_edge_channels=128 \
  --expect hybrid_edge_weight=0.3 \
  --expect hybrid_side_weight=0.2 \
  --expect zoom_coarse_weight=0.4 \
  --expect zoom_loss=hybrid)"

if [ "${ACTION}" = "skip" ]; then
  echo "Skip training: ${OUTPUT_DIR} already has matching config and best.pt"
else
  python train.py \
    --data-root "${DATA_ROOT}" \
    --split-file "${SPLIT_FILE}" \
    --model poolnet_uncertainty_route_r18 \
    --pretrained \
    --image-size 352 \
    --batch-size 16 \
    --epochs 200 \
    --lr 3e-4 \
    --device "${DEVICE}" \
    --gpu-ids "${GPU_IDS}" \
    --selection-metric max_f_measure \
    --augment-mode basic \
    --zoom-coarse-weight 0.4 \
    --zoom-loss hybrid \
    --hybrid-edge-channels 128 \
    --hybrid-edge-weight 0.3 \
    --hybrid-side-weight 0.2 \
    --output-dir "${OUTPUT_DIR}"
fi

python eval.py \
  --data-root "${DATA_ROOT}" \
  --split-file "${SPLIT_FILE}" \
  --split test \
  --model poolnet_uncertainty_route_r18 \
  --pretrained \
  --image-size 352 \
  --batch-size 16 \
  --device "${DEVICE}" \
  --gpu-ids "${GPU_IDS}" \
  --zoom-coarse-weight 0.4 \
  --zoom-loss hybrid \
  --hybrid-edge-channels 128 \
  --hybrid-edge-weight 0.3 \
  --hybrid-side-weight 0.2 \
  --checkpoint "${OUTPUT_DIR}/best.pt" \
  --output-dir "${OUTPUT_DIR}"
