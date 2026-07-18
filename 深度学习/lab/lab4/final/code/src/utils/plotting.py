"""训练曲线与生成样例绘图。"""

from __future__ import annotations

from pathlib import Path

import math

import matplotlib.pyplot as plt
import torch
import torchvision.utils as vutils


def _is_nan(value: object) -> bool:
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def save_training_curves(history: list[dict[str, float | int]], path: Path) -> None:
    if not history:
        return

    epochs = [int(item["epoch"]) for item in history]
    train_g = [float(item["train_generator_loss"]) for item in history]
    val_g = [float(item["val_generator_loss"]) for item in history]
    train_d = [float(item["train_discriminator_loss"]) for item in history]
    val_d = [float(item["val_discriminator_loss"]) for item in history]
    train_real = [float(item["train_d_real_mean"]) for item in history]
    train_fake = [float(item["train_d_fake_mean"]) for item in history]
    val_real = [float(item["val_d_real_mean"]) for item in history]
    val_fake = [float(item["val_d_fake_mean"]) for item in history]

    # FID 仅在部分 epoch 计算（其余为 NaN），单独收集有效点。
    fid_points = [
        (int(item["epoch"]), float(item["fid"]))
        for item in history
        if "fid" in item and item["fid"] is not None and not _is_nan(item["fid"])
    ]
    n_axes = 4 if fid_points else 3
    fig, axes = plt.subplots(1, n_axes, figsize=(5.3 * n_axes, 4.5))

    axes[0].plot(epochs, train_g, label="Train G Loss")
    axes[0].plot(epochs, val_g, label="Val G Loss")
    axes[0].set_title("Generator Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].grid(alpha=0.3)
    axes[0].legend()

    axes[1].plot(epochs, train_d, label="Train D Loss")
    axes[1].plot(epochs, val_d, label="Val D Loss")
    axes[1].set_title("Discriminator Loss")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Loss")
    axes[1].grid(alpha=0.3)
    axes[1].legend()

    axes[2].plot(epochs, train_real, label="Train D(x)")
    axes[2].plot(epochs, train_fake, label="Train D(G(z))")
    axes[2].plot(epochs, val_real, label="Val D(x)")
    axes[2].plot(epochs, val_fake, label="Val D(G(z))")
    axes[2].set_title("Discriminator Scores")
    axes[2].set_xlabel("Epoch")
    axes[2].set_ylabel("Score")
    axes[2].grid(alpha=0.3)
    axes[2].legend()

    if fid_points:
        fid_epochs = [p[0] for p in fid_points]
        fid_values = [p[1] for p in fid_points]
        best_idx = min(range(len(fid_values)), key=lambda i: fid_values[i])
        axes[3].plot(fid_epochs, fid_values, marker="o", label="FID")
        axes[3].scatter(
            [fid_epochs[best_idx]], [fid_values[best_idx]],
            color="red", zorder=5, label=f"best={fid_values[best_idx]:.2f}",
        )
        axes[3].set_title("FID (lower is better)")
        axes[3].set_xlabel("Epoch")
        axes[3].set_ylabel("FID")
        axes[3].grid(alpha=0.3)
        axes[3].legend()

    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_image_grid(images: torch.Tensor, path: Path, nrow: int = 8) -> None:
    grid = vutils.make_grid(images.detach().cpu(), nrow=nrow, normalize=True, pad_value=0.3)
    figure = plt.figure(figsize=(8, 8))
    plt.axis("off")
    plt.imshow(grid.permute(1, 2, 0).numpy(), cmap="gray" if images.size(1) == 1 else None)
    figure.tight_layout()
    figure.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(figure)
