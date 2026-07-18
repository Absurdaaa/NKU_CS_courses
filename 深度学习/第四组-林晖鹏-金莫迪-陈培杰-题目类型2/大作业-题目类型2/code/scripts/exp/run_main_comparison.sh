#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${1:-data/ECSSD}"
SPLIT_FILE="${2:-splits/trainval_seed_42.json}"
DEVICE="${3:-cuda}"
GPU_IDS="${4:-0,1}"
RUN_ROOT="${5:-runs/main_comparison}"

ACTION="$(python scripts/run_guard.py \
  --output-dir "${RUN_ROOT}/00_resnet18_baseline" \
  --expect model=resnet18 \
  --expect pretrained=true \
  --expect split_file="${SPLIT_FILE}" \
  --expect image_size=352 \
  --expect batch_size=16 \
  --expect epochs=100 \
  --expect lr=0.0003 \
  --expect selection_metric=max_f_measure \
  --expect augment_mode=basic)"

if [ "${ACTION}" = "skip" ]; then
  echo "Skip training: ${RUN_ROOT}/00_resnet18_baseline already matches"
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
    --selection-metric max_f_measure \
    --augment-mode basic \
    --output-dir "${RUN_ROOT}/00_resnet18_baseline"
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
  --checkpoint "${RUN_ROOT}/00_resnet18_baseline/best.pt" \
  --output-dir "${RUN_ROOT}/00_resnet18_baseline"

ACTION="$(python scripts/run_guard.py \
  --output-dir "${RUN_ROOT}/01_multicue_main" \
  --expect model=resnet18_multicue \
  --expect pretrained=true \
  --expect split_file="${SPLIT_FILE}" \
  --expect image_size=352 \
  --expect batch_size=16 \
  --expect epochs=100 \
  --expect lr=0.0003 \
  --expect selection_metric=max_f_measure \
  --expect augment_mode=basic \
  --expect multicue_context_type=pool \
  --expect multicue_edge_weight=0.4 \
  --expect disable_multicue_refine=true)"

if [ "${ACTION}" = "skip" ]; then
  echo "Skip training: ${RUN_ROOT}/01_multicue_main already matches"
else
  python train.py \
    --data-root "${DATA_ROOT}" \
    --split-file "${SPLIT_FILE}" \
    --model resnet18_multicue \
    --pretrained \
    --image-size 352 \
    --batch-size 16 \
    --epochs 100 \
    --lr 3e-4 \
    --device "${DEVICE}" \
    --gpu-ids "${GPU_IDS}" \
    --selection-metric max_f_measure \
    --augment-mode basic \
    --multicue-context-type pool \
    --multicue-edge-weight 0.4 \
    --disable-multicue-refine \
    --output-dir "${RUN_ROOT}/01_multicue_main"
fi

python eval.py \
  --data-root "${DATA_ROOT}" \
  --split-file "${SPLIT_FILE}" \
  --split test \
  --model resnet18_multicue \
  --pretrained \
  --image-size 352 \
  --batch-size 16 \
  --device "${DEVICE}" \
  --gpu-ids "${GPU_IDS}" \
  --multicue-context-type pool \
  --multicue-edge-weight 0.4 \
  --disable-multicue-refine \
  --checkpoint "${RUN_ROOT}/01_multicue_main/best.pt" \
  --output-dir "${RUN_ROOT}/01_multicue_main"

ACTION="$(python scripts/run_guard.py \
  --output-dir "${RUN_ROOT}/02_ldf_lite_main" \
  --expect model=resnet18_ldf_lite \
  --expect pretrained=true \
  --expect split_file="${SPLIT_FILE}" \
  --expect image_size=352 \
  --expect batch_size=16 \
  --expect epochs=100 \
  --expect lr=0.0003 \
  --expect selection_metric=max_f_measure \
  --expect augment_mode=basic \
  --expect ldf_loss=hybrid \
  --expect enable_ldf_gated_fusion=true)"

if [ "${ACTION}" = "skip" ]; then
  echo "Skip training: ${RUN_ROOT}/02_ldf_lite_main already matches"
else
  python train.py \
    --data-root "${DATA_ROOT}" \
    --split-file "${SPLIT_FILE}" \
    --model resnet18_ldf_lite \
    --pretrained \
    --image-size 352 \
    --batch-size 16 \
    --epochs 100 \
    --lr 3e-4 \
    --device "${DEVICE}" \
    --gpu-ids "${GPU_IDS}" \
    --selection-metric max_f_measure \
    --augment-mode basic \
    --ldf-loss hybrid \
    --enable-ldf-gated-fusion \
    --output-dir "${RUN_ROOT}/02_ldf_lite_main"
fi

python eval.py \
  --data-root "${DATA_ROOT}" \
  --split-file "${SPLIT_FILE}" \
  --split test \
  --model resnet18_ldf_lite \
  --pretrained \
  --image-size 352 \
  --batch-size 16 \
  --device "${DEVICE}" \
  --gpu-ids "${GPU_IDS}" \
  --ldf-loss hybrid \
  --enable-ldf-gated-fusion \
  --checkpoint "${RUN_ROOT}/02_ldf_lite_main/best.pt" \
  --output-dir "${RUN_ROOT}/02_ldf_lite_main"
