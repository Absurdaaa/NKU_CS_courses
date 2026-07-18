# Lab2 Name Classification Framework

这个目录现在已经整理成可复用的多文件实验框架，目标是完成作业要求里的：

- 原始 RNN 名字分类实验
- LSTM 名字分类实验
- `print(net)` 网络结构导出
- 验证集 `loss/accuracy` 曲线
- 验证集与测试集 confusion matrix
- 条件名字生成实验（对应 `char_rnn_gen.py`）

## 目录结构

```text
lab2/
├── train.py
├── train_generation.py
├── src/
│   ├── config.py
│   ├── constants.py
│   ├── data.py
│   ├── engine.py
│   ├── generation_config.py
│   ├── generation_data.py
│   ├── generation_engine.py
│   ├── models/
│   │   ├── rnn.py
│   │   ├── lstm.py
│   │   ├── name_generator.py
│   │   └── registry.py
│   └── utils/
│       ├── io.py
│       ├── paths.py
│       ├── plotting.py
│       └── runtime.py
├── docs/
├── rnn_pytorch_tutorial.ipynb
└── char_rnn_classification_tutorial.ipynb
```

## 数据放置方式

将名字分类数据按类别放到：

```text
lab2/data/names/
├── Arabic.txt
├── Chinese.txt
├── English.txt
└── ...
```

每个 `.txt` 文件对应一个类别，每行一个名字。

## 运行示例

原始 RNN：

```bash
python3 train.py --model rnn --epochs 30 --batch-size 64 --hidden-size 128
```

LSTM：

```bash
python3 train.py --model lstm --epochs 30 --batch-size 64 --hidden-size 128 --lr 1e-3
```

条件名字生成：

```bash
python3 train_generation.py --model rnn_gen --epochs 20 --batch-size 128 --hidden-size 128 --lr 1e-3 --samples-per-category 20 --run-name gen_demo
```

生成任务学习率扫描：

```bash
bash sweep_lr_generation.sh
```

生成任务类别一致性评估（用已训练分类器当“评委”）：

```bash
bash run_generation_fidelity.sh
```

如果你已经跑完 `sweep_lr_generation.sh`，不想重新训练，只想用最佳 checkpoint 重新多生成一些名字：

```bash
bash run_sample_best_generation.sh
```

快速 smoke test：

```bash
python3 train_generation.py --model rnn_gen --epochs 1 --batch-size 128 --hidden-size 64 --max-samples-per-epoch 256 --run-name gen_smoke
```

学习率扫描：

```bash
python3 sweep_lr.py --model rnn --optimizer adam --epochs 30 --batch-size 256 --hidden-size 128 --lrs 0.01 0.005 0.001 0.0005
python3 sweep_lr.py --model lstm --optimizer adam --epochs 30 --batch-size 256 --hidden-size 128 --lrs 0.01 0.005 0.001 0.0005
python3 sweep_lr.py --model myGRU --optimizer adam --epochs 30 --batch-size 256 --hidden-size 128 --lrs 0.01 0.005 0.001 0.0005
python3 sweep_lr.py --model myLSTM --optimizer adam --epochs 30 --batch-size 256 --hidden-size 128 --lrs 0.01 0.005 0.001 0.0005
```

## 输出内容

每次运行会在 `outputs/<model>/<run_name>/` 下生成：

- `model_structure.txt`
- `epoch_metrics.csv`
- `summary_metrics.csv`
- `run_metadata.json`
- `training_curves.png`
- `gradient_norms.png`
- `val_confusion_matrix.png`
- `test_confusion_matrix.png`
- `gradient_metrics.csv`
- `val_confusion_matrix.csv`
- `test_confusion_matrix.csv`
- `class_accuracy.csv`
- `length_group_accuracy.csv`
- `best_model.pth`

生成任务会在 `outputs/generation/<run_name>/` 下生成：

- `model_structure.txt`
- `epoch_metrics.csv`
- `summary_metrics.csv`
- `run_metadata.json`
- `training_loss_curve.png`
- `generated_samples.txt`
- `generated_metrics.csv`
- `best_model.pth`

现在生成任务已经支持 mini-batch 训练，不再是逐样本串行更新。对于 `rnn_gen / lstm_gen / gru_gen`，建议优先使用：

```bash
--batch-size 128
```

这样 GPU/CPU 利用率会明显高于原来的单样本训练方式。

另外，生成样本数量现在可控：

```bash
--samples-per-category 20
```

默认会对 `Russian,German,Spanish,Chinese` 四个类别各生成 20 个名字，共 80 个样本；如果需要更完整的类别一致性评估，可以加：

```bash
--sample-categories all
```

生成类别一致性评估会在 `outputs/generation/fidelity_reports/<report_name>/` 下生成：

- `fidelity_per_name.csv`
- `fidelity_summary.csv`
- `overall_fidelity.png`
- `category_fidelity.png`
- `*_fidelity_confusion_matrix.csv`
- `*_fidelity_confusion_matrix.png`
- `judge_metadata.json`

从最佳生成模型重新采样会在 `outputs/generation/resampled/<best_run_name>_resampled/` 下生成：

- `generated_samples.txt`
- `generated_metrics.csv`
- `source_run.txt`
- `resample_metadata.json`

学习率扫描还会在 `outputs/<model>/` 下额外生成：

- `<model>_<optimizer>_lr_sweep_summary.csv`
- `<model>_<optimizer>_best_lr.txt`

其中 `summary_metrics.csv` 会记录：

- `best_val_acc / best_val_loss / best_epoch`
- `test_acc / test_loss`
- `total_train_time_sec / avg_epoch_time_sec`
- `test_inference_time_sec / inference_time_per_batch_sec / inference_time_per_sample_ms`
- `param_count / trainable_param_count`
- `peak_memory_mb`
- `avg_test_sequence_length`
- `flops_per_sample`

如果你想观察“不开梯度裁剪时梯度是否明显变大”，可以直接关闭裁剪：

```bash
python3 train.py --model rnn --lr 0.001 --clip-grad-norm 0 --run-name rnn_no_clip
```

之后对比：
- `gradient_metrics.csv`
- `gradient_norms.png`
- `epoch_metrics.csv`

即可判断不开裁剪时梯度是否明显飙升，以及训练是否更容易发散。

## 说明

- `rnn` 是作业要求里的原始循环神经网络 baseline。
- `lstm` 是对应的改进模型，便于后续写“为什么 LSTM 性能优于 RNN”的分析。
- `myGRU` 和 `myLSTM` 是手动实现的门控循环网络，适合做加分项或结构理解。
- `train_generation.py` 对应的是名字生成任务：给定语言类别和起始字母，生成符合该语言风格的名字。
- 当前已支持三种生成模型：`rnn_gen`、`lstm_gen`、`gru_gen`。
- `evaluate_generation_fidelity.py` 会复用你已经训练好的名字分类器，把它当成“评委”来检查生成名字是否符合目标语言风格。
- `run_generation_fidelity.sh` 默认使用当前最优的 `lstm` 分类器作为评估器，比较 `rnn_gen / lstm_gen / gru_gen` 三种生成模型的类别一致性。
- 当前框架默认做 `train/val/test` 三划分，适合直接写实验报告。
- 分类任务默认关闭手动梯度裁剪（`clip_grad_norm=0`）；如果需要做梯度裁剪对照实验，再显式传 `--clip-grad-norm 5.0`。
