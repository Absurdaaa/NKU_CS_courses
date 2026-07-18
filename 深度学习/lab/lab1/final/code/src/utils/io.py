"""File output helpers."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping

import torch.nn as nn


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_model_summary(model: nn.Module, device: str, output_path: Path) -> None:
    total_params = sum(param.numel() for param in model.parameters())
    trainable_params = sum(
        param.numel() for param in model.parameters() if param.requires_grad
    )
    lines = [
        f"Model summary for {model.__class__.__name__}",
        "=" * 60,
        str(model),
        "",
        f"Device: {device}",
        f"Total parameters: {total_params:,}",
        f"Trainable parameters: {trainable_params:,}",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_metrics(output_path: Path, metrics: Mapping[str, object]) -> None:
    lines = [f"{key}={value}" for key, value in metrics.items()]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_lines(output_path: Path, lines: list[str]) -> None:
    output_path.write_text("\n".join(lines), encoding="utf-8")


def save_csv_rows(output_path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_single_row_csv(output_path: Path, row: dict[str, object]) -> None:
    save_csv_rows(output_path, list(row.keys()), [row])
