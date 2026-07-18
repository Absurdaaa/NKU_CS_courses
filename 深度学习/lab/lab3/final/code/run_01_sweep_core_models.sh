#!/usr/bin/env bash

set -euo pipefail


# 作用：
# 1. 给三个主模型扫学习率
# 2. 统一使用 200 epochs / batch_size=512
# 3. 跑完后会在 outputs/<model>/ 下生成：
#    - <model>_adam_lr_sweep_summary.csv
#    - <model>_adam_best_lr.txt
#
# 当前建议重点记录的指标：
# - best_val_acc
# - best_val_loss
# - best_val_exact_match
# - test_acc
# - test_exact_match
# - test_bleu
# - total_train_time_sec
# - avg_epoch_time_sec
# - param_count
# - flops_per_sample
# - peak_memory_mb

python3 sweep_lr.py \
  --model seq2seq_rnn \
  --optimizer adam \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --teacher-forcing-ratio 0.5 \
  --max-samples 12000 \
  --lrs 0.003 0.002 0.001 0.0005 0.0003

python3 sweep_lr.py \
  --model seq2seq_attn \
  --optimizer adam \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --teacher-forcing-ratio 0.5 \
  --max-samples 12000 \
  --lrs 0.003 0.002 0.001 0.0005 0.0003

python3 sweep_lr.py \
  --model seq2seq_luong \
  --optimizer adam \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --teacher-forcing-ratio 0.5 \
  --max-samples 12000 \
  --lrs 0.003 0.002 0.001 0.0005 0.0003
