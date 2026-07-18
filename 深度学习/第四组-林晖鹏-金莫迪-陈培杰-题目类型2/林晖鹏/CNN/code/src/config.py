"""CLI config for experiments."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import torch

from .models import AVAILABLE_MODELS


@dataclass
class ExperimentConfig:
    model: str
    run_name: str | None
    epochs: int
    batch_size: int
    optimizer: str
    lr: float
    momentum: float
    weight_decay: float
    val_ratio: float
    seed: int
    num_workers: int
    data_root: Path
    output_dir: Path
    device: str
    download: bool
    save_plots: bool
    use_wandb: bool
    wandb_project: str
    wandb_entity: str | None
    wandb_run_name: str | None


def build_parser(project_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CIFAR-10 experiment framework")
    parser.add_argument(
        "--model",
        default="simple_cnn",
        choices=AVAILABLE_MODELS,
        help="Model name.",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Optional run name for output directory and logging.",
    )
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs.")
    parser.add_argument("--batch-size", type=int, default=512, help="Batch size.")
    parser.add_argument(
        "--optimizer",
        type=str,
        default="sgd",
        choices=("sgd", "adam", "adamw"),
        help="Optimizer name.",
    )
    parser.add_argument("--lr", type=float, default=5e-2, help="Learning rate.")
    parser.add_argument("--momentum", type=float, default=0.9, help="SGD momentum.")
    parser.add_argument("--weight-decay", type=float, default=5e-4, help="Weight decay.")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation split ratio.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--num-workers", type=int, default=8, help="DataLoader workers.")
    parser.add_argument(
        "--data-root",
        type=str,
        default=str(project_root / "data"),
        help="Dataset directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(project_root / "outputs"),
        help="Output directory.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Training device.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download CIFAR-10 when local files are missing.",
    )
    parser.add_argument(
        "--save-plots",
        action="store_true",
        help="Save training curves and prediction plots.",
    )
    parser.add_argument(
        "--use-wandb",
        action="store_true",
        help="Enable Weights & Biases logging.",
    )
    parser.add_argument(
        "--wandb-project",
        type=str,
        default="cifar10-lab1",
        help="Weights & Biases project name.",
    )
    parser.add_argument(
        "--wandb-entity",
        type=str,
        default=None,
        help="Weights & Biases entity or team name.",
    )
    parser.add_argument(
        "--wandb-run-name",
        type=str,
        default=None,
        help="Weights & Biases run name.",
    )
    return parser


def parse_config(project_root: Path) -> ExperimentConfig:
    args = build_parser(project_root).parse_args()
    return ExperimentConfig(
        model=args.model,
        run_name=args.run_name,
        epochs=args.epochs,
        batch_size=args.batch_size,
        optimizer=args.optimizer,
        lr=args.lr,
        momentum=args.momentum,
        weight_decay=args.weight_decay,
        val_ratio=args.val_ratio,
        seed=args.seed,
        num_workers=args.num_workers,
        data_root=Path(args.data_root),
        output_dir=Path(args.output_dir),
        device=args.device,
        download=args.download,
        save_plots=args.save_plots,
        use_wandb=args.use_wandb,
        wandb_project=args.wandb_project,
        wandb_entity=args.wandb_entity,
        wandb_run_name=args.wandb_run_name,
    )
