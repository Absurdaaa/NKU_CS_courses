"""输出文件写出工具。"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_model_summary(generator, discriminator, device: str, path: Path) -> None:
    path.write_text(
        "Device: "
        + device
        + "\n\n[Generator]\n"
        + str(generator)
        + "\n\n[Discriminator]\n"
        + str(discriminator)
        + "\n",
        encoding="utf-8",
    )


def save_epoch_metrics(history: list[dict[str, float | int]], path: Path) -> None:
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


def save_run_metadata(metadata: dict[str, object], path: Path) -> None:
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
