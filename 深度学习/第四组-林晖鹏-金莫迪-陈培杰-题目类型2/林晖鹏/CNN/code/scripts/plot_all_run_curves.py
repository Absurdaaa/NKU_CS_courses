#!/usr/bin/env python3
"""Generate training_curves.png for every run directory under outputs/."""

from __future__ import annotations

import csv
from pathlib import Path
import sys

CODE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CODE_ROOT.parent
sys.path.insert(0, str(CODE_ROOT))
from src.utils.runtime import setup_matplotlib

setup_matplotlib(PROJECT_ROOT)

from src.utils.plotting import plot_training_curves


def read_history(csv_path: Path) -> dict[str, list[float]]:
    history = {
        "train_loss": [],
        "val_loss": [],
        "train_acc": [],
        "val_acc": [],
    }
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            history["train_loss"].append(float(row["train_loss"]))
            history["val_loss"].append(float(row["val_loss"]))
            history["train_acc"].append(float(row["train_acc"]))
            history["val_acc"].append(float(row["val_acc"]))
    return history


def main() -> None:
    outputs_dir = PROJECT_ROOT / "outputs"
    csv_paths = sorted(outputs_dir.glob("*/*/epoch_metrics.csv"))
    if not csv_paths:
        print("No epoch_metrics.csv files found.")
        return

    for csv_path in csv_paths:
        run_dir = csv_path.parent
        history = read_history(csv_path)
        output_path = run_dir / "training_curves.png"
        plot_training_curves(history, output_path)
        print(f"saved {output_path}")


if __name__ == "__main__":
    main()
