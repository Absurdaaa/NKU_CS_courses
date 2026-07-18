"""Experiment logging and metadata helpers."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
import time

import torch

from utils.io import ensure_dir


def timestamp():
    return time.strftime("%Y%m%d-%H%M%S")


def setup_run_dir(output_dir, model_name):
    base_dir = Path(output_dir)
    # 如果 output_dir 已经像 runs/resnet18 这样是模型目录，就直接在下面建时间戳 run。
    if base_dir.name == model_name:
        run_dir = base_dir / timestamp()
    else:
        run_dir = base_dir / model_name / timestamp()
    ensure_dir(run_dir)
    return run_dir


def save_json(data, path):
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)


def build_logger(log_path):
    logger = logging.getLogger(str(log_path))
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def init_metrics_csv(path):
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["epoch", "train_loss", "mae", "f_measure", "epoch_time_sec", "lr"],
        )
        writer.writeheader()


def append_metrics_csv(path, row):
    path = Path(path)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["epoch", "train_loss", "mae", "f_measure", "epoch_time_sec", "lr"],
        )
        writer.writerow(row)


def count_parameters(model):
    total = sum(param.numel() for param in model.parameters())
    trainable = sum(param.numel() for param in model.parameters() if param.requires_grad)
    return {"total": total, "trainable": trainable}


def estimate_model_profile(model, image_size, device):
    params = count_parameters(model)
    profile = {
        "params_total": params["total"],
        "params_trainable": params["trainable"],
        "flops": None,
        "flops_tool": None,
    }

    try:
        from thop import profile as thop_profile

        dummy = torch.randn(1, 3, image_size, image_size, device=device)
        was_training = model.training
        model.eval()
        flops, _ = thop_profile(model, inputs=(dummy,), verbose=False)
        if was_training:
            model.train()
        profile["flops"] = int(flops)
        profile["flops_tool"] = "thop"
    except Exception:
        profile["flops"] = None
        profile["flops_tool"] = None

    return profile


def format_bytes(num_bytes):
    if num_bytes is None:
        return None
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024.0
