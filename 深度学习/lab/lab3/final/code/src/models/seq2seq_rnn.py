"""Baseline Seq2Seq model without attention."""

from __future__ import annotations

import random

import torch
import torch.nn as nn

from ..constants import EOS_TOKEN, SOS_TOKEN
from .encoder import EncoderRNN


class DecoderRNN(nn.Module):
    def __init__(self, hidden_size: int, output_size: int, num_layers: int, dropout: float, pad_idx: int) -> None:
        super().__init__()
        self.embedding = nn.Embedding(output_size, hidden_size, padding_idx=pad_idx)
        self.dropout = nn.Dropout(dropout)
        self.gru = nn.GRU(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.out = nn.Linear(hidden_size, output_size)

    def forward_step(self, input_tokens: torch.Tensor, hidden: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        embedded = self.dropout(self.embedding(input_tokens))
        output, hidden = self.gru(embedded, hidden)
        # 这一层就是把当前时刻的隐藏状态翻译成“下一个词更像是谁”的分数。
        logits = self.out(output)
        return logits, hidden


class Seq2SeqRNN(nn.Module):
    def __init__(
        self,
        src_vocab_size: int,
        tgt_vocab_size: int,
        hidden_size: int,
        num_layers: int,
        dropout: float,
        pad_idx: int,
        max_decode_length: int,
    ) -> None:
        super().__init__()
        self.encoder = EncoderRNN(src_vocab_size, hidden_size, num_layers, dropout, pad_idx)
        self.decoder = DecoderRNN(hidden_size, tgt_vocab_size, num_layers, dropout, pad_idx)
        self.max_decode_length = max_decode_length
        self.tgt_vocab_size = tgt_vocab_size

    def forward(
        self,
        source_tokens: torch.Tensor,
        source_lengths: torch.Tensor,
        target_tokens: torch.Tensor | None = None,
        teacher_forcing_ratio: float = 0.0,
    ) -> tuple[torch.Tensor, torch.Tensor, None]:
        encoder_outputs, encoder_hidden = self.encoder(source_tokens, source_lengths)
        # baseline 版本不看每个时间步的 encoder 输出，只拿最后的 hidden 往下解码。
        del encoder_outputs

        batch_size = source_tokens.size(0)
        hidden = encoder_hidden
        if target_tokens is not None:
            decode_steps = target_tokens.size(1) - 1
        else:
            decode_steps = self.max_decode_length

        decoder_input = torch.full(
            (batch_size, 1),
            fill_value=SOS_TOKEN,
            dtype=torch.long,
            device=source_tokens.device,
        )
        logits_per_step = []
        predicted_ids = []

        for step in range(decode_steps):
            step_logits, hidden = self.decoder.forward_step(decoder_input, hidden)
            logits_per_step.append(step_logits)
            step_prediction = step_logits.argmax(dim=-1)
            predicted_ids.append(step_prediction)

            # teacher forcing 可以理解成“训练时偶尔直接告诉模型上一步正确答案”。
            use_teacher_forcing = target_tokens is not None and random.random() < teacher_forcing_ratio
            if use_teacher_forcing:
                decoder_input = target_tokens[:, step + 1].unsqueeze(1)
            else:
                # 推理时就只能靠模型自己刚刚预测出来的词继续往后滚。
                decoder_input = step_prediction.detach()

        logits = torch.cat(logits_per_step, dim=1)
        predictions = torch.cat(predicted_ids, dim=1)
        return logits, predictions, None
