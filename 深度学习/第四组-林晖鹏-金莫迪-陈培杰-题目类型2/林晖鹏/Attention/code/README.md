# Lab3 代码说明

本目录保留实验三最终提交所需的关键代码，主要包括：

- `train.py`
  - 单次训练入口
- `sweep_lr.py`
  - 学习率扫描入口
- `run*.sh`
  - 主实验、扩展实验与报告素材生成脚本
- `src/`
  - 核心实现
- `scripts/generate_report_assets.py`
  - 报告图表与表格生成
- `model_prints/`
  - 三种主模型的结构打印结果

建议优先查看：

1. `train.py`
2. `sweep_lr.py`
3. `src/models/seq2seq_rnn.py`
4. `src/models/seq2seq_attn.py`
5. `src/models/seq2seq_luong.py`
6. `src/engine.py`
