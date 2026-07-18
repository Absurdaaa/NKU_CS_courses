#!/usr/bin/env bash

set -euo pipefail


# 这是 lab4 的总控脚本。
# 默认按“先扫学习率 -> 再正式训练 -> 最后整理报告素材”的顺序组织。
#
# 本实验的核心任务：
# - 训练基础版 GAN（FashionMNIST，老师原始单隐藏层 MLP）
# - 训练加深版 GAN（gan_deep，自由调整的深层 MLP，作对比）
# - 训练卷积版 DCGAN（FashionMNIST，加分项）
# - 导出 G / D loss 曲线与模型结构
# - 生成 8 张固定噪声样例图
# - 生成 5 组潜变量扰动分析图（每组 3 次调整，共 15 x 8 张）
#
# 推荐流程：
# 1. 分别为 gan / gan_deep / dcgan 扫学习率
# 2. 用最佳学习率做正式训练
# 3. 汇总报告所需图表与表格


LRS="0.001 0.0005 0.0002 0.0001"
COMMON="--optimizer adam --epochs 100 --batch-size 512 --latent-dim 100"


echo "== [1/7] Sweep GAN (original) learning rates =="
python3 sweep_lr.py --model gan      $COMMON --lrs $LRS

echo "== [2/7] Sweep GAN (deep) learning rates =="
python3 sweep_lr.py --model gan_deep $COMMON --lrs $LRS

echo "== [3/7] Sweep DCGAN learning rates =="
python3 sweep_lr.py --model dcgan    $COMMON --lrs $LRS


echo "== [4/7] Train final GAN (original) =="
python3 train.py --model gan      --run-name final_gan_fashionmnist      $COMMON --lr 0.0002

echo "== [5/7] Train final GAN (deep) =="
python3 train.py --model gan_deep --run-name final_gan_deep_fashionmnist $COMMON --lr 0.0002

echo "== [6/7] Train final DCGAN =="
python3 train.py --model dcgan    --run-name final_dcgan_fashionmnist    $COMMON --lr 0.0002


echo "== [7/7] Generate report assets =="
python3 scripts/generate_report_assets.py \
  --gan-run final_gan_fashionmnist \
  --gan-deep-run final_gan_deep_fashionmnist \
  --dcgan-run final_dcgan_fashionmnist \
  --fixed-sample-count 8 \
  --latent-analysis-count 100 \
  --latent-analysis-picks 5 \
  --latent-perturbations 3


echo "All lab4 stages completed."
