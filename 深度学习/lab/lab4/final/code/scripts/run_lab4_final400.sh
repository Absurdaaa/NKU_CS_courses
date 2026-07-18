#!/usr/bin/env bash
# Lab4 400-epoch 最终训练：三个模型统一训练 400 轮，FID 每 10 轮评估一次（5000 样本）。
# gan / gan_deep 用优化配置（去 Dropout + TTUR + 标签平滑），dcgan 用标准 lr=0.0005。
# 双卡：GPU0 跑 gan_deep -> gan（串行），GPU1 跑 dcgan。
# 用法：PY=<conda python> bash scripts/run_lab4_final400.sh （可 setsid 后台）

set -uo pipefail

cd "$(dirname "$0")/.."
PY=${PY:-python3}
COMMON="--epochs 400 --batch-size 512 --latent-dim 100 --num-workers 4 --fid-eval-every 10 --fid-samples 5000 --optimizer adam"
mkdir -p outputs/logs

echo "[$(date '+%F %T')] START 400-epoch finals"

# GPU0：gan_deep（优化）-> gan（优化），串行
(
  CUDA_VISIBLE_DEVICES=0 $PY train.py --model gan_deep --run-name final_gan_deep_opt $COMMON \
    --lr 0.0002 --d-lr 0.0005 --label-smoothing 0.1 --disc-dropout 0.0 > outputs/logs/e400_gan_deep.log 2>&1
  CUDA_VISIBLE_DEVICES=0 $PY train.py --model gan --run-name final_gan_opt $COMMON \
    --lr 0.0002 --d-lr 0.0005 --label-smoothing 0.1 > outputs/logs/e400_gan.log 2>&1
) &
P0=$!

# GPU1：dcgan（标准）
(
  CUDA_VISIBLE_DEVICES=1 $PY train.py --model dcgan --run-name final_dcgan_fashionmnist $COMMON \
    --lr 0.0005 > outputs/logs/e400_dcgan.log 2>&1
) &
P1=$!

wait $P0 $P1
echo "[$(date '+%F %T')] 400-epoch finals done"
