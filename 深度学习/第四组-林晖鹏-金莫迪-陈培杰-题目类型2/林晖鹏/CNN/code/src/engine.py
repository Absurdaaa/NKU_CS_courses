"""Training and evaluation loop."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from .config import ExperimentConfig
from .constants import CLASSES
from .utils.io import save_csv_rows, save_lines, save_metrics, save_single_row_csv
from .utils.plotting import plot_training_curves, save_prediction_grid
from .utils.profiling import (
    count_parameters,
    estimate_flops,
    measure_inference_time,
    sync_device,
)
from .utils.wandb_logger import WandbLogger


def build_optimizer(model: nn.Module, config: ExperimentConfig) -> optim.Optimizer:
    if config.optimizer == "sgd":
        return optim.SGD(
            model.parameters(),
            lr=config.lr,
            momentum=config.momentum,
            weight_decay=config.weight_decay,
        )
    if config.optimizer == "adam":
        return optim.Adam(
            model.parameters(),
            lr=config.lr,
            weight_decay=config.weight_decay,
        )
    if config.optimizer == "adamw":
        return optim.AdamW(
            model.parameters(),
            lr=config.lr,
            weight_decay=config.weight_decay,
        )
    raise ValueError(f"Unsupported optimizer: {config.optimizer}")


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: torch.device,
) -> Tuple[float, float]:
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * images.size(0)
        preds = outputs.argmax(dim=1)
        total += labels.size(0)
        correct += (preds == labels).sum().item()

    return total_loss / len(loader.dataset), correct / total


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)
        preds = outputs.argmax(dim=1)
        total += labels.size(0)
        correct += (preds == labels).sum().item()

    return total_loss / len(loader.dataset), correct / total


@torch.no_grad()
def evaluate_with_timing(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Tuple[float, float, float]:
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    sync_device(device)
    start = time.perf_counter()
    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)
        preds = outputs.argmax(dim=1)
        total += labels.size(0)
        correct += (preds == labels).sum().item()
    sync_device(device)
    elapsed = time.perf_counter() - start

    return total_loss / len(loader.dataset), correct / total, elapsed


@torch.no_grad()
def evaluate_per_class(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> Dict[str, float]:
    model.eval()
    correct_per_class = {class_name: 0 for class_name in CLASSES}
    total_per_class = {class_name: 0 for class_name in CLASSES}

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        outputs = model(images)
        preds = outputs.argmax(dim=1)

        for label, pred in zip(labels, preds):
            class_name = CLASSES[label.item()]
            total_per_class[class_name] += 1
            if label == pred:
                correct_per_class[class_name] += 1

    return {
        class_name: correct_per_class[class_name] / total_per_class[class_name]
        for class_name in CLASSES
    }


def run_training(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    test_loader: DataLoader,
    config: ExperimentConfig,
    output_dir: Path,
) -> None:
    device = torch.device(config.device)
    criterion = nn.CrossEntropyLoss()
    optimizer = build_optimizer(model, config)
    total_params, trainable_params = count_parameters(model)
    flops = estimate_flops(model, device)
    wandb_logger = None
    if config.use_wandb:
        try:
            wandb_logger = WandbLogger(config, output_dir)
        except Exception as exc:
            print(f"W&B initialization failed, fallback to local logging only: {exc}")

    history: Dict[str, List[float]] = {
        "train_loss": [],
        "train_acc": [],
        "val_loss": [],
        "val_acc": [],
    }
    epoch_rows: List[Dict[str, object]] = []
    best_val_acc = 0.0
    best_val_epoch = 0
    time_to_best_val_sec = 0.0
    total_train_start = time.perf_counter()

    for epoch in range(1, config.epochs + 1):
        sync_device(device)
        epoch_start = time.perf_counter()
        train_loss, train_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, device
        )
        val_loss, val_acc = evaluate(model, val_loader, criterion, device)
        sync_device(device)
        epoch_time_sec = time.perf_counter() - epoch_start
        elapsed_train_time_sec = time.perf_counter() - total_train_start

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        epoch_rows.append(
            {
                "epoch": epoch,
                "train_loss": f"{train_loss:.6f}",
                "train_acc": f"{train_acc:.6f}",
                "val_loss": f"{val_loss:.6f}",
                "val_acc": f"{val_acc:.6f}",
                "epoch_time_sec": f"{epoch_time_sec:.6f}",
                "elapsed_train_time_sec": f"{elapsed_train_time_sec:.6f}",
            }
        )
        if wandb_logger is not None:
            wandb_logger.log_epoch(
                {
                    "epoch": epoch,
                    "train/loss": train_loss,
                    "train/acc": train_acc,
                    "val/loss": val_loss,
                    "val/acc": val_acc,
                    "time/epoch_sec": epoch_time_sec,
                    "time/elapsed_train_sec": elapsed_train_time_sec,
                }
            )

        print(
            f"Epoch [{epoch}/{config.epochs}] "
            f"train_loss={train_loss:.4f} "
            f"train_acc={train_acc * 100:.2f}% "
            f"val_loss={val_loss:.4f} "
            f"val_acc={val_acc * 100:.2f}% "
            f"epoch_time={epoch_time_sec:.2f}s"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_val_epoch = epoch
            time_to_best_val_sec = elapsed_train_time_sec
            torch.save(model.state_dict(), output_dir / "best_model.pth")

    save_csv_rows(
        output_dir / "epoch_metrics.csv",
        [
            "epoch",
            "train_loss",
            "train_acc",
            "val_loss",
            "val_acc",
            "epoch_time_sec",
            "elapsed_train_time_sec",
        ],
        epoch_rows,
    )

    if config.save_plots:
        plot_training_curves(history, output_dir / "training_curves.png")
        save_prediction_grid(model, val_loader, device, output_dir / "val_predictions.png")

    total_train_time_sec = time.perf_counter() - total_train_start
    test_loss, test_acc, test_inference_time_sec = evaluate_with_timing(
        model, test_loader, criterion, device
    )
    class_acc = evaluate_per_class(model, test_loader, device)
    inference_profile = measure_inference_time(
        model,
        device,
        next(iter(test_loader))[0][: min(32, test_loader.batch_size)],
    )
    print(f"\nTest loss: {test_loss:.4f}")
    print(f"Test accuracy: {test_acc * 100:.2f}%")
    print(f"Total train time: {total_train_time_sec:.2f}s")
    print(f"Test inference time: {test_inference_time_sec:.2f}s")
    print(f"Params: {total_params:,}")
    print(f"Trainable params: {trainable_params:,}")
    print(f"FLOPs (1x3x32x32): {flops:,}")
    print("\nPer-class accuracy:")
    class_acc_lines = []
    class_acc_rows = []
    for class_name, accuracy in class_acc.items():
        line = f"{class_name:5s}: {accuracy * 100:.2f}%"
        class_acc_lines.append(line)
        class_acc_rows.append(
            {
                "class_name": class_name,
                "accuracy": f"{accuracy:.6f}",
            }
        )
        print(line)

    summary_metrics = {
        "model": config.model,
        "optimizer": config.optimizer,
        "epochs": config.epochs,
        "batch_size": config.batch_size,
        "learning_rate": config.lr,
        "param_count": total_params,
        "trainable_param_count": trainable_params,
        "flops_per_image": flops,
        "final_train_loss": f"{history['train_loss'][-1]:.6f}",
        "final_train_acc": f"{history['train_acc'][-1]:.6f}",
        "best_val_acc": f"{best_val_acc:.6f}",
        "best_val_epoch": best_val_epoch,
        "time_to_best_val_sec": f"{time_to_best_val_sec:.6f}",
        "total_train_time_sec": f"{total_train_time_sec:.6f}",
        "avg_epoch_time_sec": f"{total_train_time_sec / config.epochs:.6f}",
        "test_loss": f"{test_loss:.6f}",
        "test_acc": f"{test_acc:.6f}",
        "test_inference_time_sec": f"{test_inference_time_sec:.6f}",
        "inference_time_per_batch_sec": f"{inference_profile['inference_time_per_batch_sec']:.6f}",
        "inference_time_per_image_ms": f"{inference_profile['inference_time_per_image_ms']:.6f}",
    }
    save_metrics(output_dir / "metrics.txt", summary_metrics)
    save_single_row_csv(output_dir / "summary_metrics.csv", summary_metrics)
    save_lines(output_dir / "class_accuracy.txt", class_acc_lines)
    save_csv_rows(
        output_dir / "class_accuracy.csv",
        ["class_name", "accuracy"],
        class_acc_rows,
    )
    if wandb_logger is not None:
        wandb_logger.log_summary(
            {
                "param_count": total_params,
                "trainable_param_count": trainable_params,
                "flops_per_image": flops,
                "best_val_acc": best_val_acc,
                "best_val_epoch": best_val_epoch,
                "time_to_best_val_sec": time_to_best_val_sec,
                "final_train_loss": history["train_loss"][-1],
                "final_train_acc": history["train_acc"][-1],
                "total_train_time_sec": total_train_time_sec,
                "avg_epoch_time_sec": total_train_time_sec / config.epochs,
                "test_loss": test_loss,
                "test_acc": test_acc,
                "test_inference_time_sec": test_inference_time_sec,
                "inference_time_per_batch_sec": inference_profile["inference_time_per_batch_sec"],
                "inference_time_per_image_ms": inference_profile["inference_time_per_image_ms"],
            }
        )
        wandb_logger.log_class_accuracy(class_acc)
        wandb_logger.finish()
