"""Plotting and visualization utilities."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, List

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ..constants import CLASSES


def denormalize(image: torch.Tensor) -> torch.Tensor:
    return image * 0.5 + 0.5


def save_image_grid(
    loader: DataLoader,
    output_path: Path,
    title: str,
    max_images: int = 16,
) -> None:
    images, labels = next(iter(loader))
    images = images[:max_images].cpu()
    labels = labels[:max_images].cpu()
    rows = int(np.ceil(len(images) / 4))

    fig, axes = plt.subplots(rows, 4, figsize=(10, 2.5 * rows))
    axes = np.array(axes).reshape(-1)

    for ax in axes:
        ax.axis("off")

    for idx, (image, label) in enumerate(zip(images, labels)):
        axes[idx].imshow(np.transpose(denormalize(image).numpy(), (1, 2, 0)))
        axes[idx].set_title(CLASSES[label], fontsize=10)
        axes[idx].axis("off")

    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_training_curves(history: Dict[str, List[float]], output_path: Path) -> None:
    epochs = list(range(1, len(history["train_loss"]) + 1))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    axes[0].plot(epochs, history["train_loss"], marker="o", label="Train Loss")
    axes[0].plot(epochs, history["val_loss"], marker="o", label="Val Loss")
    axes[0].set_title("Loss Curves")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].grid(True, linestyle="--", alpha=0.4)
    axes[0].legend()

    axes[1].plot(epochs, history["train_acc"], marker="o", label="Train Acc")
    axes[1].plot(epochs, history["val_acc"], marker="o", label="Val Acc")
    axes[1].set_title("Accuracy Curves")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy")
    axes[1].set_ylim(0.0, 1.0)
    axes[1].grid(True, linestyle="--", alpha=0.4)
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_prediction_grid(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    output_path: Path,
    title: str = "Validation Predictions",
    max_images: int = 16,
) -> None:
    model.eval()
    images, labels = next(iter(loader))
    images = images[:max_images]
    labels = labels[:max_images]

    with torch.no_grad():
        outputs = model(images.to(device))
        preds = outputs.argmax(dim=1).cpu()

    rows = int(np.ceil(len(images) / 4))
    fig, axes = plt.subplots(rows, 4, figsize=(10, 2.5 * rows))
    axes = np.array(axes).reshape(-1)

    for ax in axes:
        ax.axis("off")

    for idx, (image, label, pred) in enumerate(zip(images, labels, preds)):
        axes[idx].imshow(np.transpose(denormalize(image).numpy(), (1, 2, 0)))
        color = "green" if label == pred else "red"
        axes[idx].set_title(
            f"T:{CLASSES[label]}\nP:{CLASSES[pred]}",
            fontsize=9,
            color=color,
        )
        axes[idx].axis("off")

    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
