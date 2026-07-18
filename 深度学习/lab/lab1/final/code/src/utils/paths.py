"""Output path helpers."""

from __future__ import annotations

from ..config import ExperimentConfig


def format_float_tag(value: float) -> str:
    text = f"{value:.8g}"
    return text.replace("-", "m").replace(".", "p")


def build_run_name(config: ExperimentConfig) -> str:
    if config.run_name:
        return config.run_name
    lr_tag = format_float_tag(config.lr)
    return f"{config.optimizer}_lr{lr_tag}_bs{config.batch_size}"
