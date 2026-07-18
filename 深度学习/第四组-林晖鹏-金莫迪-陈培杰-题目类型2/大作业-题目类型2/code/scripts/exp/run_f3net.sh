#!/usr/bin/env bash
set -euo pipefail

# =========================================================================
#  F3Net-R18 训练 & 评测脚本 (basic 框架)
#
#  用法:
#    bash scripts/run_f3net.sh train              # 训练 base 变体
#    bash scripts/run_f3net.sh train enhanced      # 训练 enhanced 变体
#    bash scripts/run_f3net.sh eval base            # 评测
#    bash scripts/run_f3net.sh all base             # 训练 + 评测
#
#  环境变量 (可覆盖默认值):
#    DATA_ROOT     – 数据集路径  (默认 data/ECSSD)
#    SPLIT_FILE    – 划分文件    (默认 splits/trainval_seed_42.json)
#    EPOCHS        – 训练轮数    (默认 32)
#    BATCH_SIZE    – 批大小      (默认 32)
#    LR            – 学习率      (默认 0.05)
#    CUDA_DEVICE   – GPU 编号    (默认 0)
# =========================================================================

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# --------------- 可配置参数 ---------------
DATA_ROOT="${DATA_ROOT:-data/ECSSD}"
SPLIT_FILE="${SPLIT_FILE:-splits/trainval_seed_42.json}"
EPOCHS="${EPOCHS:-200}"
BATCH_SIZE="${BATCH_SIZE:-16}"
LR="${LR:-0.05}"
CUDA_DEVICE="${CUDA_DEVICE:-0,1}"

VARIANT="${2:-base}"
LOSS_PROFILE="${3:-base}"
MODEL_NAME="f3net_r18"
RUN_DIR="runs/${MODEL_NAME}"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

train() {
    local variant="${1:-base}"
    local loss_profile="${2:-base}"

    log "========== Train F3Net-R18 (variant=$variant, loss=$loss_profile) =========="
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
        --scheduler cosine \
        --min-lr 1e-6 \
        --grad-clip 1.0 \
        --selection-metric max_f_measure \
        --f3net-variant "$variant" \
        --f3net-loss-profile "$loss_profile" \
        --augment-mode basic \
        --pretrained \
        --output-dir "$RUN_DIR" \
        --seed 42

    log "Training done. Checkpoints: $RUN_DIR/best.pt, $RUN_DIR/last.pt"
}

eval_only() {
    local variant="${1:-base}"
    local loss_profile="${2:-base}"
    local checkpoint="${3:-$RUN_DIR/best.pt}"
    local split="${4:-test}"

    log "========== Evaluate F3Net-R18 (variant=$variant, split=$split) =========="
    log "checkpoint=$checkpoint"

    CUDA_VISIBLE_DEVICES="$CUDA_DEVICE" python eval.py \
        --data-root "$DATA_ROOT" \
        --split-file "$SPLIT_FILE" \
        --model "$MODEL_NAME" \
        --image-size 352 \
        --batch-size 1 \
        --device cuda \
        --gpu-ids "$CUDA_DEVICE" \
        --f3net-variant "$variant" \
        --f3net-loss-profile "$loss_profile" \
        --split "$split" \
        --checkpoint "$checkpoint"

    log "Evaluation done."
}

case "${1:-}" in
    train)  train "$VARIANT" "$LOSS_PROFILE" ;;
    eval)   eval_only "$VARIANT" "$LOSS_PROFILE" "$4" "${5:-test}" ;;
    all)    train "$VARIANT" "$LOSS_PROFILE"
            eval_only "$VARIANT" "$LOSS_PROFILE" "$RUN_DIR/best.pt" "test" ;;
    *)
        echo "Usage: $0 {train|eval|all} [variant: base|enhanced] [loss_profile: base|enhanced]"
        echo ""
        echo "  train [variant]             Train model"
        echo "  eval  [variant] [ckpt]      Evaluate model"
        echo "  all   [variant]             Train + evaluate"
        echo ""
        echo "Env vars: DATA_ROOT SPLIT_FILE EPOCHS BATCH_SIZE LR CUDA_DEVICE"
        exit 1 ;;
esac
