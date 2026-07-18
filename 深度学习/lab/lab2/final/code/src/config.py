"""CLI config for RNN name classification experiments."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import torch

from .constants import NUM_CHARACTERS
from .models import AVAILABLE_MODELS


@dataclass
class ExperimentConfig:
    model: str
    run_name: str | None
    epochs: int
    batch_size: int
    lr: float
    clip_grad_norm: float
    optimizer: str
    hidden_size: int
    num_layers: int
    dropout: float
    seed: int
    num_workers: int
    train_ratio: float
    val_ratio: float
    data_root: Path
    output_dir: Path
    device: torch.device
    input_size: int


def build_parser(project_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RNN/LSTM name classification framework")
    parser.add_argument("--model", type=str, default="rnn", choices=AVAILABLE_MODELS, help="Model name.")
    parser.add_argument("--run-name", type=str, default=None, help="Optional run name.")
    parser.add_argument("--epochs", type=int, default=30, help="Training epochs.")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size.")
    parser.add_argument("--lr", type=float, default=1e-2, help="Learning rate.")
    parser.add_argument(
        "--clip-grad-norm",
        type=float,
        default=0.0,
        help="Gradient clipping max norm. Set to 0 or a negative value to disable clipping.",
    )
    parser.add_argument(
        "--optimizer",
        type=str,
        default="adam",
        choices=("adam", "sgd", "adamw"),
        help="Optimizer name.",
    )
    parser.add_argument("--hidden-size", type=int, default=128, help="Hidden state size.")
    parser.add_argument("--num-layers", type=int, default=1, help="Number of recurrent layers for LSTM.")
    parser.add_argument("--dropout", type=float, default=0.0, help="Dropout used in LSTM when num_layers > 1.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--num-workers", type=int, default=0, help="DataLoader workers.")
    parser.add_argument("--train-ratio", type=float, default=0.7, help="Training split ratio.")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Validation split ratio.")
    parser.add_argument(
        "--data-root",
        type=str,
        default=str(project_root / "data" / "names"),
        help="Directory containing per-language .txt files.",
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
    return parser


def parse_config(project_root: Path) -> ExperimentConfig:
    args = build_parser(project_root).parse_args()
    if not (0 < args.train_ratio < 1):
        raise ValueError("--train-ratio must be in (0, 1).")
    if not (0 < args.val_ratio < 1):
        raise ValueError("--val-ratio must be in (0, 1).")
    if args.train_ratio + args.val_ratio >= 1:
        raise ValueError("train_ratio + val_ratio must be smaller than 1.")

    return ExperimentConfig(
        model=args.model,
        run_name=args.run_name,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        clip_grad_norm=args.clip_grad_norm,
        optimizer=args.optimizer,
        hidden_size=args.hidden_size,
        num_layers=args.num_layers,
        dropout=args.dropout,
        seed=args.seed,
        num_workers=args.num_workers,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        data_root=Path(args.data_root),
        output_dir=Path(args.output_dir),
        device=torch.device(args.device),
        input_size=NUM_CHARACTERS,
    )
