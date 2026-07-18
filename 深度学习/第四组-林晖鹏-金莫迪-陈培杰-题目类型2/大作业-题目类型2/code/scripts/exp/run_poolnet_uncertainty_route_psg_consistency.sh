#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${1:-data/ECSSD}"
SPLIT_FILE="${2:-splits/trainval_seed_42.json}"
DEVICE="${3:-cuda}"
GPU_IDS="${4:-0,1}"
OUTPUT_DIR="${5:-runs/poolnet_uncertainty_route_psg_consistency_r18/pilot_e60}"
EPOCHS="${6:-60}"

python train.py \
  --data-root "${DATA_ROOT}" \
  --split-file "${SPLIT_FILE}" \
  --model poolnet_uncertainty_route_psg_consistency_r18 \
  --pretrained \
  --image-size 352 \
  --batch-size 16 \
  --epochs "${EPOCHS}" \
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

python eval.py \
  --data-root "${DATA_ROOT}" \
  --split-file "${SPLIT_FILE}" \
  --split test \
  --model poolnet_uncertainty_route_psg_consistency_r18 \
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
