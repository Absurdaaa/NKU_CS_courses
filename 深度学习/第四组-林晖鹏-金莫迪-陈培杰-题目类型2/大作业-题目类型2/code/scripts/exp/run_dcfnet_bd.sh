#!/usr/bin/env bash
set -euo pipefail
# =========================================================================
# DCFNet-BD-R18: DCFNet + Body/Detail supervision (LDF, AAAI 2020)
# Adds body_head + detail_head at c0 for decomposed supervision
# SGD lr=1e-3, epochs=200
# =========================================================================
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
DATA_ROOT="${DATA_ROOT:-data/ECSSD}"
SPLIT_FILE="${SPLIT_FILE:-splits/trainval_seed_42.json}"
EPOCHS="${EPOCHS:-200}"
BATCH_SIZE="${BATCH_SIZE:-16}"
LR="${LR:-1e-3}"
CUDA_DEVICE="${CUDA_DEVICE:-0,1}"
MODEL="dcfnet_bd_r18"
RUN="runs/${MODEL}"
log() { echo "[$(date '+%H:%M:%S')] $*"; }
train() {
    log "Train $MODEL  DATA=$DATA_ROOT  EPOCHS=$EPOCHS  BATCH=$BATCH_SIZE  LR=$LR"
    CUDA_VISIBLE_DEVICES="$CUDA_DEVICE" python train.py --data-root "$DATA_ROOT" --split-file "$SPLIT_FILE" \
        --model "$MODEL" --image-size 352 --batch-size "$BATCH_SIZE" --epochs "$EPOCHS" --lr "$LR" \
        --device cuda --gpu-ids "$CUDA_DEVICE" --scheduler none --grad-clip 1.0 \
        --selection-metric max_f_measure --augment-mode basic --pretrained --output-dir "$RUN" --seed 42
    log "Done: $RUN/best.pt"
}
eval_only() {
    local ckpt="${1:-$RUN/best.pt}"; local split="${2:-test}"
    log "Eval $MODEL split=$split"
    CUDA_VISIBLE_DEVICES="$CUDA_DEVICE" python eval.py --data-root "$DATA_ROOT" --split-file "$SPLIT_FILE" \
        --model "$MODEL" --image-size 352 --batch-size 1 --device cuda --gpu-ids "$CUDA_DEVICE" \
        --split "$split" --checkpoint "$ckpt"
    log "Done."
}
case "${1:-}" in
    train) train ;;  eval) eval_only "$2" "${3:-test}" ;;  all) train; eval_only "$RUN/best.pt" "test" ;;
    *) echo "Usage: $0 {train|eval|all}"; exit 1 ;;
esac
