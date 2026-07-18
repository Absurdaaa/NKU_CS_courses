"""LSTM classifier."""

from __future__ import annotations

import torch
import torch.nn as nn


class LSTMClassifier(nn.Module):
    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        output_size: int,
        num_layers: int = 1,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        # 使用 PyTorch 内置 LSTM；当层数为 1 时，dropout 在模块内部不会生效
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.output = nn.Linear(hidden_size, output_size)
        self.log_softmax = nn.LogSoftmax(dim=1)

    def forward(self, sequences: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        # 先打包变长序列，避免 padding 部分参与无效计算
        packed = nn.utils.rnn.pack_padded_sequence(
            sequences,
            lengths.cpu(),
            enforce_sorted=True,
        )
        _, (hidden, _) = self.lstm(packed)
        # 取最后一层的最终隐藏状态作为整条名字序列的表示
        logits = self.output(hidden[-1])
        return self.log_softmax(logits)
