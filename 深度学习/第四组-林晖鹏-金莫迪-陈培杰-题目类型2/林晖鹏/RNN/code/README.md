# Lab2 核心代码说明

这个 `code/` 目录用于作为实验二的核心代码提交目录，只保留训练入口、模型实现、评估脚本和运行脚本，便于老师快速查看。

## 目录结构

```text
code/
├── train.py
├── train_generation.py
├── sweep_lr.py
├── evaluate_generation_fidelity.py
├── sample_best_generation.py
├── make_report_figures.py
├── make_gradient_compare.py
├── scripts/
└── src/
    ├── config.py
    ├── constants.py
    ├── data.py
    ├── engine.py
    ├── generation_config.py
    ├── generation_data.py
    ├── generation_engine.py
    ├── models/
    └── utils/
```

## 如果先看整体训练流程

- 名字识别任务入口：`train.py`
- 名字识别学习率扫描：`sweep_lr.py`
- 条件名字生成任务入口：`train_generation.py`
- 生成任务类别一致性评估：`evaluate_generation_fidelity.py`

如果老师想先了解整个实验框架，建议按下面顺序看：

1. `train.py` 或 `train_generation.py`
2. `src/data.py` / `src/generation_data.py`
3. `src/engine.py` / `src/generation_engine.py`
4. `src/models/`

## 如果重点看模型实现

模型代码统一放在：

- `src/models/registry.py`

这个文件负责注册分类模型，便于从训练入口快速跳转到具体模型实现。

### 名字识别模型

- 原始 RNN：`src/models/rnn.py`
- 内置 LSTM：`src/models/lstm.py`
- 手写 myLSTM：`src/models/myLSTM.py`
- 手写 myGRU：`src/models/myGRU.py`

### 名字生成模型

- `src/models/name_generator.py`

这个文件中包含：

- `rnn_gen`
- `lstm_gen`
- `gru_gen`

三种条件名字生成模型。

## 主要模块职责

- `src/data.py`
  - 名字识别数据读取、字符编码、`train/val/test` 划分
- `src/engine.py`
  - 名字识别训练、验证、测试主循环
- `src/generation_data.py`
  - 生成任务数据组织与 mini-batch 处理
- `src/generation_engine.py`
  - 生成任务训练、采样和统计指标
- `src/utils/io.py`
  - CSV、JSON、模型结构等结果文件写出
- `src/utils/plotting.py`
  - 曲线图、矩阵图等可视化输出
- `src/utils/profiling.py`
  - 参数量、FLOPs、显存与推理时间统计

## 运行脚本说明

- `scripts/run.sh`
  - 分类任务学习率扫描主脚本
- `scripts/run_grad_compare.sh`
  - 梯度稳定性对照实验脚本
- `scripts/run_generation.sh`
  - 生成任务基线运行脚本
- `scripts/sweep_lr_generation.sh`
  - 生成任务学习率扫描脚本
- `scripts/run_sample_best_generation.sh`
  - 从最佳生成模型重新采样更多名字
- `scripts/run_generation_fidelity.sh`
  - 用最佳分类器对生成名字做类别一致性评估

## 说明

- 本目录只保留核心代码，不包含 `outputs/`、`docs/`、`old/` 等实验结果或参考材料。
- 如果需要查看实验结果与图表，请结合报告正文以及 `lab2/outputs/` 目录中的内容。
