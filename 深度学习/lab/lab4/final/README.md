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
  - 学习率扫描入口（按 FID 选最优学习率）
- `code/src/models/`
  - GAN / DCGAN 模型实现：
    - `gan.py`：原始全连接 GAN（`GAN*`）与加深全连接 GAN（`DeepGAN*`）
    - `dcgan.py`：卷积版 DCGAN
    - `registry.py`：统一构建入口与权重初始化
- `code/src/engine.py`
  - 训练、验证、测试主循环（含按 FID 选 checkpoint 的逻辑）
- `code/src/utils/fid.py`
  - 基于 Inception-V3 的 FID 评估
- `code/src/data.py`
  - FashionMNIST 数据加载与划分

## 结构说明

```text
final/
|-- README.md
|-- report.pdf
`-- code/
    |-- train.py
    |-- sweep_lr.py
    |-- run.sh
    |-- model_prints/
    |-- src/
    |   |-- config.py
    |   |-- constants.py
    |   |-- data.py
    |   |-- engine.py
    |   |-- models/
    |   `-- utils/
    `-- scripts/
        |-- generate_report_assets.py   # 固定噪声样例、潜变量扰动、插值等图表
        |-- advanced_analysis.py         # 插值/多样性/最近邻/判别器特征探针
        |-- run_lab4_2gpu.sh             # 双卡总控（扫 lr -> final -> 报告素材）
        `-- run_lab4_final400.sh         # 400 轮最终训练
```

## model_prints

`code/model_prints/` 中保存了三个模型生成器/判别器的 `print(net)` 输出文本，对应报告中“网络结构打印结果”一节：

- `gan_print.txt`：原始全连接 GAN
- `gan_deep_print.txt`：加深全连接 GAN
- `dcgan_print.txt`：卷积版 DCGAN

## 补充说明

- 三个模型（原始全连接 GAN、加深全连接 GAN、卷积版 DCGAN）均在 FashionMNIST 上训练，统一使用 FID 作为模型选择与质量评价指标。
- 报告中使用的数据、训练结果与图表，生成过程来自原项目目录 `lab4/` 下的 `outputs/`、`实验模板/` 等内容。
- 本 `final/` 目录只保留提交时最需要查看的主要代码与最终 PDF，方便快速检查。
