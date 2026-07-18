"""手写 LSTM 分类器。"""

from __future__ import annotations

import torch
import torch.nn as nn


class MyLSTMClassifier(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, output_size: int) -> None:
        super().__init__()
        self.hidden_size = hidden_size

        # LSTM 里有四个门：
        # 1. 遗忘门：决定旧记忆丢多少
        # 2. 输入门：决定新信息写多少
        # 3. 候选记忆：这一时刻“想写进去”的新内容
        # 4. 输出门：决定当前 hidden 往外吐多少
        self.x2f = nn.Linear(input_size, hidden_size)
        self.h2f = nn.Linear(hidden_size, hidden_size, bias=False)

        self.x2i = nn.Linear(input_size, hidden_size)
        self.h2i = nn.Linear(hidden_size, hidden_size, bias=False)

        self.x2g = nn.Linear(input_size, hidden_size)
        self.h2g = nn.Linear(hidden_size, hidden_size, bias=False)

        self.x2o = nn.Linear(input_size, hidden_size)
        self.h2o = nn.Linear(hidden_size, hidden_size, bias=False)

        self.output = nn.Linear(hidden_size, output_size)
        self.log_softmax = nn.LogSoftmax(dim=1)

    def lstm_step(
        self,
        inputs: torch.Tensor,
        hidden: torch.Tensor,
        cell: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        # 这里每个门都看“当前字符 + 上一时刻 hidden”
        forget_gate = torch.sigmoid(self.x2f(inputs) + self.h2f(hidden))
        input_gate = torch.sigmoid(self.x2i(inputs) + self.h2i(hidden))
        candidate_cell = torch.tanh(self.x2g(inputs) + self.h2g(hidden))
        output_gate = torch.sigmoid(self.x2o(inputs) + self.h2o(hidden))

        # 新的 cell state = 留下来的旧记忆 + 新写进去的内容
        next_cell = forget_gate * cell + input_gate * candidate_cell
        # hidden 可以理解成“对外可见的那部分记忆”
        next_hidden = output_gate * torch.tanh(next_cell)
        return next_hidden, next_cell

    def forward(self, sequences: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        seq_len, batch_size, _ = sequences.size()
        hidden = sequences.new_zeros(batch_size, self.hidden_size)
        cell = sequences.new_zeros(batch_size, self.hidden_size)

        for time_index in range(seq_len):
            inputs = sequences[time_index]
            new_hidden, new_cell = self.lstm_step(inputs, hidden, cell)

            # 短名字提前结束后，后面 padding 部分就别再更新状态了
            active = (time_index < lengths).unsqueeze(1)
            hidden = torch.where(active, new_hidden, hidden)
            cell = torch.where(active, new_cell, cell)

        # 最后拿整条名字对应的 hidden 做分类
        logits = self.output(hidden)
        return self.log_softmax(logits)
