# Lab4 GAN Framework

本目录已按 `LAB_PROJECT_STRUCTURE.md` 规范整理成和 `lab1`、`lab2`、`lab3` 一致的多文件实验骨架，用于后续完成：

- 基础全连接 `GAN` 在 `FashionMNIST` 上的训练
- 卷积版 `DCGAN` 在 `FashionMNIST` 上的训练
- 学习率扫描、正式训练输出、报告素材生成

## 目录结构

```text
lab4/
├── README.md
├── docs/
│   ├── GAN实验报告.docx
│   └── 要求.md
├── data/
├── outputs/
├── run.sh
├── sweep_lr.py
├── train.py
├── scripts/
│   └── generate_report_assets.py
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── constants.py
│   ├── data.py
│   ├── engine.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── dcgan.py
│   │   ├── gan.py
│   │   └── registry.py
│   └── utils/
│       ├── __init__.py
│       ├── io.py
│       ├── paths.py
│       ├── plotting.py
│       ├── profiling.py
│       └── runtime.py
├── old/
│   ├── dcgan_faces_tutorial.ipynb
│   └── gan-pytorch.ipynb
└── 实验模板/
    ├── fig/
    │   └── generated/
    ├── style/
    └── tables/
```

## 当前状态

这一步只完成工程骨架与文件职责整理，尚未实现实际训练逻辑。下一步会在这个骨架上补齐：

- `FashionMNIST` 数据加载与预处理
- `GAN / DCGAN` 模型实现
- 对抗训练循环
- 学习率扫描脚本
- 随机向量插值与报告图表生成

## 文件职责

- `train.py`
  - 单次正式训练入口
  - 后续负责读取配置、构建数据、构建模型、启动训练、保存结果
- `sweep_lr.py`
  - 学习率扫描入口
  - 后续负责分别对 `gan / dcgan` 扫描学习率，并写出最优学习率摘要
- `run.sh`
  - 批量运行脚本
  - 只保留当前实验真正要跑的命令模板
- `scripts/generate_report_assets.py`
  - 报告素材导出脚本
  - 后续负责整理 loss 曲线、生成样例、随机向量扰动图和表格
- `src/config.py`
  - CLI 参数和配置 dataclass
- `src/constants.py`
  - 图像尺寸、通道数、类别名、默认超参数等公共常量
- `src/data.py`
  - `FashionMNIST` 数据集读取、变换、DataLoader 构建
- `src/engine.py`
  - 训练循环、验证采样、checkpoint 保存、指标汇总
- `src/models/`
  - `gan.py`：基础全连接生成器/判别器
  - `dcgan.py`：卷积生成器/判别器
  - `registry.py`：统一注册模型名与构建逻辑
- `src/utils/`
  - `io.py`：CSV / JSON / txt 写出
  - `paths.py`：run_name 与输出路径规则
  - `plotting.py`：loss 曲线、样本网格、latent 扰动图
  - `profiling.py`：参数量、训练时间、显存统计
  - `runtime.py`：seed、设备、matplotlib 环境设置

## 预期输出规范

正式训练完成后，输出将落到：

```text
outputs/<model>/<run_name>/
```

至少预留给下阶段生成这些文件：

- `model_structure.txt`
- `epoch_metrics.csv`
- `summary_metrics.csv`
- `run_metadata.json`
- `best_model.pth`
- `training_curves.png`
- `generated_samples.png`
- `latent_edit_grid.png`

学习率扫描结果将预留为：

- `outputs/<model>/<model>_<optimizer>_lr_sweep_summary.csv`
- `outputs/<model>/<model>_<optimizer>_best_lr.txt`

报告素材将预留到：

- `实验模板/fig/generated/`
- `实验模板/tables/`
- `实验模板/generated_assets_manifest.txt`
