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
    train_exact = [float(item["train_exact_match"]) for item in history]
    val_exact = [float(item["val_exact_match"]) for item in history]

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    axes[0].plot(epochs, train_loss, label="Train Loss")
    axes[0].plot(epochs, val_loss, label="Val Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].set_title("Loss Curves")
    axes[0].grid(alpha=0.3)
    axes[0].legend()

    axes[1].plot(epochs, train_acc, label="Train Token Acc")
    axes[1].plot(epochs, val_acc, label="Val Token Acc")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy")
    axes[1].set_title("Token Accuracy Curves")
    axes[1].grid(alpha=0.3)
    axes[1].legend()

    axes[2].plot(epochs, train_exact, label="Train Exact Match")
    axes[2].plot(epochs, val_exact, label="Val Exact Match")
    axes[2].set_xlabel("Epoch")
    axes[2].set_ylabel("Exact Match")
    axes[2].set_title("Sentence Exact Match Curves")
    axes[2].grid(alpha=0.3)
    axes[2].legend()

    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_attention_heatmap(attention: torch.Tensor, source_text: str, prediction_text: str, path: Path) -> None:
    source_tokens = source_text.split(" ")
    target_tokens = prediction_text.split(" ")
    if not target_tokens:
        target_tokens = ["<EMPTY>"]

    source_axis_labels = ["<SOS>"] + source_tokens + ["<EOS>"]
    matrix = attention[: len(target_tokens), : len(source_axis_labels)].cpu().numpy()
    if matrix.size == 0:
        matrix = np.zeros((1, 1), dtype=np.float32)
        source_axis_labels = ["<EMPTY>"]
        target_tokens = ["<EMPTY>"]

    fig, ax = plt.subplots(figsize=(max(6, len(source_axis_labels) * 0.6), max(4, len(target_tokens) * 0.6)))
    image = ax.imshow(matrix, cmap="bone", aspect="auto")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks(np.arange(matrix.shape[1]))
    ax.set_yticks(np.arange(matrix.shape[0]))
    ax.set_xticklabels(source_axis_labels[: matrix.shape[1]], rotation=90)
    ax.set_yticklabels(target_tokens[: matrix.shape[0]])
    ax.set_xlabel("Source Tokens")
    ax.set_ylabel("Generated Tokens")
    ax.set_title("Attention Heatmap")
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
