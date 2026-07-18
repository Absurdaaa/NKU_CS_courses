#!/usr/bin/env bash

set -euo pipefail


# 作用：
# 1. 读取三个模型 sweep 后的 best_lr.txt
# 2. 用最优学习率各正式训练一遍
# 3. 正式输出目录里会包含：
#    - model_structure.txt
#    - epoch_metrics.csv
#    - summary_metrics.csv
#    - run_metadata.json
#    - training_curves.png
#    - sample_translations.csv
#    - all_test_translations.csv
#    - length_bucket_metrics.csv
#    - attention_examples/*.png（注意力模型）

get_best_lr() {
  local path="$1"
  grep '^best_learning_rate=' "$path" | cut -d= -f2
}

RNN_LR=$(get_best_lr "outputs/seq2seq_rnn/seq2seq_rnn_adam_best_lr.txt")
BAHDANAU_LR=$(get_best_lr "outputs/seq2seq_attn/seq2seq_attn_adam_best_lr.txt")
LUONG_LR=$(get_best_lr "outputs/seq2seq_luong/seq2seq_luong_adam_best_lr.txt")

python3 train.py \
  --model seq2seq_rnn \
  --run-name final_seq2seq_rnn_b512_e200 \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --lr "$RNN_LR" \
  --teacher-forcing-ratio 0.5 \
  --max-samples 12000

python3 train.py \
  --model seq2seq_attn \
  --run-name final_seq2seq_attn_b512_e200  \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --lr "$BAHDANAU_LR" \
  --teacher-forcing-ratio 0.5 \
  --max-samples 12000

python3 train.py \
  --model seq2seq_luong \
  --run-name final_seq2seq_luong_b512_e200 \
  --epochs 200 \
  --batch-size 512 \
  --hidden-size 128 \
  --lr "$LUONG_LR" \
  --teacher-forcing-ratio 0.5 \
  --max-samples 12000
