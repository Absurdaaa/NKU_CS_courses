#!/usr/bin/env bash
# Lab4 双卡总控：负载均衡扫 lr -> 选最优 lr -> 正式训练 -> 生成报告素材。
# 用法：PY=/path/to/python bash scripts/run_lab4_2gpu.sh
# 设计为可 nohup 后台运行，单个 run 失败不会中断整体（无 set -e）。

set -uo pipefail

cd "$(dirname "$0")/.."   # 切到 lab4 目录
PY=${PY:-python3}
LRS="0.001 0.0005 0.0002 0.0001"
# sweep 阶段用 2048 个样本算 FID（快, 足够选学习率）；final 用 5000（数值更稳, 见下方覆盖）。
COMMON="--optimizer adam --epochs 100 --batch-size 512 --latent-dim 100 --num-workers 4 --fid-eval-every 5 --fid-samples 2048"
FINAL_FID="--fid-samples 5000"
mkdir -p outputs/logs

echo "[$(date '+%F %T')] START orchestrator (PY=$PY)"

# ---------- Phase 1: 双卡负载均衡跑 sweep ----------
# GPU0: dcgan ×4(最慢) + gan ×2
(
  for lr in 0.001 0.0005 0.0002 0.0001; do
    CUDA_VISIBLE_DEVICES=0 $PY sweep_lr.py --model dcgan $COMMON --lrs $lr
  done
  for lr in 0.001 0.0005; do
    CUDA_VISIBLE_DEVICES=0 $PY sweep_lr.py --model gan $COMMON --lrs $lr
  done
) > outputs/logs/gpu0_sweep.log 2>&1 &
PID0=$!

# GPU1: gan_deep ×4 + gan ×2
(
  CUDA_VISIBLE_DEVICES=1 $PY sweep_lr.py --model gan_deep $COMMON --lrs 0.001 0.0005 0.0002 0.0001
  for lr in 0.0002 0.0001; do
    CUDA_VISIBLE_DEVICES=1 $PY sweep_lr.py --model gan $COMMON --lrs $lr
  done
) > outputs/logs/gpu1_sweep.log 2>&1 &
PID1=$!

wait $PID0 $PID1
echo "[$(date '+%F %T')] Phase1 sweeps done"

# ---------- Phase 2: 聚合 sweep 结果并挑最优 lr（已存在的 run 会被跳过） ----------
for M in gan gan_deep dcgan; do
  $PY sweep_lr.py --model $M $COMMON --lrs $LRS > outputs/logs/aggregate_$M.log 2>&1
done

GAN_LR=$(cat outputs/gan/gan_adam_best_lr.txt)
GAND_LR=$(cat outputs/gan_deep/gan_deep_adam_best_lr.txt)
DC_LR=$(cat outputs/dcgan/dcgan_adam_best_lr.txt)
echo "[$(date '+%F %T')] best lr -> gan=$GAN_LR gan_deep=$GAND_LR dcgan=$DC_LR"

# ---------- Phase 3: 用最优 lr 正式训练（双卡并行） ----------
CUDA_VISIBLE_DEVICES=0 $PY train.py --model gan      --run-name final_gan_fashionmnist      $COMMON $FINAL_FID --lr $GAN_LR  > outputs/logs/final_gan.log 2>&1 &
CUDA_VISIBLE_DEVICES=0 $PY train.py --model gan_deep --run-name final_gan_deep_fashionmnist $COMMON $FINAL_FID --lr $GAND_LR > outputs/logs/final_gan_deep.log 2>&1 &
CUDA_VISIBLE_DEVICES=1 $PY train.py --model dcgan    --run-name final_dcgan_fashionmnist    $COMMON $FINAL_FID --lr $DC_LR   > outputs/logs/final_dcgan.log 2>&1 &
wait
echo "[$(date '+%F %T')] Phase3 finals done"

# ---------- Phase 4: 生成报告素材 ----------
$PY scripts/generate_report_assets.py \
  --gan-run final_gan_fashionmnist \
  --gan-deep-run final_gan_deep_fashionmnist \
  --dcgan-run final_dcgan_fashionmnist \
  --fixed-sample-count 8 \
  --latent-analysis-count 100 \
  --latent-analysis-picks 5 \
  --latent-perturbations 3 > outputs/logs/report_assets.log 2>&1

echo "[$(date '+%F %T')] ALL DONE"
