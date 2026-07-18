#!/usr/bin/env bash

set -euo pipefail

# cd /Users/linshangjin/Desktop/DeepLearning/lab2

# 这个脚本现在只做学习率扫描。
# 你把所有模型都扫完之后，把 outputs 结果留给我，我再帮你：
# 1. 检查每个模型的最优学习率
# 2. 选报告里最终使用的 run
# 3. 整理表格、曲线和报告正文
#
# 当前统一设置：
# - optimizer = adam
# - batch_size = 128
# - epochs = 30
# - hidden_size = 128
# - clip_grad_norm = 0（关闭手动梯度裁剪）
#
# 报告必做：
# 1. 原始 RNN
# 2. LSTM
# 加分可选：
# 3. 手写 myLSTM
# 4. 手写 myGRU

###############################################################################
# 一、必做部分
###############################################################################

# 原始 RNN
python3 sweep_lr.py \
  --model rnn \
  --optimizer adam \
  --epochs 100 \
  --batch-size 128 \
  --hidden-size 128 \
  --clip-grad-norm 0 \
  --lrs 0.02 0.01 0.005 0.001 0.0005

# LSTM
python3 sweep_lr.py \
  --model lstm \
  --optimizer adam \
  --epochs 100 \
  --batch-size 128 \
  --hidden-size 128 \
  --clip-grad-norm 0 \
  --lrs 0.02 0.01 0.005 0.001 0.0005

###############################################################################
# 二、加分项（可选）
###############################################################################

# 手写 LSTM
python3 sweep_lr.py \
  --model myLSTM \
  --optimizer adam \
  --epochs 100 \
  --batch-size 128 \
  --hidden-size 128 \
  --clip-grad-norm 0 \
  --lrs 0.02 0.01 0.005 0.001 0.0005

# 手写 GRU
python3 sweep_lr.py \
  --model myGRU \
  --optimizer adam \
  --epochs 100 \
  --batch-size 128 \
  --hidden-size 128 \
  --clip-grad-norm 0 \
  --lrs 0.02 0.01 0.005 0.001 0.0005

###############################################################################
# 三、运行结束后你主要会用到这些目录
###############################################################################

# outputs/rnn/
# outputs/lstm/
# outputs/myLSTM/
# outputs/myGRU/
