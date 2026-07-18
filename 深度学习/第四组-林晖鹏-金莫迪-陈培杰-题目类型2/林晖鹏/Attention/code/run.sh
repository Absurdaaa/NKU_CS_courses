#!/usr/bin/env bash

set -euo pipefail


# 这是 lab3 的总控脚本。
# 默认按“先扫参 -> 再正式训练 -> 最后整理报告素材”的顺序跑完。
#
# 当前默认实验设置：
# - epochs = 100
# - batch_size = 256
# - 默认过滤后数据规模约 10522 对句子
#
# 如果你中途想停在某一步，也可以直接单独跑对应的 run_0X_*.sh。

echo "== [1/5] Sweep core models =="
bash run_01_sweep_core_models.sh

echo "== [2/5] Sweep scheduled sampling extension =="
bash run_02_sweep_scheduled_sampling.sh

echo "== [3/5] Train best core models =="
bash run_03_train_best_core_models.sh

echo "== [4/5] Train best scheduled sampling extension =="
bash run_04_train_best_scheduled_sampling.sh

echo "== [5/5] Generate report assets =="
bash run_05_generate_report_assets.sh

echo "All lab3 stages completed."
