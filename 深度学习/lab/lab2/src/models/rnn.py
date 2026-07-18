"""Vanilla RNN classifier."""

from __future__ import annotations

import torch
import torch.nn as nn


class VanillaRNNClassifier(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, output_size: int) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        # 手写最基础的 RNN 单元：当前字符和上一时刻隐藏状态拼接后更新 hidden
        self.i2h = nn.Linear(input_size + hidden_size, hidden_size)
        self.h2o = nn.Linear(hidden_size, output_size)
        self.log_softmax = nn.LogSoftmax(dim=1)

    def forward(self, sequences: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        seq_len, batch_size, _ = sequences.size()
        hidden = sequences.new_zeros(batch_size, self.hidden_size)

        for time_index in range(seq_len):
            inputs = sequences[time_index]
            combined = torch.cat((inputs, hidden), dim=1)
            new_hidden = torch.tanh(self.i2h(combined))
            # 对已经结束的短序列，不再继续更新 hidden，保持其最后一个有效时刻的状态
            active = (time_index < lengths).unsqueeze(1)
            hidden = torch.where(active, new_hidden, hidden)

        # 取每个名字最终的隐藏状态做分类
        logits = self.h2o(hidden)
        return self.log_softmax(logits)
