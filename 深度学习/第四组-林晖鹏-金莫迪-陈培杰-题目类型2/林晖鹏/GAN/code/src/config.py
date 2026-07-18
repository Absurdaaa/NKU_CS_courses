"""CLI 参数与实验配置定义。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import torch

from .constants import AVAILABLE_MODELS


@dataclass(slots=True)
class TrainConfig:
    """Lab4 训练配置。"""

    project_root: Path
    data_root: Path
    output_dir: Path
    model: str
    run_name: str | None
    epochs: int
    batch_size: int
    lr: float
    optimizer: str
    beta1: float
    latent_dim: int
    hidden_dim: int
    image_size: int
    image_channels: int
    generator_base_channels: int
    discriminator_base_channels: int
    seed: int
    num_workers: int
    val_ratio: float
    max_train_samples: int
    max_val_samples: int
    max_test_samples: int
    fixed_noise_count: int
    fid_eval_every: int
    fid_samples: int
    label_smoothing: float
    d_lr: float
    disc_dropout: float
    device: torch.device


def build_parser(project_root: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lab4 GAN/DCGAN training framework")
    parser.add_argument("--model", type=str, default="gan", choices=AVAILABLE_MODELS, help="Model name.")
    parser.add_argument("--run-name", type=str, default=None, help="Optional run name.")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs.")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size.")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate.")
    parser.add_argument(
        "--optimizer",
        type=str,
        default="adam",
        choices=("adam", "sgd", "adamw"),
        help="Optimizer name for both generator and discriminator.",
    )
    parser.add_argument("--beta1", type=float, default=0.5, help="Beta1 used by Adam/AdamW.")
    parser.add_argument("--latent-dim", type=int, default=100, help="Latent noise dimension.")
    parser.add_argument("--hidden-dim", type=int, default=128, help="MLP hidden size for vanilla GAN.")
    parser.add_argument("--image-size", type=int, default=None, help="Override training image size.")
    parser.add_argument("--image-channels", type=int, default=1, help="Number of image channels.")
    parser.add_argument(
        "--generator-base-channels",
        type=int,
        default=64,
        help="Base channel count used by DCGAN generator.",
    )
    parser.add_argument(
        "--discriminator-base-channels",
        type=int,
        default=64,
        help="Base channel count used by DCGAN discriminator.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--num-workers", type=int, default=0, help="DataLoader workers.")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation ratio split from train set.")
    parser.add_argument("--max-train-samples", type=int, default=0, help="Optional cap for train split, 0 means full set.")
    parser.add_argument("--max-val-samples", type=int, default=0, help="Optional cap for val split, 0 means full set.")
    parser.add_argument("--max-test-samples", type=int, default=0, help="Optional cap for test split, 0 means full set.")
    parser.add_argument("--fixed-noise-count", type=int, default=64, help="Number of fixed latent samples for visualization.")
    parser.add_argument("--fid-eval-every", type=int, default=5, help="Compute FID every N epochs (0 disables FID).")
    parser.add_argument("--fid-samples", type=int, default=5000, help="Number of real/fake samples used per FID computation.")
    parser.add_argument("--label-smoothing", type=float, default=0.0, help="单边标签平滑：真实标签 = 1 - 该值（0 表示关闭）。")
    parser.add_argument("--d-lr", type=float, default=0.0, help="判别器学习率（TTUR）；0 表示与 --lr 相同。")
    parser.add_argument("--disc-dropout", type=float, default=0.3, help="gan_deep 判别器的 Dropout 概率。")
    parser.add_argument(
        "--data-root",
        type=str,
        default=str(project_root / "data"),
        help="Dataset root directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(project_root / "outputs"),
        help="Output root directory.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Training device.",
    )
    return parser


def parse_config(project_root: Path, argv: list[str] | None = None) -> TrainConfig:
    args = build_parser(project_root).parse_args(argv)
    if not (0 < args.val_ratio < 1):
        raise ValueError("--val-ratio must be in (0, 1).")
    if args.latent_dim <= 0:
        raise ValueError("--latent-dim must be positive.")
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be positive.")
    if args.epochs <= 0:
        raise ValueError("--epochs must be positive.")
    image_size = 28 if args.image_size is None else args.image_size

    return TrainConfig(
        project_root=project_root,
        data_root=Path(args.data_root),
        output_dir=Path(args.output_dir),
        model=args.model,
        run_name=args.run_name,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        optimizer=args.optimizer,
        beta1=args.beta1,
        latent_dim=args.latent_dim,
        hidden_dim=args.hidden_dim,
        image_size=image_size,
        image_channels=args.image_channels,
        generator_base_channels=args.generator_base_channels,
        discriminator_base_channels=args.discriminator_base_channels,
        seed=args.seed,
        num_workers=args.num_workers,
        val_ratio=args.val_ratio,
        max_train_samples=args.max_train_samples,
        max_val_samples=args.max_val_samples,
        max_test_samples=args.max_test_samples,
        fixed_noise_count=args.fixed_noise_count,
        fid_eval_every=args.fid_eval_every,
        fid_samples=args.fid_samples,
        label_smoothing=args.label_smoothing,
        d_lr=args.d_lr,
        disc_dropout=args.disc_dropout,
        device=torch.device(args.device),
    )
