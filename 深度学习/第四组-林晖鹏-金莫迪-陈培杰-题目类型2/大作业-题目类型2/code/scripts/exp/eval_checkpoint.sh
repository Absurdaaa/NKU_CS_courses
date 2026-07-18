#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "Usage: bash scripts/eval_checkpoint.sh <model> <checkpoint> <output_dir> [data_root] [split_file] [device] [gpu_ids] [extra args...]"
  exit 1
fi

MODEL="$1"
CHECKPOINT="$2"
OUTPUT_DIR="$3"
shift 3

DATA_ROOT="${1:-data/ECSSD}"
SPLIT_FILE="${2:-splits/trainval_seed_42.json}"
DEVICE="${3:-cuda}"
GPU_IDS="${4:-0,1}"

if [ "$#" -ge 4 ]; then
  shift 4
else
  shift "$#"
fi

python eval.py \
  --data-root "${DATA_ROOT}" \
  --split-file "${SPLIT_FILE}" \
  --split test \
  --model "${MODEL}" \
  --image-size 352 \
  --batch-size 16 \
  --device "${DEVICE}" \
  --gpu-ids "${GPU_IDS}" \
  --checkpoint "${CHECKPOINT}" \
  --output-dir "${OUTPUT_DIR}" \
  "$@"
