#!/usr/bin/env bash
set -euo pipefail
# =========================================================================
# PFA-R18: Pyramid Feature Attention Network (CVPR 2019)
# CFE(dilated 1,3,5,7) + CA + SA + EdgeHoldLoss
# SGD lr=3e-4, cosine, epochs=100
# =========================================================================
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
DATA_ROOT="${DATA_ROOT:-data/ECSSD}"
SPLIT_FILE="${SPLIT_FILE:-splits/trainval_seed_42.json}"
EPOCHS="${EPOCHS:-100}"
BATCH_SIZE="${BATCH_SIZE:-64}"
LR="${LR:-3e-4}"
CUDA_DEVICE="${CUDA_DEVICE:-0,1}"
MODEL="pfa_r18"
RUN="runs/${MODEL}"
log() { echo "[$(date '+%H:%M:%S')] $*"; }
train() {
    log "Train $MODEL  DATA=$DATA_ROOT  EPOCHS=$EPOCHS  BATCH=$BATCH_SIZE  LR=$LR"
    CUDA_VISIBLE_DEVICES="$CUDA_DEVICE" python train.py --data-root "$DATA_ROOT" --split-file "$SPLIT_FILE" \
        --model "$MODEL" --image-size 352 --batch-size "$BATCH_SIZE" --epochs "$EPOCHS" --lr "$LR" \
        --device cuda --gpu-ids "$CUDA_DEVICE" --scheduler cosine --min-lr 1e-6 --grad-clip 1.0 \
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
