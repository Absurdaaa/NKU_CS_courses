# Lab3 提交目录说明

这个 `final/` 目录用于作为实验三的最终提交目录，主要包含两部分：

- `report.pdf`
  - 实验报告最终 PDF
- `code/`
  - 实验三关键代码

## 目录结构

```text
final/
├── README.md
├── report.pdf
└── code/
    ├── train.py
    ├── sweep_lr.py
    ├── run.sh
    ├── run_01_sweep_core_models.sh
    ├── run_02_sweep_scheduled_sampling.sh
    ├── run_03_train_best_core_models.sh
    ├── run_04_train_best_scheduled_sampling.sh
    ├── run_05_generate_report_assets.sh
    ├── run_06_sweep_luong_variants.sh
    ├── run_07_sweep_luong_concat_ss.sh
    ├── scripts/
    ├── src/
    └── model_prints/
```

## 建议查看顺序

如果希望先看实验结果与分析，建议直接阅读：

- `report.pdf`

如果希望查看代码实现，建议按下面顺序查看：

1. `code/train.py`
   - 单次训练入口
2. `code/sweep_lr.py`
   - 学习率扫描入口
3. `code/src/models/seq2seq_rnn.py`
   - 纯 RNN Seq2Seq
4. `code/src/models/seq2seq_attn.py`
   - Bahdanau attention
5. `code/src/models/seq2seq_luong.py`
   - Luong attention 与 `dot/general/concat`
6. `code/src/engine.py`
   - 训练、验证、测试与指标统计

## 补充说明

- `code/model_prints/` 中保存了三种主模型的结构打印结果，便于对应报告中的“网络结构打印结果”部分。
- 报告中使用的数据、训练输出和图表生成过程来自原项目目录 `lab3/` 下的 `data/`、`outputs512/`、`实验模板/` 等内容。
- 本 `final/` 目录只保留提交时最需要查看的关键代码和最终 PDF，方便快速检查。
