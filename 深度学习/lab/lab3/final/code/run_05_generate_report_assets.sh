#!/usr/bin/env bash

set -euo pipefail


# 作用：
# 1. 汇总最优 run 的关键指标
# 2. 生成三模型对比图、长度分桶图、定性样例表
# 3. 输出到 实验模板/fig/generated 和 实验模板/tables

python3 scripts/generate_report_assets.py
