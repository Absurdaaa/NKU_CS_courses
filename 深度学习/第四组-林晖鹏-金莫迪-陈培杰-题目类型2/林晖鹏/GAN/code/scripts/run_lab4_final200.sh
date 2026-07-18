#!/usr/bin/env bash
# Lab4 200-epoch final 训练：三模型统一 lr=0.0005，FID 每 5 轮(5000 样本)。
# 双卡分配：dcgan 独占 GPU0；gan_deep + gan 在 GPU1 串行（避免同卡两个 Inception 同时算 FID 撞显存）。
# 用法：PY=<conda python> bash scripts/run_lab4_final200.sh （可 setsid 后台）

set -uo pipefail

cd "$(dirname "$0")/.."
PY=${PY:-python3}
LR=0.0005
COMMON="--optimizer adam --epochs 200 --batch-size 512 --latent-dim 100 --num-workers 4 --fid-eval-every 5 --fid-samples 5000 --lr $LR"
mkdir -p outputs/logs

echo "[$(date '+%F %T')] START 200-epoch final (lr=$LR)"

# GPU0：dcgan（最重，独占）
(
  CUDA_VISIBLE_DEVICES=0 $PY train.py --model dcgan --run-name final_dcgan_fashionmnist $COMMON
) > outputs/logs/f200_dcgan.log 2>&1 &
P0=$!

# GPU1：gan_deep -> gan 串行
(
  CUDA_VISIBLE_DEVICES=1 $PY train.py --model gan_deep --run-name final_gan_deep_fashionmnist $COMMON > outputs/logs/f200_gan_deep.log 2>&1
  CUDA_VISIBLE_DEVICES=1 $PY train.py --model gan      --run-name final_gan_fashionmnist      $COMMON > outputs/logs/f200_gan.log 2>&1
) &
P1=$!

wait $P0 $P1
echo "[$(date '+%F %T')] finals done"

$PY scripts/generate_report_assets.py \
  --gan-run final_gan_fashionmnist \
  --gan-deep-run final_gan_deep_fashionmnist \
  --dcgan-run final_dcgan_fashionmnist \
  --fixed-sample-count 8 \
  --latent-analysis-count 100 \
  --latent-analysis-picks 5 \
  --latent-perturbations 3 > outputs/logs/f200_report.log 2>&1

echo "[$(date '+%F %T')] ALL DONE"
