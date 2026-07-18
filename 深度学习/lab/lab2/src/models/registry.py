"""Model registry helpers."""

from __future__ import annotations

from .lstm import LSTMClassifier
from .myGRU import MyGRUClassifier
from .myLSTM import MyLSTMClassifier
from .rnn import VanillaRNNClassifier

AVAILABLE_MODELS = ("rnn", "lstm", "myGRU", "myLSTM")


def build_model(
    model_name: str,
    input_size: int,
    hidden_size: int,
    output_size: int,
    num_layers: int,
    dropout: float,
):
    if model_name == "rnn":
        return VanillaRNNClassifier(input_size=input_size, hidden_size=hidden_size, output_size=output_size)
    if model_name == "lstm":
        return LSTMClassifier(
            input_size=input_size,
            hidden_size=hidden_size,
            output_size=output_size,
            num_layers=num_layers,
            dropout=dropout,
        )
    if model_name == "myGRU":
        return MyGRUClassifier(
            input_size=input_size,
            hidden_size=hidden_size,
            output_size=output_size,
        )
    if model_name == "myLSTM":
        return MyLSTMClassifier(
            input_size=input_size,
            hidden_size=hidden_size,
            output_size=output_size,
        )
    raise ValueError(f"Unknown model: {model_name}")
