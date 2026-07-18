#!/usr/bin/env bash

set -euo pipefail

# cd /Users/linshangjin/Desktop/DeepLearning/lab2

# 条件名字生成任务的学习率扫描脚本
# 默认使用全量数据；如果你想先快速粗扫，可以把 MAX_SAMPLES 改成更小的值

HIDDEN_SIZE=128
EPOCHS=100
BATCH_SIZE=128
DROPOUT=0.0
OPTIMIZER=adam
CLIP_GRAD_NORM=0
MAX_SAMPLES=0
SAMPLES_PER_CATEGORY=20

LRS=(
  0.02 
  0.01
  0.005
  0.001
  0.0005
)

for MODEL in rnn_gen lstm_gen gru_gen; do
  for LR in "${LRS[@]}"; do
    LR_TAG="${LR/./p}"
    RUN_NAME="${MODEL}_opt${OPTIMIZER}_h${HIDDEN_SIZE}_lr${LR_TAG}"

    if [[ -f "outputs/generation/${RUN_NAME}/summary_metrics.csv" ]]; then
      echo "Skipping completed run: ${RUN_NAME}"
      continue
    fi

    echo "== generation sweep: model=${MODEL}, lr=${LR} =="
    python3 train_generation.py \
      --model "${MODEL}" \
      --epochs "${EPOCHS}" \
      --batch-size "${BATCH_SIZE}" \
      --optimizer "${OPTIMIZER}" \
      --hidden-size "${HIDDEN_SIZE}" \
      --lr "${LR}" \
      --dropout "${DROPOUT}" \
      --clip-grad-norm "${CLIP_GRAD_NORM}" \
      --samples-per-category "${SAMPLES_PER_CATEGORY}" \
      --max-samples-per-epoch "${MAX_SAMPLES}" \
      --run-name "${RUN_NAME}"
  done
done

echo
echo "Finished generation LR sweep. Check:"
echo "  outputs/generation/"
echo
echo "Suggested comparison metrics:"
echo "  summary_metrics.csv -> best_train_loss"
echo "  training_loss_curve.png"
echo "  generated_samples.txt"
echo "  generated_metrics.csv"
