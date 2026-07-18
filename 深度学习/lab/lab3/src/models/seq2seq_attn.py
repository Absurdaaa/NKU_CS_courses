"""Seq2Seq model with Bahdanau attention."""

from __future__ import annotations

import random

import torch
import torch.nn as nn

from ..constants import SOS_TOKEN
from .encoder import EncoderRNN


class BahdanauAttention(nn.Module):
    def __init__(self, hidden_size: int) -> None:
        super().__init__()
        self.query_layer = nn.Linear(hidden_size, hidden_size, bias=False)
        self.key_layer = nn.Linear(hidden_size, hidden_size, bias=False)
        self.score_layer = nn.Linear(hidden_size, 1, bias=False)

    def forward(
        self,
        query: torch.Tensor,
        keys: torch.Tensor,
        mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        projected_query = self.query_layer(query).unsqueeze(1)
        projected_keys = self.key_layer(keys)
        scores = self.score_layer(torch.tanh(projected_query + projected_keys)).squeeze(-1)
        # 被 padding 补出来的位置直接屏蔽掉，别让注意力分到这些假 token 上。
        scores = scores.masked_fill(~mask, float("-inf"))
        weights = torch.softmax(scores, dim=-1)
        # 这一步相当于“把整句编码结果按注意力权重做加权平均”。
        context = torch.bmm(weights.unsqueeze(1), keys).squeeze(1)
        return context, weights


class AttnDecoderRNN(nn.Module):
    def __init__(self, hidden_size: int, output_size: int, num_layers: int, dropout: float, pad_idx: int) -> None:
        super().__init__()
        self.embedding = nn.Embedding(output_size, hidden_size, padding_idx=pad_idx)
        self.dropout = nn.Dropout(dropout)
        self.attention = BahdanauAttention(hidden_size)
        self.gru = nn.GRU(
            input_size=hidden_size * 2,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.out = nn.Linear(hidden_size, output_size)

    def forward_step(
        self,
        input_tokens: torch.Tensor,
        hidden: torch.Tensor,
        encoder_outputs: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        embedded = self.dropout(self.embedding(input_tokens)).squeeze(1)
        # 这里用最后一层 decoder hidden 当 query，去整句 encoder 输出里“找重点”。
        query = hidden[-1]
        context, attention_weights = self.attention(query, encoder_outputs, attention_mask)
        # 把当前输入词向量和注意力拿到的上下文拼起来，再送进 GRU。
        gru_input = torch.cat([embedded, context], dim=-1).unsqueeze(1)
        output, hidden = self.gru(gru_input, hidden)
        logits = self.out(output)
        return logits, hidden, attention_weights


class Seq2SeqAttention(nn.Module):
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
        self.decoder = AttnDecoderRNN(hidden_size, tgt_vocab_size, num_layers, dropout, pad_idx)
        self.max_decode_length = max_decode_length

    def forward(
        self,
        source_tokens: torch.Tensor,
        source_lengths: torch.Tensor,
        target_tokens: torch.Tensor | None = None,
        teacher_forcing_ratio: float = 0.0,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        encoder_outputs, encoder_hidden = self.encoder(source_tokens, source_lengths)
        batch_size, max_source_length, _ = encoder_outputs.shape

        hidden = encoder_hidden
        # attention mask 用来告诉模型：哪些位置是真词，哪些只是补零。
        attention_mask = (
            torch.arange(max_source_length, device=source_tokens.device).unsqueeze(0)
            < source_lengths.unsqueeze(1)
        )
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
        attention_per_step = []

        for step in range(decode_steps):
            step_logits, hidden, step_attention = self.decoder.forward_step(
                decoder_input,
                hidden,
                encoder_outputs,
                attention_mask,
            )
            logits_per_step.append(step_logits)
            attention_per_step.append(step_attention.unsqueeze(1))
            step_prediction = step_logits.argmax(dim=-1)
            predicted_ids.append(step_prediction)

            # 有监督训练时偶尔“扶一把”，不然 decoder 前期很容易越跑越偏。
            use_teacher_forcing = target_tokens is not None and random.random() < teacher_forcing_ratio
            if use_teacher_forcing:
                decoder_input = target_tokens[:, step + 1].unsqueeze(1)
            else:
                decoder_input = step_prediction.detach()

        logits = torch.cat(logits_per_step, dim=1)
        predictions = torch.cat(predicted_ids, dim=1)
        attentions = torch.cat(attention_per_step, dim=1)
        return logits, predictions, attentions
