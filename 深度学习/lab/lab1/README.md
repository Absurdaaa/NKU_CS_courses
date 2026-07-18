# Lab1 Project Guide

本目录已经按“代码 / 数据 / 结果 / 报告”分开整理，便于提交和查阅。

## 顶层结构

```text
lab1/
├── code/         # 所有实验代码
├── data/         # CIFAR-10 数据
├── outputs/      # 训练输出、日志、权重
├── docs/         # 实验要求与其他文档
├── 实验模板/      # LaTeX 报告、图片、表格、参考文献
└── README.md
```

## 教师快速定位

如果只需要快速检查本次实验代码，建议优先查看：

- `code/train.py`
  - 单次训练入口
- `code/sweep_lr.py`
  - 学习率扫描入口
- `code/src/models/`
  - 各模型实现：`simple_cnn.py`、`resnet.py`、`densenet.py`、`mobilenet.py`、`res2net.py`
- `code/src/engine.py`
  - 训练、验证、测试主循环
- `code/src/data.py`
  - 数据集加载与划分
- `code/scripts/generate_report_assets.py`
  - 报告图表生成
- `code/scripts/generate_gradcam_report.py`
  - Grad-CAM 可视化生成
- `实验模板/main.tex`
  - 实验报告正文

## code/ 结构

```text
code/
├── train.py
├── sweep_lr.py
├── src/
│   ├── config.py
│   ├── constants.py
│   ├── data.py
│   ├── engine.py
│   ├── models/
│   │   ├── registry.py
│   │   ├── simple_cnn.py
│   │   ├── resnet.py
│   │   ├── densenet.py
│   │   ├── mobilenet.py
│   │   └── res2net.py
│   └── utils/
│       ├── io.py
│       ├── paths.py
│       ├── plotting.py
│       ├── profiling.py
│       ├── runtime.py
│       └── wandb_logger.py
├── scripts/
│   ├── generate_report_assets.py
│   ├── generate_gradcam_report.py
│   └── plot_all_run_curves.py
└── legacy/
    ├── cnn-pytorch-cifar10.py
    └── cnn-pytorch-cifar10.ipynb
```

## 运行方式

单次训练：

```bash
python3 code/train.py --model simple_cnn --optimizer sgd --epochs 10
python3 code/train.py --model resnet20 --optimizer sgd --lr 0.05
python3 code/train.py --model densenet_bc_100 --optimizer sgd --lr 0.2
python3 code/train.py --model mobilenet_v1 --optimizer sgd --lr 0.05
python3 code/train.py --model res2net29_8c64w --optimizer sgd --lr 0.05
```

学习率扫描：

```bash
python3 code/sweep_lr.py --model simple_cnn --optimizer sgd --batch-size 512 --epochs 100 --lrs 0.2 0.1 0.05 0.02 0.01 0.005
python3 code/sweep_lr.py --model resnet20 --optimizer sgd --batch-size 512 --epochs 100 --lrs 0.2 0.1 0.05 0.02 0.01 0.005
```

报告资源生成：

```bash
python3 code/scripts/generate_report_assets.py
python3 code/scripts/generate_gradcam_report.py
```

## 输出说明

训练输出默认保存在：

```text
outputs/<model_name>/<run_name>/
```

典型内容包括：

- `best_model.pth`
- `epoch_metrics.csv`
- `summary_metrics.csv`
- `class_accuracy.csv`
- `model_structure.txt`

学习率扫描还会生成：

- `<model>_sgd_lr_sweep_summary.csv`
- `<model>_sgd_best_lr.txt`

## 报告相关

- LaTeX 正文：`实验模板/main.tex`
- 编译后的 PDF：`实验模板/main.pdf`
- 参考文献：`实验模板/reference.bib`
- 图表资源：`实验模板/fig/generated/`
- 表格资源：`实验模板/tables/`

## 说明

- `data/`、`outputs/`、`实验模板/` 保持在项目根目录，便于统一管理数据、实验结果和报告。
- `code/` 中的入口脚本已经适配当前结构，运行时会自动读写根目录下的 `data/` 和 `outputs/`。
