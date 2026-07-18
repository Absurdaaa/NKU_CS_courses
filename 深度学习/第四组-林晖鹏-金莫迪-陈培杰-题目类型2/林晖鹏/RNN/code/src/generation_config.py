"""CLI config for conditional name generation experiments."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import torch


@dataclass
class GenerationConfig:
    model: str
    run_name: str | None
    epochs: int
    batch_size: int
    max_samples_per_epoch: int
    lr: float
    optimizer: str
    hidden_size: int
    dropout: float
    clip_grad_norm: float
    seed: int
    data_root: Path
    output_dir: Path
    device: torch.device
    sample_max_length: int
    sample_categories: str
    samples_per_category: int


def build_parser(project_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Conditional name generation framework")
    parser.add_argument(
        "--model",
        type=str,
        default="rnn_gen",
        choices=("rnn_gen", "lstm_gen", "gru_gen"),
        help="Generation model name.",
    )
    parser.add_argument("--run-name", type=str, default=None, help="Optional run name.")
    parser.add_argument("--epochs", type=int, default=20, help="Training epochs.")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size.")
    parser.add_argument(
        "--max-samples-per-epoch",
        type=int,
        default=0,
        help="Use only the first N shuffled samples per epoch. 0 means using the full dataset.",
    )
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate.")
    parser.add_argument(
        "--optimizer",
        type=str,
        default="adam",
        choices=("adam", "sgd", "adamw"),
        help="Optimizer name.",
    )
    parser.add_argument("--hidden-size", type=int, default=128, help="Hidden state size.")
    parser.add_argument("--dropout", type=float, default=0.1, help="Dropout used before output sampling.")
    parser.add_argument(
        "--clip-grad-norm",
        type=float,
        default=5.0,
        help="Gradient clipping max norm. Set to 0 or a negative value to disable clipping.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--data-root",
        type=str,
        default=str(project_root / "data" / "names"),
        help="Directory containing per-language .txt files.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(project_root / "outputs" / "generation"),
        help="Output directory.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Training device.",
    )
    parser.add_argument("--sample-max-length", type=int, default=20, help="Maximum length for generated names.")
    parser.add_argument(
        "--sample-categories",
        type=str,
        default="Russian,German,Spanish,Chinese",
        help='Categories to preview/evaluate, comma-separated, or "all".',
    )
    parser.add_argument(
        "--samples-per-category",
        type=int,
        default=10,
        help="How many names to generate for each selected category.",
    )
    return parser


def parse_generation_config(project_root: Path) -> GenerationConfig:
    args = build_parser(project_root).parse_args()
    return GenerationConfig(
        model=args.model,
        run_name=args.run_name,
        epochs=args.epochs,
        batch_size=args.batch_size,
        max_samples_per_epoch=args.max_samples_per_epoch,
        lr=args.lr,
        optimizer=args.optimizer,
        hidden_size=args.hidden_size,
        dropout=args.dropout,
        clip_grad_norm=args.clip_grad_norm,
        seed=args.seed,
        data_root=Path(args.data_root),
        output_dir=Path(args.output_dir),
        device=torch.device(args.device),
        sample_max_length=args.sample_max_length,
        sample_categories=args.sample_categories,
        samples_per_category=args.samples_per_category,
    )
