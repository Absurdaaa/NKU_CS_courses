"""手写 GRU 分类器。"""

from __future__ import annotations

import torch
import torch.nn as nn


class MyGRUClassifier(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, output_size: int) -> None:
        super().__init__()
        self.hidden_size = hidden_size

        # GRU 包含更新门 z、重置门 r 和候选隐藏状态 h_tilde
        self.x2z = nn.Linear(input_size, hidden_size)
        self.h2z = nn.Linear(hidden_size, hidden_size, bias=False)

        self.x2r = nn.Linear(input_size, hidden_size)
        self.h2r = nn.Linear(hidden_size, hidden_size, bias=False)

        self.x2h = nn.Linear(input_size, hidden_size)
        self.h2h = nn.Linear(hidden_size, hidden_size, bias=False)

        self.output = nn.Linear(hidden_size, output_size)
        self.log_softmax = nn.LogSoftmax(dim=1)

    def gru_step(self, inputs: torch.Tensor, hidden: torch.Tensor) -> torch.Tensor:
        update_gate = torch.sigmoid(self.x2z(inputs) + self.h2z(hidden))
        reset_gate = torch.sigmoid(self.x2r(inputs) + self.h2r(hidden))

        candidate_hidden = torch.tanh(self.x2h(inputs) + self.h2h(reset_gate * hidden)) # bias藏在了x2h里面
        next_hidden = (1.0 - update_gate) * hidden + update_gate * candidate_hidden
        return next_hidden

    def forward(self, sequences: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        seq_len, batch_size, _ = sequences.size()
        hidden = sequences.new_zeros(batch_size, self.hidden_size)

        for time_index in range(seq_len):
            inputs = sequences[time_index]
            new_hidden = self.gru_step(inputs, hidden)
            # 对已经结束的短序列，保持最后一个有效时刻的隐藏状态不再更新
            active = (time_index < lengths).unsqueeze(1)
            hidden = torch.where(active, new_hidden, hidden)

        logits = self.output(hidden)
        return self.log_softmax(logits)
