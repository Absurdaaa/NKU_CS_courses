#!/usr/bin/env python3
"""Run a learning-rate sweep and summarize the best run."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

from src.models import AVAILABLE_MODELS

PROJECT_ROOT = Path(__file__).resolve().parent
TRAIN_SCRIPT = PROJECT_ROOT / "train.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Learning-rate sweep helper for lab2")
    parser.add_argument("--model", required=True, choices=AVAILABLE_MODELS, help="Model name.")
    parser.add_argument("--lrs", nargs="+", type=float, required=True, help="Learning rates to sweep.")
    parser.add_argument("--epochs", type=int, default=30, help="Training epochs.")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size.")
    parser.add_argument(
        "--optimizer",
        type=str,
        default="adam",
        choices=("adam", "sgd", "adamw"),
        help="Optimizer name.",
    )
    parser.add_argument("--hidden-size", type=int, default=128, help="Hidden state size.")
    parser.add_argument("--num-layers", type=int, default=1, help="Number of recurrent layers.")
    parser.add_argument("--dropout", type=float, default=0.0, help="Dropout for stacked LSTM.")
    parser.add_argument(
        "--clip-grad-norm",
        type=float,
        default=0.0,
        help="Gradient clipping max norm. Set to 0 or a negative value to disable clipping.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--num-workers", type=int, default=0, help="DataLoader workers.")
    parser.add_argument("--train-ratio", type=float, default=0.7, help="Training split ratio.")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Validation split ratio.")
    parser.add_argument(
        "--data-root",
        type=str,
        default=str(PROJECT_ROOT / "data" / "names"),
        help="Directory containing per-language name files.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "outputs"),
        help="Output root directory.",
    )
    parser.add_argument("--device", type=str, default=None, help="Training device override.")
    parser.add_argument("--sweep-name", type=str, default="sweep", help="Optional sweep name prefix.")
    return parser.parse_args()


def format_float_tag(value: float) -> str:
    return f"{value:.8g}".replace("-", "m").replace(".", "p")


def build_run_name(args: argparse.Namespace, lr: float) -> str:
    return (
        f"{args.sweep_name}_{args.model}_opt{args.optimizer}_"
        f"h{args.hidden_size}_lr{format_float_tag(lr)}_bs{args.batch_size}"
    )


def build_training_command(args: argparse.Namespace, lr: float) -> tuple[list[str], Path]:
    run_name = build_run_name(args, lr)
    cmd = [
        sys.executable,
        str(TRAIN_SCRIPT),
        "--model",
        args.model,
        "--run-name",
        run_name,
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--lr",
        str(lr),
        "--optimizer",
        args.optimizer,
        "--hidden-size",
        str(args.hidden_size),
        "--num-layers",
        str(args.num_layers),
        "--dropout",
        str(args.dropout),
        "--clip-grad-norm",
        str(args.clip_grad_norm),
        "--seed",
        str(args.seed),
        "--num-workers",
        str(args.num_workers),
        "--train-ratio",
        str(args.train_ratio),
        "--val-ratio",
        str(args.val_ratio),
        "--data-root",
        args.data_root,
        "--output-dir",
        args.output_dir,
    ]
    if args.device:
        cmd.extend(["--device", args.device])
    summary_csv = Path(args.output_dir) / args.model / run_name / "summary_metrics.csv"
    return cmd, summary_csv


def should_skip_run(summary_csv: Path) -> bool:
    return summary_csv.exists()


def load_summary_metrics(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {row["metric"]: row["value"] for row in reader}


def load_run_metadata(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_summary_row(args: argparse.Namespace, summary_csv: Path) -> dict[str, str]:
    summary = load_summary_metrics(summary_csv)
    metadata = load_run_metadata(summary_csv.parent / "run_metadata.json")
    return {
        "run_name": summary_csv.parent.name,
        "model": str(metadata["model"]),
        "optimizer": str(metadata["optimizer"]),
        "learning_rate": str(metadata["lr"]),
        "hidden_size": str(metadata["hidden_size"]),
        "num_layers": str(metadata["num_layers"]),
        "best_val_acc": summary["best_val_acc"],
        "best_val_loss": summary["best_val_loss"],
        "best_epoch": summary["best_epoch"],
        "test_acc": summary["test_acc"],
        "test_loss": summary["test_loss"],
        "total_train_time_sec": summary["total_train_time_sec"],
        "avg_epoch_time_sec": summary["avg_epoch_time_sec"],
        "test_inference_time_sec": summary["test_inference_time_sec"],
        "inference_time_per_sample_ms": summary["inference_time_per_sample_ms"],
        "param_count": summary["param_count"],
        "trainable_param_count": summary["trainable_param_count"],
        "peak_memory_mb": summary["peak_memory_mb"],
        "avg_test_sequence_length": summary["avg_test_sequence_length"],
        "flops_per_sample": summary["flops_per_sample"],
    }


def run_training_sequential(args: argparse.Namespace) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for lr in args.lrs:
        cmd, summary_csv = build_training_command(args, lr)
        if should_skip_run(summary_csv):
            print(f"Skipping completed lr={lr}")
            rows.append(collect_summary_row(args, summary_csv))
            continue
        subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
        rows.append(collect_summary_row(args, summary_csv))
    return rows


def summarize_runs(args: argparse.Namespace, rows: list[dict[str, str]]) -> None:
    model_dir = Path(args.output_dir) / args.model
    model_dir.mkdir(parents=True, exist_ok=True)
    summary_path = model_dir / f"{args.model}_{args.optimizer}_lr_sweep_summary.csv"
    fieldnames = [
        "run_name",
        "model",
        "optimizer",
        "learning_rate",
        "hidden_size",
        "num_layers",
        "best_val_acc",
        "best_val_loss",
        "best_epoch",
        "test_acc",
        "test_loss",
        "total_train_time_sec",
        "avg_epoch_time_sec",
        "test_inference_time_sec",
        "inference_time_per_sample_ms",
        "param_count",
        "trainable_param_count",
        "peak_memory_mb",
        "avg_test_sequence_length",
        "flops_per_sample",
    ]
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    best_row = max(rows, key=lambda row: float(row["best_val_acc"]))
    best_path = model_dir / f"{args.model}_{args.optimizer}_best_lr.txt"
    best_path.write_text(
        "\n".join(
            [
                f"model={best_row['model']}",
                f"optimizer={best_row['optimizer']}",
                f"best_learning_rate={best_row['learning_rate']}",
                f"hidden_size={best_row['hidden_size']}",
                f"num_layers={best_row['num_layers']}",
                f"best_val_acc={best_row['best_val_acc']}",
                f"best_val_loss={best_row['best_val_loss']}",
                f"best_epoch={best_row['best_epoch']}",
                f"test_acc={best_row['test_acc']}",
                f"run_name={best_row['run_name']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\nSweep summary saved to: {summary_path}")
    print(f"Best LR summary saved to: {best_path}")
    print(
        f"Best run: lr={best_row['learning_rate']} "
        f"best_val_acc={float(best_row['best_val_acc']):.4f} "
        f"test_acc={float(best_row['test_acc']):.4f}"
    )


def main() -> None:
    args = parse_args()
    rows = run_training_sequential(args)
    summarize_runs(args, rows)


if __name__ == "__main__":
    main()
