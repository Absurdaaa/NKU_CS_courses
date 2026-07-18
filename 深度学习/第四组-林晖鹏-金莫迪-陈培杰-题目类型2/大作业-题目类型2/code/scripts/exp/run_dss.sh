#!/usr/bin/env bash
set -euo pipefail

# =========================================================================
#  DSS-R18 训练 & 评测脚本 (basic 框架)
#
#  Reference: Hou et al., CVPR 2017
#  SGD lr=1e-3, momentum=0.9, decay=5e-4, BCE
#
#  用法:
#    bash scripts/run_dss.sh train
#    bash scripts/run_dss.sh eval
#    bash scripts/run_dss.sh all
# =========================================================================

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

DATA_ROOT="${DATA_ROOT:-data/ECSSD}"
SPLIT_FILE="${SPLIT_FILE:-splits/trainval_seed_42.json}"
EPOCHS="${EPOCHS:-200}"
BATCH_SIZE="${BATCH_SIZE:-16}"
LR="${LR:-1e-3}"
CUDA_DEVICE="${CUDA_DEVICE:-0,1}"

MODEL_NAME="dss_r18"
RUN_DIR="runs/${MODEL_NAME}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

train() {
    log "========== Train DSS-R18 =========="
    log "DATA=$DATA_ROOT  EPOCHS=$EPOCHS  BATCH=$BATCH_SIZE  LR=$LR  GPU=$CUDA_DEVICE"

    CUDA_VISIBLE_DEVICES="$CUDA_DEVICE" python train.py \
        --data-root "$DATA_ROOT" \
        --split-file "$SPLIT_FILE" \
        --model "$MODEL_NAME" \
        --image-size 352 \
        --batch-size "$BATCH_SIZE" \
        --epochs "$EPOCHS" \
        --lr "$LR" \
        --device cuda \
        --gpu-ids "$CUDA_DEVICE" \
        --scheduler none \
        --grad-clip 1.0 \
        --selection-metric max_f_measure \
        --augment-mode basic \
        --pretrained \
        --output-dir "$RUN_DIR" \
        --seed 42

    log "Training done. Checkpoints: $RUN_DIR/best.pt, $RUN_DIR/last.pt"
}

eval_only() {
    local checkpoint="${1:-$RUN_DIR/best.pt}"
    local split="${2:-test}"

    log "========== Evaluate DSS-R18 (split=$split) =========="
    CUDA_VISIBLE_DEVICES="$CUDA_DEVICE" python eval.py \
        --data-root "$DATA_ROOT" \
        --split-file "$SPLIT_FILE" \
        --model "$MODEL_NAME" \
        --image-size 352 \
        --batch-size 1 \
        --device cuda \
        --gpu-ids "$CUDA_DEVICE" \
        --split "$split" \
        --checkpoint "$checkpoint"
    log "Evaluation done."
}

case "${1:-}" in
    train)  train ;;
    eval)   eval_only "$2" "${3:-test}" ;;
    all)    train; eval_only "$RUN_DIR/best.pt" "test" ;;
    *)      echo "Usage: $0 {train|eval|all}"; exit 1 ;;
esac
