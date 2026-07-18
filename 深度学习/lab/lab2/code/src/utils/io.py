"""Small IO helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_model_summary(model, device: str, path: Path) -> None:
    path.write_text(f"Device: {device}\n\n{model}\n", encoding="utf-8")


def save_epoch_metrics(history: list[dict[str, float | int]], path: Path) -> None:
    if not history:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0].keys()))
        writer.writeheader()
        writer.writerows(history)


def save_gradient_metrics(history: list[dict[str, float | int]], path: Path) -> None:
    if not history:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0].keys()))
        writer.writeheader()
        writer.writerows(history)


def save_summary_metrics(summary: dict[str, float | int], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for key, value in summary.items():
            writer.writerow([key, value])


def save_class_accuracy(class_accuracy: list[dict[str, float | int | str]], path: Path) -> None:
    if not class_accuracy:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(class_accuracy[0].keys()))
        writer.writeheader()
        writer.writerows(class_accuracy)


def save_length_group_accuracy(rows: list[dict[str, float | int | str]], path: Path) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def save_confusion_csv(confusion, class_names: list[str], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true/pred"] + class_names)
        for class_name, row in zip(class_names, confusion.tolist()):
            writer.writerow([class_name] + row)


def save_run_metadata(metadata: dict[str, object], path: Path) -> None:
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
