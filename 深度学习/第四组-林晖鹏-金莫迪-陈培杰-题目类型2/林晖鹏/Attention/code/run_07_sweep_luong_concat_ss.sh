#!/usr/bin/env bash

set -euo pipefail


# 作用：
# 1. 对 Luong concat + Scheduled Sampling 做单独学习率扫描
# 2. 保持和当前正式实验一致的 200 epochs / batch_size=512 / hidden_size=128
# 3. 输出目录固定到 outputs512，方便后续直接替换报告里的扩展实验表
#
# 重点比较：
# - best_val_acc
# - test_acc / test_exact_match / test_bleu
# - total_train_time_sec

python3 sweep_lr.py \
  --model seq2seq_luong_concat \
  --optimizer adam \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --teacher-forcing-ratio 1 \
  --scheduled-sampling \
  --scheduled-sampling-strategy inverse_sigmoid \
  --scheduled-sampling-inverse-sigmoid-k 10 \
  --scheduled-sampling-min-ratio 0.1 \
  --max-samples 12000 \
  --output-dir outputs512 \
  --lrs 0.003 0.002 0.001 0.0005 0.0003
