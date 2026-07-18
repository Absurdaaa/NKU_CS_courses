"""Plotting helpers for report assets."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch


def save_curves(history: list[dict[str, float | int]], path: Path) -> None:
    epochs = [int(item["epoch"]) for item in history]
    train_loss = [float(item["train_loss"]) for item in history]
    val_loss = [float(item["val_loss"]) for item in history]
    train_acc = [float(item["train_acc"]) for item in history]
    val_acc = [float(item["val_acc"]) for item in history]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].plot(epochs, train_loss, label="Train Loss")
    axes[0].plot(epochs, val_loss, label="Val Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].set_title("Loss Curves")
    axes[0].grid(alpha=0.3)
    axes[0].legend()

    axes[1].plot(epochs, train_acc, label="Train Acc")
    axes[1].plot(epochs, val_acc, label="Val Acc")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy")
    axes[1].set_title("Accuracy Curves")
    axes[1].grid(alpha=0.3)
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_gradient_norms(history: list[dict[str, float | int]], path: Path) -> None:
    if not history:
        return

    steps = [int(item["global_step"]) for item in history]
    before_clip = [float(item["grad_norm_before_clip"]) for item in history]
    after_clip = [float(item["grad_norm_after_clip"]) for item in history]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(steps, before_clip, label="Before Clip", alpha=0.85, linewidth=1.0)
    ax.plot(steps, after_clip, label="After Clip", alpha=0.85, linewidth=1.0)
    ax.set_xlabel("Training Step")
    ax.set_ylabel("Gradient Norm")
    ax.set_title("Gradient Norm During Training")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_generation_loss_curve(history: list[dict[str, float | int]], path: Path) -> None:
    if not history:
        return

    epochs = [int(item["epoch"]) for item in history]
    train_loss = [float(item["train_loss"]) for item in history]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(epochs, train_loss, label="Train Loss")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.set_title("Generation Training Loss")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_confusion_matrix(confusion: torch.Tensor | None, class_names: list[str], path: Path, title: str) -> None:
    if confusion is None:
        return

    matrix = confusion.float()
    row_sums = matrix.sum(dim=1, keepdim=True).clamp_min(1.0)
    normalized = (matrix / row_sums).cpu().numpy()

    fig, ax = plt.subplots(figsize=(8, 7))
    image = ax.imshow(normalized, cmap="Blues")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks(np.arange(len(class_names)))
    ax.set_yticks(np.arange(len(class_names)))
    ax.set_xticklabels(class_names, rotation=90)
    ax.set_yticklabels(class_names)
    ax.set_xlabel("Predicted Label")
    ax.set_ylabel("True Label")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
