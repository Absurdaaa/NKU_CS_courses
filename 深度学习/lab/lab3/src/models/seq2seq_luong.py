"""Seq2Seq model with Luong attention."""

from __future__ import annotations

import random

import torch
import torch.nn as nn

from ..constants import SOS_TOKEN
from .encoder import EncoderRNN


class LuongAttention(nn.Module):
    """Luong attention，支持 dot / general / concat 三种打分方式。"""

    def __init__(self, hidden_size: int, score_method: str = "general") -> None:
        super().__init__()
        if score_method not in {"dot", "general", "concat"}:
            raise ValueError(f"Unsupported Luong score method: {score_method}")
        self.score_method = score_method
        self.query_layer = nn.Linear(hidden_size, hidden_size, bias=False) if score_method == "general" else None
        self.concat_layer = (
            nn.Linear(hidden_size * 2, hidden_size, bias=False) if score_method == "concat" else None
        )
        self.score_layer = nn.Linear(hidden_size, 1, bias=False) if score_method == "concat" else None

    def forward(
        self,
        query: torch.Tensor,
        keys: torch.Tensor,
        mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if self.score_method == "dot":
            projected_query = query.unsqueeze(2)
            # 最朴素的 Luong dot：不做额外投影，直接点积。
            scores = torch.bmm(keys, projected_query).squeeze(2)
        elif self.score_method == "general":
            projected_query = self.query_layer(query).unsqueeze(2)
            # general 会先把 query 线性变换一下，再和 encoder outputs 做匹配。
            scores = torch.bmm(keys, projected_query).squeeze(2)
        else:
            expanded_query = query.unsqueeze(1).expand(-1, keys.size(1), -1)
            combined = torch.cat([expanded_query, keys], dim=-1)
            energy = torch.tanh(self.concat_layer(combined))
            scores = self.score_layer(energy).squeeze(-1)
        scores = scores.masked_fill(~mask, float("-inf"))
        weights = torch.softmax(scores, dim=-1)
        context = torch.bmm(weights.unsqueeze(1), keys).squeeze(1)
        return context, weights


class LuongDecoderRNN(nn.Module):
    def __init__(
        self,
        hidden_size: int,
        output_size: int,
        num_layers: int,
        dropout: float,
        pad_idx: int,
        score_method: str,
    ) -> None:
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
        self.attention = LuongAttention(hidden_size, score_method=score_method)
        self.concat_layer = nn.Linear(hidden_size * 2, hidden_size)
        self.out = nn.Linear(hidden_size, output_size)

    def forward_step(
        self,
        input_tokens: torch.Tensor,
        hidden: torch.Tensor,
        encoder_outputs: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        embedded = self.dropout(self.embedding(input_tokens))
        # Luong 这一路通常是先跑 decoder，再拿 decoder 当前输出去和 encoder 对齐。
        decoder_output, hidden = self.gru(embedded, hidden)
        query = decoder_output.squeeze(1)
        context, attention_weights = self.attention(query, encoder_outputs, attention_mask)
        # 把 decoder 当前状态和上下文拼一下，再压回 hidden_size。
        attn_hidden = torch.tanh(self.concat_layer(torch.cat([query, context], dim=-1)))
        logits = self.out(attn_hidden).unsqueeze(1)
        return logits, hidden, attention_weights


class Seq2SeqLuong(nn.Module):
    def __init__(
        self,
        src_vocab_size: int,
        tgt_vocab_size: int,
        hidden_size: int,
        num_layers: int,
        dropout: float,
        pad_idx: int,
        max_decode_length: int,
        score_method: str = "general",
    ) -> None:
        super().__init__()
        self.encoder = EncoderRNN(src_vocab_size, hidden_size, num_layers, dropout, pad_idx)
        self.decoder = LuongDecoderRNN(
            hidden_size,
            tgt_vocab_size,
            num_layers,
            dropout,
            pad_idx,
            score_method=score_method,
        )
        self.max_decode_length = max_decode_length
        self.score_method = score_method

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
        attention_mask = (
            torch.arange(max_source_length, device=source_tokens.device).unsqueeze(0)
            < source_lengths.unsqueeze(1)
        )
        decode_steps = target_tokens.size(1) - 1 if target_tokens is not None else self.max_decode_length

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

            use_teacher_forcing = target_tokens is not None and random.random() < teacher_forcing_ratio
            if use_teacher_forcing:
                decoder_input = target_tokens[:, step + 1].unsqueeze(1)
            else:
                decoder_input = step_prediction.detach()

        logits = torch.cat(logits_per_step, dim=1)
        predictions = torch.cat(predicted_ids, dim=1)
        attentions = torch.cat(attention_per_step, dim=1)
        return logits, predictions, attentions
