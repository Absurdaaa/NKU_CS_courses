#!/usr/bin/env bash

set -euo pipefail


# 作用：
# 1. 正式训练 Scheduled Sampling 扩展实验
# 2. 这里默认还是基于 Bahdanau attention
# 3. 建议最后和 final_seq2seq_attn_bs256_e100 做一一对比

get_best_lr() {
  local path="$1"
  grep '^best_learning_rate=' "$path" | cut -d= -f2
}

ATTN_LR=$(get_best_lr "outputs/seq2seq_attn/seq2seq_attn_adam_best_lr.txt")

python3 train.py \
  --model seq2seq_attn \
  --run-name final_seq2seq_attn_ss_bs512_e200 \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --lr "$ATTN_LR" \
  --teacher-forcing-ratio 1 \
  --scheduled-sampling \
  --scheduled-sampling-strategy inverse_sigmoid \
  --scheduled-sampling-inverse-sigmoid-k 10 \
  --scheduled-sampling-min-ratio 0.1 \
  --max-samples 12000


ATTN_LR=$(get_best_lr "outputs/seq2seq_luong/seq2seq_luong_adam_best_lr.txt")

python3 train.py \
  --model seq2seq_luong \
  --run-name final_seq2seq_luong_ss_bs512_e200 \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --lr "$ATTN_LR" \
  --teacher-forcing-ratio 1 \
  --scheduled-sampling \
  --scheduled-sampling-strategy inverse_sigmoid \
  --scheduled-sampling-inverse-sigmoid-k 10 \
  --scheduled-sampling-min-ratio 0.1 \
  --max-samples 12000