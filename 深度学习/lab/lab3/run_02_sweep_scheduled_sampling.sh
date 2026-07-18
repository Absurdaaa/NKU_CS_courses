#!/usr/bin/env bash

set -euo pipefail


# 作用：
# 1. 跑扩展实验：Bahdanau attention + Scheduled Sampling
# 2. 先只对 Bahdanau 版本做扩展，方便和主实验直接比较
# 3. 跑完后重点看：
#    - seq2seq_attn 和 seq2seq_attn + scheduled sampling 的差别
#    - test_bleu / test_exact_match / total_train_time_sec

python3 sweep_lr.py \
  --model seq2seq_attn \
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
  --lrs 0.003 0.002 0.001 0.0005 0.0003
  
  
python3 sweep_lr.py \
  --model seq2seq_luong \
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
  --lrs 0.003 0.002 0.001 0.0005 0.0003
