#!/usr/bin/env bash

set -euo pipefail

cd /Users/linshangjin/Desktop/DeepLearning/lab2

# 这个脚本专门用来比较“开/关梯度裁剪”时的训练行为。
# 默认先对 RNN 做对照，因为普通 RNN 更容易出现梯度不稳定。

COMMON_ARGS=(
  --optimizer adam
  --batch-size 128
  --epochs 30
  --hidden-size 128
)

echo "== RNN with gradient clipping =="
python3 train.py \
  --model rnn \
  --lr 0.001 \
  --clip-grad-norm 5.0 \
  --run-name rnn_clip "${COMMON_ARGS[@]}"

echo "== RNN without gradient clipping =="
python3 train.py \
  --model rnn \
  --lr 0.001 \
  --clip-grad-norm 0 \
  --run-name rnn_no_clip "${COMMON_ARGS[@]}"

echo "== LSTM with gradient clipping =="
python3 train.py \
  --model lstm \
  --lr 0.01 \
  --clip-grad-norm 5.0 \
  --run-name lstm_clip "${COMMON_ARGS[@]}"

echo "== LSTM without gradient clipping =="
python3 train.py \
  --model lstm \
  --lr 0.01 \
  --clip-grad-norm 0 \
  --run-name lstm_no_clip "${COMMON_ARGS[@]}"

echo
echo "Finished. Check these directories:"
echo "  outputs/rnn/rnn_clip"
echo "  outputs/rnn/rnn_no_clip"
echo "  outputs/lstm/lstm_clip"
echo "  outputs/lstm/lstm_no_clip"
echo
echo "Key files to compare:"
echo "  gradient_norms.png"
echo "  gradient_metrics.csv"
echo "  epoch_metrics.csv"
echo "  summary_metrics.csv"
