#!/usr/bin/env bash

set -euo pipefail

cd /Users/linshangjin/Desktop/DeepLearning/lab2

for MODEL in rnn_gen lstm_gen gru_gen; do
  python3 train_generation.py \
    --model "${MODEL}" \
    --epochs 20 \
    --batch-size 128 \
    --optimizer adam \
    --hidden-size 128 \
    --lr 0.001 \
    --dropout 0.0 \
    --clip-grad-norm 0 \
    --samples-per-category 20 \
    --run-name "${MODEL}_baseline"
done

echo
echo "Finished. Check:"
echo "  outputs/generation/rnn_gen_baseline"
echo "  outputs/generation/lstm_gen_baseline"
echo "  outputs/generation/gru_gen_baseline"
echo
echo "Key files:"
echo "  model_structure.txt"
echo "  epoch_metrics.csv"
echo "  summary_metrics.csv"
echo "  training_loss_curve.png"
echo "  generated_samples.txt"
echo "  generated_metrics.csv"
