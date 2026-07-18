# 生成任务可比较的实验

生成任务里最适合比较 `rnn_gen / lstm_gen / gru_gen` 的实验有：

## 1. 训练损失收敛速度

看：
- `epoch_metrics.csv`
- `training_loss_curve.png`

可以比较：
- 谁下降更快
- 谁更稳定
- 谁更容易震荡

## 2. 生成样例质量

看：
- `generated_samples.txt`

同样的语言类别、同样的起始字母下，比较：
- 是否更像真实名字
- 是否更容易重复字符
- 是否更容易过早结束
- 是否更能体现语言风格

## 3. 生成统计指标

看：
- `generated_metrics.csv`

里面有：
- `avg_generated_length`
- `unique_ratio`
- `train_overlap_ratio`

可以比较：
- 谁更容易生成过短/过长名字
- 谁生成的样本更多样
- 谁更容易直接“背”训练集名字

## 4. 参数量与训练时间

看：
- `model_structure.txt`
- `summary_metrics.csv`

可以比较：
- 谁更重
- 谁训练更慢
- 在生成质量差不多时，谁更划算

## 5. 类别一致性（Category Fidelity）

这是最适合接到你当前名字分类任务上的一个额外实验。

思路是：
- 先用名字分类任务里训练好的判别模型（推荐最优 `lstm`）当“评委”
- 再把生成模型产出的名字重新送进这个判别器
- 看它是否还能被判成目标语言类别

对应脚本：

```bash
bash run_generation_fidelity.sh
```

它会输出：
- `fidelity_summary.csv`
- `overall_fidelity.png`
- `category_fidelity.png`
- `*_fidelity_confusion_matrix.png`

可以比较：
- 哪个生成模型整体上更符合目标语言风格
- 哪些语言类别最容易“生成跑偏”
- 生成模型的条件类别和判别器预测类别之间最常见的错配是什么

这个实验的意义在于：
- `generated_samples.txt` 偏主观
- `category fidelity` 提供了更可量化的“像不像该语言名字”的证据
- 很适合写进报告，解释为什么某些生成模型更擅长保持语言风格一致性

## 推荐写法

如果要在报告里解释为什么 `LSTM generation` 或 `GRU generation` 比 `RNN generation` 更好，建议重点从这两点展开：

1. 门控结构更容易保留前面已经生成的上下文信息，因此对长名字或复杂拼写模式更稳定。
2. 从生成样例看，RNN 更容易出现重复、结构塌缩或过早结束，而 LSTM/GRU 更容易保持字符序列的整体一致性。
3. 从类别一致性评估看，若 `LSTM generation` 或 `GRU generation` 的 fidelity 更高，说明它们不仅“看起来像名字”，而且更能保持目标语言风格。
