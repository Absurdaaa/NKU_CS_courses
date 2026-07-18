#!/usr/bin/env bash

set -euo pipefail

cd /Users/linshangjin/Desktop/DeepLearning/lab2

python3 sample_best_generation.py \
  --models rnn_gen lstm_gen gru_gen \
  --sample-categories all \
  --samples-per-category 20 \
  --sample-max-length 20

echo
echo "Finished resampling from best generation checkpoints. Check:"
echo "  outputs/generation/resampled/"
echo
echo "Typical outputs:"
echo "  outputs/generation/resampled/<best_run_name>_resampled/generated_samples.txt"
echo "  outputs/generation/resampled/<best_run_name>_resampled/generated_metrics.csv"
