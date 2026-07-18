#!/usr/bin/env bash

set -euo pipefail


# 作用：
# 1. 对 Luong attention 的三种 scoring function 做学习率扫描
# 2. 统一使用 200 epochs / batch_size=512 / hidden_size=128
# 3. 输出目录默认放到 outputs512，方便和当前正式实验保持一致
#
# 重点比较：
# - dot / general / concat 三种打分方式的 best_val_acc
# - test_acc / test_exact_match / test_bleu
# - total_train_time_sec / peak_memory_mb

python3 sweep_lr.py \
  --model seq2seq_luong_dot \
  --optimizer adam \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --teacher-forcing-ratio 0.5 \
  --max-samples 12000 \
  --output-dir outputs512 \
  --lrs 0.003 0.002 0.001 0.0005 0.0003

python3 sweep_lr.py \
  --model seq2seq_luong_general \
  --optimizer adam \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --teacher-forcing-ratio 0.5 \
  --max-samples 12000 \
  --output-dir outputs512 \
  --lrs 0.003 0.002 0.001 0.0005 0.0003

python3 sweep_lr.py \
  --model seq2seq_luong_concat \
  --optimizer adam \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --teacher-forcing-ratio 0.5 \
  --max-samples 12000 \
  --output-dir outputs512 \
  --lrs 0.003 0.002 0.001 0.0005 0.0003
