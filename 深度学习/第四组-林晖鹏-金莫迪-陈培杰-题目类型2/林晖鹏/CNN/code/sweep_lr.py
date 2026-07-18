#!/usr/bin/env python3
"""Run a learning-rate sweep and summarize the best run."""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


CODE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_ROOT.parent
TRAIN_SCRIPT = CODE_ROOT / "train.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Learning-rate sweep helper")
    parser.add_argument(
        "--model",
        required=True,
        help="Model name, for example simple_cnn / resnet18 / vgg11_bn.",
    )
    parser.add_argument(
        "--optimizer",
        default="sgd",
        choices=("sgd", "adam", "adamw"),
        help="Optimizer name.",
    )
    parser.add_argument(
        "--lrs",
        nargs="+",
        type=float,
        required=True,
        help="Learning rates to sweep.",
    )
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs.")
    parser.add_argument("--batch-size", type=int, default=512, help="Batch size.")
    parser.add_argument("--num-workers", type=int, default=8, help="DataLoader workers.")
    parser.add_argument("--weight-decay", type=float, default=5e-4, help="Weight decay.")
    parser.add_argument("--momentum", type=float, default=0.9, help="SGD momentum.")
    parser.add_argument("--device", type=str, default=None, help="Training device override.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "outputs"),
        help="Output root directory.",
    )
    parser.add_argument("--download", action="store_true", help="Download dataset if needed.")
    parser.add_argument("--save-plots", action="store_true", help="Save plots for each run.")
    parser.add_argument("--use-wandb", action="store_true", help="Enable Weights & Biases logging.")
    parser.add_argument("--wandb-project", type=str, default="cifar10-lab1", help="W&B project name.")
    parser.add_argument("--wandb-entity", type=str, default=None, help="W&B entity.")
    parser.add_argument("--sweep-name", type=str, default=None, help="Optional name for this sweep.")
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=1,
        help="Maximum number of concurrent training runs.",
    )
    parser.add_argument(
        "--devices",
        nargs="+",
        default=None,
        help="Optional device list, for example cuda:0 cuda:1.",
    )
    return parser.parse_args()


def format_float_tag(value: float) -> str:
    text = f"{value:.8g}"
    return text.replace("-", "m").replace(".", "p")


def build_training_command(
    args: argparse.Namespace,
    lr: float,
    device: str | None = None,
) -> tuple[list[str], Path]:
    run_name = f"{args.sweep_name or 'sweep'}_{args.optimizer}_lr{format_float_tag(lr)}_bs{args.batch_size}"
    cmd = [
        sys.executable,
        str(TRAIN_SCRIPT),
        "--model",
        args.model,
        "--run-name",
        run_name,
        "--optimizer",
        args.optimizer,
        "--lr",
        str(lr),
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--num-workers",
        str(args.num_workers),
        "--weight-decay",
        str(args.weight_decay),
        "--momentum",
        str(args.momentum),
        "--seed",
        str(args.seed),
        "--output-dir",
        args.output_dir,
    ]
    selected_device = device or args.device
    if selected_device:
        cmd.extend(["--device", selected_device])
    if args.download:
        cmd.append("--download")
    if args.save_plots:
        cmd.append("--save-plots")
    if args.use_wandb:
        cmd.extend(
            [
                "--use-wandb",
                "--wandb-project",
                args.wandb_project,
            ]
        )
        if args.wandb_entity:
            cmd.extend(["--wandb-entity", args.wandb_entity])
    summary_csv = Path(args.output_dir) / args.model / run_name / "summary_metrics.csv"
    return cmd, summary_csv


def load_single_row_csv(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return next(reader)


def collect_summary_row(summary_csv: Path) -> dict[str, str]:
    summary = load_single_row_csv(summary_csv)
    return {
        "run_name": summary_csv.parent.name,
        "optimizer": summary["optimizer"],
        "learning_rate": summary["learning_rate"],
        "best_val_acc": summary["best_val_acc"],
        "best_val_epoch": summary["best_val_epoch"],
        "time_to_best_val_sec": summary["time_to_best_val_sec"],
        "total_train_time_sec": summary["total_train_time_sec"],
        "test_acc": summary["test_acc"],
        "test_loss": summary["test_loss"],
        "param_count": summary["param_count"],
        "flops_per_image": summary["flops_per_image"],
    }


def should_skip_run(summary_csv: Path) -> bool:
    return summary_csv.exists()


def run_training_sequential(args: argparse.Namespace) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for lr in args.lrs:
        cmd, summary_csv = build_training_command(args, lr)
        if should_skip_run(summary_csv):
            print(f"Skipping completed lr={lr}")
            rows.append(collect_summary_row(summary_csv))
            continue
        subprocess.run(cmd, check=True, cwd=CODE_ROOT)
        rows.append(collect_summary_row(summary_csv))
    return rows


def run_training_parallel(args: argparse.Namespace) -> list[dict[str, str]]:
    jobs: list[dict[str, object]] = []
    rows: list[dict[str, str]] = []
    devices = args.devices or []
    device_index = 0

    pending_lrs = list(args.lrs)
    while pending_lrs or jobs:
        while pending_lrs and len(jobs) < args.max_parallel:
            lr = pending_lrs.pop(0)
            assigned_device = None
            if devices:
                assigned_device = devices[device_index % len(devices)]
                device_index += 1
            cmd, summary_csv = build_training_command(args, lr, assigned_device)
            if should_skip_run(summary_csv):
                print(f"Skipping completed lr={lr}")
                rows.append(collect_summary_row(summary_csv))
                continue
            env = os.environ.copy()
            print(
                f"Starting lr={lr} "
                f"{f'on {assigned_device}' if assigned_device else ''}".strip()
            )
            process = subprocess.Popen(cmd, cwd=CODE_ROOT, env=env)
            jobs.append(
                {
                    "lr": lr,
                    "process": process,
                    "summary_csv": summary_csv,
                    "device": assigned_device,
                }
            )

        time.sleep(2.0)
        still_running: list[dict[str, object]] = []
        for job in jobs:
            process = job["process"]
            return_code = process.poll()
            if return_code is None:
                still_running.append(job)
                continue
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, process.args)
            lr = job["lr"]
            summary_csv = job["summary_csv"]
            print(f"Finished lr={lr}")
            rows.append(collect_summary_row(summary_csv))
        jobs = still_running

    rows.sort(key=lambda row: float(row["learning_rate"]), reverse=True)
    return rows


def summarize_runs(model: str, rows: Iterable[dict[str, str]], output_dir: Path, sweep_name: str) -> None:
    rows = list(rows)
    summary_path = output_dir / model / f"{sweep_name}_lr_sweep_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as file:
        fieldnames = [
            "run_name",
            "optimizer",
            "learning_rate",
            "best_val_acc",
            "best_val_epoch",
            "time_to_best_val_sec",
            "total_train_time_sec",
            "test_acc",
            "test_loss",
            "param_count",
            "flops_per_image",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    best_row = max(rows, key=lambda row: float(row["best_val_acc"]))
    best_path = output_dir / model / f"{sweep_name}_best_lr.txt"
    best_path.write_text(
        "\n".join(
            [
                f"model={model}",
                f"optimizer={best_row['optimizer']}",
                f"best_learning_rate={best_row['learning_rate']}",
                f"best_val_acc={best_row['best_val_acc']}",
                f"best_val_epoch={best_row['best_val_epoch']}",
                f"test_acc={best_row['test_acc']}",
                f"run_name={best_row['run_name']}",
            ]
        ),
        encoding="utf-8",
    )

    print(f"\nSweep summary saved to: {summary_path}")
    print(f"Best lr: {best_row['learning_rate']} | best_val_acc: {best_row['best_val_acc']} | run: {best_row['run_name']}")


def main() -> None:
    args = parse_args()
    sweep_name = args.sweep_name or f"{args.model}_{args.optimizer}"
    if args.max_parallel <= 1:
        rows = run_training_sequential(args)
    else:
        rows = run_training_parallel(args)

    summarize_runs(args.model, rows, Path(args.output_dir), sweep_name)


if __name__ == "__main__":
    main()
