"""Run naming helpers."""

from __future__ import annotations

from ..config import ExperimentConfig


def build_run_name(config: ExperimentConfig) -> str:
    if config.run_name:
        return config.run_name
    lr_string = str(config.lr).replace(".", "p")
    return f"{config.model}_h{config.hidden_size}_lr{lr_string}_bs{config.batch_size}"
