# Final Submission Guide

本目录用于最终提交，主要包含三部分内容：

- `code/`
  - 实验主要代码
- `report.pdf`
  - 实验报告 PDF
- `README.md`
  - 本说明文件

## 代码入口

建议优先查看以下文件：

- `code/train.py`
  - 单次训练入口
- `code/sweep_lr.py`
  - 学习率扫描入口
- `code/src/models/`
  - 五个模型实现：
    - `simple_cnn.py`
    - `resnet.py`
    - `densenet.py`
    - `mobilenet.py`
    - `res2net.py`
- `code/src/engine.py`
  - 训练、验证、测试主循环
- `code/src/data.py`
  - CIFAR-10 数据加载与划分

## 结构说明

```text
final/
|-- README.md
|-- report.pdf
`-- code/
    |-- train.py
    |-- sweep_lr.py
    |-- model_prints/
    |-- src/
    |   |-- config.py
    |   |-- constants.py
    |   |-- data.py
    |   |-- engine.py
    |   |-- models/
    |   `-- utils/
    `-- scripts/
```

## model_prints

`code/model_prints/` 中保存了各模型的 `print(net)` 输出文本，便于对应实验报告中“网络结构打印结果”部分：

- `simple_cnn_print.txt`
- `resnet20_print.txt`
- `densenet_bc_100_print.txt`
- `mobilenet_v1_print.txt`
- `res2net29_8c64w_print.txt`

## 补充说明

- 报告中使用的数据、训练结果和图表生成过程来自原项目目录 `lab1/` 下的 `outputs/`、`实验模板/` 等内容。
- 本 `final/` 目录只保留提交时最需要查看的主要代码和最终 PDF，方便快速检查。
