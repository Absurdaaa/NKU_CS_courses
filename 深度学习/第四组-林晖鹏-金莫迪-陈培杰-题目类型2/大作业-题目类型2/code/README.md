# C3Net — 显式中心-周边对比显著性检测

本目录是课程项目"深度学习及应用（高阶课）"的实验代码，基于 ResNet-18 + FPN 框架，以 **CSCM（Center-Surround Contrast Modulation）** 为核心模块，实现了多个显著性物体检测（SOD）方法的统一训练、评测与消融管线。

## 环境

```bash
cd code
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

依赖：`torch>=2.2.0`、`torchvision>=0.17.0`、`pillow`、`numpy`、`thop`、`pytest`。详见 `requirements.txt`。

## 目录结构

```
code/
├── config.py              # 全局默认配置
├── train.py               # 训练入口
├── eval.py                # 评测入口
├── infer.py               # 单张/批量推理
├── requirements.txt       # Python 依赖
├── data/                  # 数据集存放目录
├── datasets/              # 数据加载（ECSSDDataset、transforms）
├── engine/                # 训练/评测循环（train_one_epoch, evaluate）
├── model/                 # 模型实现（见下方模型列表）
├── utils/                 # 指标（MAE、F-measure、IoU 等）、日志、工具函数
├── splits/                # 数据划分 JSON（ECSSD、DUTS、DUT-OMRON、CAMO）
├── runs/                  # 训练输出目录（自动生成）
└── scripts/               # 脚本集合
    ├── download_ecssd.py  # ECSSD 数据集下载与整理
    ├── exp/               # 实验启动脚本 (.sh)
    ├── analysis/          # 结果分析脚本 (.py)
    └── vis/               # 可视化脚本 (.py)
```

## 数据集准备

### ECSSD（主数据集）

```bash
# 下载并整理 ECSSD（1000 张，700 train / 300 test，seed 42）
python scripts/download_ecssd.py --output-root data/ECSSD

# 若已下载 zip 到缓存目录，跳过重复下载
python scripts/download_ecssd.py --output-root data/ECSSD \
  --cache-dir data/raw/ECSSD --skip-download
```

整理后的目录结构：

```
data/ECSSD/
├── images/
│   ├── train/    # 700 张
│   └── test/     # 300 张
└── masks/
    ├── train/    # 700 张
    └── test/     # 300 张
```

### DUTS-TE（外部测试集，5019 张）

从 [DUTS 主页](http://saliencydetection.net/duts/) 下载 `DUTS-TE.zip`，解压后按以下结构放置：

```
data/DUTS-TE/
├── images/       # DUTS-TE-image/
└── masks/        # DUTS-TE-mask/
```

### DUT-OMRON（外部测试集，5168 张）

从 [DUT-OMRON 主页](http://saliencydetection.net/dut-omron/) 下载 `DUT-OMRON-image.zip`，解压后按以下结构放置：

```
data/DUT-OMRON/
├── images/
└── masks/
```

### CAMO（伪装物体测试集，250 张）

从 [CAMO 仓库](https://github.com/dengpingfan/SINet) 下载 COCO 格式的测试集，放置于：

```
data/CAMO/
├── images/
└── masks/
```

## 支持的模型

| 注册名 | 来源 | 说明 |
|--------|------|------|
| `resnet18` | 基线 | ResNet-18 + 轻量 FPN 解码器 |
| `c3net_r18` | **本文** | CSCM + CA-ASPP + 边缘分支 + 深监督 |
| `ctdnet_r18` | 本文（对比） | 语义/空间/边界三路分工解码器 |
| `poolnet_r18` | PoolNet (Liu et al., 2019) | 金字塔池化全局上下文 |
| `egnet_r18` | EGNet (Zhao et al., 2019) | 边缘引导显著性检测 |
| `pfa_r18` | PFAN (Zhao et al., 2019) | 金字塔特征注意力 |
| `sinet_r18` | SINet (Fan et al., 2020) | 伪装物体检测（复用为对比） |
| `dss_r18` | DSS (Hou et al., 2017) | 深监督短连接 |
| `f3net_r18` | F3Net (Wei et al., 2020) | 结构损失 + 特征反馈 |

所有模型遵循统一张量契约：输入 `B×3×H×W`，输出 `B×1×H×W` 单通道 logits。

## 数据划分

`splits/` 目录包含以下划分文件：

| 文件 | 内容 |
|------|------|
| `official_split.json` | ECSSD 课程固定 700 train / 300 test |
| `trainval_seed_42.json` | 700 中固定 600 train / 100 val（seed 42）|
| `trainval_seed_3407.json` | 同上，seed 3407 |
| `trainval_seed_2026.json` | 同上，seed 2026 |
| `duts_te.json` | DUTS-TE 外部测试集（5019 张）|
| `dutomron.json` | DUT-OMRON 外部测试集（5168 张）|
| `camo.json` | CAMO 伪装物体测试集（250 张）|

## 常用命令

所有命令在 `code/` 目录下执行。

### 训练

```bash
# 训练基线（默认参数）
python train.py

# 训练 C3Net，200 epoch
python train.py --model c3net_r18 --epochs 200 --output-dir runs/c3net_r18

# 使用特定种子划分
python train.py --model c3net_r18 --split-file splits/trainval_seed_42.json

# 指定 GPU
python train.py --model c3net_r18 --device cuda --gpu-ids 0
```

**训练关键参数**（完整列表见 `config.py` 的 `DEFAULTS`）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model` | `resnet18` | 模型注册名 |
| `--data-root` | `data/ECSSD` | 数据集根目录 |
| `--split-file` | `splits/trainval_seed_42.json` | 数据划分文件 |
| `--epochs` | `100` | 训练轮数 |
| `--batch-size` | `16` | 批大小 |
| `--lr` | `3e-4` | 学习率 |
| `--image-size` | `352` | 输入分辨率 |
| `--grad-clip` | `1.0` | 梯度裁剪 |
| `--seed` | `42` | 随机种子 |
| `--output-dir` | `runs/{model}` | 输出目录 |
| `--pretrained` | (flag) | 使用 ImageNet 预训练权重 |

### 评测

```bash
# 评测 C3Net 在 ECSSD 上
python eval.py --model c3net_r18 --checkpoint runs/c3net_r18/best.pt

# 跨数据集评测（DUTS-TE）
python eval.py --model c3net_r18 --checkpoint runs/c3net_r18/best.pt \
  --data-root data/DUTS-TE --split-file splits/duts_te.json

# 评测时指定输出目录（保存 pred 图像和指标 JSON）
python eval.py --model c3net_r18 --checkpoint runs/c3net_r18/best.pt \
  --output-dir eval_output/c3net_duts
```

### 推理

```bash
# 单张推理
python infer.py --input data/ECSSD/images/test/0004.jpg \
  --checkpoint runs/c3net_r18/best.pt

# 批量推理
python infer.py --input data/ECSSD/images/test \
  --checkpoint runs/c3net_r18/best.pt --output-dir predictions
```

### 批量实验

实验 Shell 脚本集中在 `scripts/exp/`，典型用法：

```bash
# 跑基线
bash scripts/exp/run_resnet18_baseline.sh

# 跑 C3Net 完整消融（累积 + LOO）
bash scripts/exp/run_c3net_ablation.sh

# 跑主对比（所有 9 个模型）
bash scripts/exp/run_main_comparison.sh

# 跑数据效率实验（n=100/200/400/600）
bash scripts/exp/run_data_efficiency.sh

# 跑多阶段对比增强
bash scripts/exp/run_method_enh.sh

# 三种子填充实验（seed 42/3407/2026）
bash scripts/exp/run_c3net_3seed_fill.sh
```

### 分析 & 可视化

```bash
# 汇总数据效率实验结果（生成表格/数据）
python scripts/analysis/summarize_data_efficiency.py

# 汇总方法增强实验结果
python scripts/analysis/summarize_method_enh.py

# 汇总 CAMO 伪装反例结果
python scripts/analysis/summarize_camo_h3.py

# 汇总所有主实验 CSV → 统一指标表
python scripts/analysis/summarize_test_csvs.py

# 可视化 CSCM 注意力
python scripts/vis/visualize_cscm_insight.py

# 可视化 C3Net 各阶段中间特征
python scripts/vis/visualize_c3net_stages.py

# 生成定性对比网格图
python scripts/vis/render_qual_grid.py
```

## 运行输出

训练完成后，`--output-dir`（默认 `runs/{model}/`）下生成：

```
runs/c3net_r18/20250601-120000/
├── best.pt          # 最优权重（按 val max-F）
├── last.pt          # 最后一轮权重
├── config.json      # 本次运行的完整配置
├── metrics.csv      # 每轮训练/验证指标
├── summary.json     # 汇总指标
└── train.log        # 训练日志
```

## 指标说明

- **max-F**：扫描阈值取最优 F-measure（$\beta^2=0.3$），主指标
- **MAE**：平均绝对误差
- **IoU**：交并比
- **S-measure**：结构相似性度量
- **E-measure**：增强对齐度量
