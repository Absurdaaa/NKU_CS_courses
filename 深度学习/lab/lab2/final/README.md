# Lab2 提交目录说明

这个 `final/` 目录用于作为实验二的最终提交目录，主要包含两部分：

- `main.pdf`
  - 实验报告最终 PDF
- `code/`
  - 实验二核心代码

## 目录结构

```text
final/
├── main.pdf
├── README.md
└── code/
    ├── README.md
    ├── train.py
    ├── train_generation.py
    ├── sweep_lr.py
    ├── evaluate_generation_fidelity.py
    ├── sample_best_generation.py
    ├── scripts/
    └── src/
```

## 建议查看顺序

如果老师希望先看实验结果与分析，建议直接阅读：

- `main.pdf`

如果老师希望查看代码实现，建议按下面顺序查看：

1. `code/train.py`
   - 名字识别任务训练入口
2. `code/train_generation.py`
   - 条件名字生成任务训练入口
3. `code/src/models/registry.py`
   - 分类模型注册入口
4. 具体模型实现
   - `code/src/models/rnn.py`
   - `code/src/models/lstm.py`
   - `code/src/models/myLSTM.py`
   - `code/src/models/myGRU.py`
   - `code/src/models/name_generator.py`

## 代码内容说明

`code/` 目录中包含本实验的核心实现：

- 名字识别任务
  - 原始 RNN
  - 内置 LSTM
  - 手写 myLSTM
  - 手写 myGRU
- 条件名字生成任务
  - `rnn_gen`
  - `lstm_gen`
  - `gru_gen`
- 学习率扫描
- 梯度稳定性分析
- 生成任务类别一致性评估

运行脚本统一放在：

- `code/scripts/`

例如：

- `code/scripts/run.sh`
  - 分类任务批量运行脚本
- `code/scripts/sweep_lr_generation.sh`
  - 生成任务学习率扫描脚本
- `code/scripts/run_generation_fidelity.sh`
  - 生成任务类别一致性评估脚本

## 说明

- 该目录只保留最终提交所需内容，不包含完整实验输出目录。
- 更详细的代码框架说明请查看：
  - `code/README.md`
