"""Conditional character-level generators for names."""

from __future__ import annotations

import torch
import torch.nn as nn


class ConditionalNameGeneratorRNN(nn.Module):
    def __init__(
        self,
        num_categories: int,
        input_size: int,
        hidden_size: int,
        output_size: int,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size

        combined_size = num_categories + input_size + hidden_size
        self.i2h = nn.Linear(combined_size, hidden_size)
        self.i2o = nn.Linear(combined_size, output_size)
        self.o2o = nn.Linear(hidden_size + output_size, output_size)
        self.dropout = nn.Dropout(dropout)
        self.log_softmax = nn.LogSoftmax(dim=1)

    def forward(self, category: torch.Tensor, input_step: torch.Tensor, state: torch.Tensor):
        combined = torch.cat((category, input_step, state), dim=1)
        hidden = torch.tanh(self.i2h(combined))
        output = self.i2o(combined)
        output = self.o2o(torch.cat((hidden, output), dim=1))
        output = self.dropout(output)
        output = self.log_softmax(output)
        return output, hidden

    def init_state(self, device: torch.device, batch_size: int = 1):
        return torch.zeros(batch_size, self.hidden_size, device=device)


class ConditionalNameGeneratorLSTM(nn.Module):
    def __init__(
        self,
        num_categories: int,
        input_size: int,
        hidden_size: int,
        output_size: int,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.num_categories = num_categories
        self.input_size = input_size
        self.lstm = nn.LSTM(num_categories + input_size, hidden_size, num_layers=1)
        self.dropout = nn.Dropout(dropout)
        self.output = nn.Linear(hidden_size, output_size)
        self.log_softmax = nn.LogSoftmax(dim=1)

    def forward(self, category: torch.Tensor, input_step: torch.Tensor, state):
        step_input = torch.cat((category, input_step), dim=1).unsqueeze(0)
        output, next_state = self.lstm(step_input, state)
        logits = self.output(self.dropout(output.squeeze(0)))
        logits = self.log_softmax(logits)
        return logits, next_state

    def init_state(self, device: torch.device, batch_size: int = 1):
        hidden = torch.zeros(1, batch_size, self.hidden_size, device=device)
        cell = torch.zeros(1, batch_size, self.hidden_size, device=device)
        return hidden, cell


class ConditionalNameGeneratorGRU(nn.Module):
    def __init__(
        self,
        num_categories: int,
        input_size: int,
        hidden_size: int,
        output_size: int,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.gru = nn.GRU(num_categories + input_size, hidden_size, num_layers=1)
        self.dropout = nn.Dropout(dropout)
        self.output = nn.Linear(hidden_size, output_size)
        self.log_softmax = nn.LogSoftmax(dim=1)

    def forward(self, category: torch.Tensor, input_step: torch.Tensor, state: torch.Tensor):
        step_input = torch.cat((category, input_step), dim=1).unsqueeze(0)
        output, next_state = self.gru(step_input, state)
        logits = self.output(self.dropout(output.squeeze(0)))
        logits = self.log_softmax(logits)
        return logits, next_state

    def init_state(self, device: torch.device, batch_size: int = 1):
        return torch.zeros(1, batch_size, self.hidden_size, device=device)


def build_generation_model(
    model_name: str,
    num_categories: int,
    input_size: int,
    hidden_size: int,
    output_size: int,
    dropout: float = 0.0,
):
    if model_name == "rnn_gen":
        return ConditionalNameGeneratorRNN(num_categories, input_size, hidden_size, output_size, dropout)
    if model_name == "lstm_gen":
        return ConditionalNameGeneratorLSTM(num_categories, input_size, hidden_size, output_size, dropout)
    if model_name == "gru_gen":
        return ConditionalNameGeneratorGRU(num_categories, input_size, hidden_size, output_size, dropout)
    raise ValueError(f"Unknown generation model: {model_name}")
