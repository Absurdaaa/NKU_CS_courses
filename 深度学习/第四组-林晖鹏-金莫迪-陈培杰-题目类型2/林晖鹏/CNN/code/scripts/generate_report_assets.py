#!/usr/bin/env python3
"""Generate LaTeX-ready report assets from experiment outputs."""

from __future__ import annotations

import csv
from pathlib import Path
import sys

CODE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CODE_ROOT.parent
sys.path.insert(0, str(CODE_ROOT))

from src.utils.runtime import setup_matplotlib
from src.constants import CLASSES

setup_matplotlib(PROJECT_ROOT)

import matplotlib.pyplot as plt
import numpy as np

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TEMPLATE_DIR = PROJECT_ROOT / "实验模板"
FIG_DIR = TEMPLATE_DIR / "fig" / "generated"
TABLE_DIR = TEMPLATE_DIR / "tables"

MODELS = [
    "simple_cnn",
    "resnet20",
    "densenet_bc_100",
    "mobilenet_v1",
    "res2net29_8c64w",
]

MODEL_DISPLAY_NAMES = {
    "simple_cnn": "CNN",
    "resnet20": "ResNet20",
    "densenet_bc_100": "DenseNet-BC-100",
    "mobilenet_v1": "MobileNetV1",
    "res2net29_8c64w": "Res2Net",
}


def ensure_dirs() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)


def read_kv_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def read_single_row_csv(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return next(reader)


def read_epoch_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)


def read_class_accuracy_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)


def resolve_best_run_dir(model: str) -> tuple[Path, dict[str, str], dict[str, str]]:
    model_dir = OUTPUTS_DIR / model
    best_info = read_kv_file(model_dir / f"{model}_sgd_best_lr.txt")
    run_dir = model_dir / best_info["run_name"]
    summary = read_single_row_csv(run_dir / "summary_metrics.csv")
    return run_dir, best_info, summary


def plot_curves(model: str, run_dir: Path) -> Path:
    rows = read_epoch_rows(run_dir / "epoch_metrics.csv")
    epochs = [int(row["epoch"]) for row in rows]
    train_loss = [float(row["train_loss"]) for row in rows]
    val_loss = [float(row["val_loss"]) for row in rows]
    train_acc = [float(row["train_acc"]) for row in rows]
    val_acc = [float(row["val_acc"]) for row in rows]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].plot(epochs, train_loss, label="Train Loss", marker="o", markersize=2)
    axes[0].plot(epochs, val_loss, label="Val Loss", marker="o", markersize=2)
    axes[0].set_title(f"{MODEL_DISPLAY_NAMES[model]} Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Loss")
    axes[0].grid(True, linestyle="--", alpha=0.4)
    axes[0].legend()

    axes[1].plot(epochs, train_acc, label="Train Acc", marker="o", markersize=2)
    axes[1].plot(epochs, val_acc, label="Val Acc", marker="o", markersize=2)
    axes[1].set_title(f"{MODEL_DISPLAY_NAMES[model]} Accuracy")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Accuracy")
    axes[1].set_ylim(0.0, 1.0)
    axes[1].grid(True, linestyle="--", alpha=0.4)
    axes[1].legend()

    fig.tight_layout()
    out_path = FIG_DIR / f"{model}_curves.png"
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_combined_curves(best_runs: dict[str, Path]) -> tuple[Path, Path]:
    loss_fig, loss_axes = plt.subplots(1, 2, figsize=(12, 4.5))
    acc_fig, acc_axes = plt.subplots(1, 2, figsize=(12, 4.5))

    for model in MODELS:
        rows = read_epoch_rows(best_runs[model] / "epoch_metrics.csv")
        epochs = [int(row["epoch"]) for row in rows]
        train_loss = [float(row["train_loss"]) for row in rows]
        val_loss = [float(row["val_loss"]) for row in rows]
        train_acc = [float(row["train_acc"]) for row in rows]
        val_acc = [float(row["val_acc"]) for row in rows]
        label = MODEL_DISPLAY_NAMES[model]

        loss_axes[0].plot(epochs, train_loss, label=label, linewidth=1.6)
        loss_axes[1].plot(epochs, val_loss, label=label, linewidth=1.6)
        acc_axes[0].plot(epochs, train_acc, label=label, linewidth=1.6)
        acc_axes[1].plot(epochs, val_acc, label=label, linewidth=1.6)

    for ax, title, ylabel in [
        (loss_axes[0], "Train Loss", "Loss"),
        (loss_axes[1], "Validation Loss", "Loss"),
        (acc_axes[0], "Train Accuracy", "Accuracy"),
        (acc_axes[1], "Validation Accuracy", "Accuracy"),
    ]:
        ax.set_title(title)
        ax.set_xlabel("Epoch")
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle="--", alpha=0.4)

    acc_axes[0].set_ylim(0.0, 1.0)
    acc_axes[1].set_ylim(0.0, 1.0)

    loss_axes[1].legend(loc="best", fontsize=9)
    acc_axes[1].legend(loc="best", fontsize=9)

    loss_fig.tight_layout()
    acc_fig.tight_layout()

    loss_path = FIG_DIR / "all_models_loss_curves.png"
    acc_path = FIG_DIR / "all_models_accuracy_curves.png"
    loss_fig.savefig(loss_path, dpi=220, bbox_inches="tight")
    acc_fig.savefig(acc_path, dpi=220, bbox_inches="tight")
    plt.close(loss_fig)
    plt.close(acc_fig)
    return loss_path, acc_path


def plot_metric_comparison(best_runs: dict[str, Path]) -> dict[str, Path]:
    metric_defs = {
        "train_loss": ("all_models_train_loss.png", "Train Loss", "Loss", None, "#1f77b4"),
        "val_loss": ("all_models_val_loss.png", "Validation Loss", "Loss", None, "#ff7f0e"),
        "train_acc": ("all_models_train_acc.png", "Train Accuracy", "Accuracy", (0.0, 1.0), "#2ca02c"),
        "val_acc": ("all_models_val_acc.png", "Validation Accuracy", "Accuracy", (0.0, 1.0), "#d62728"),
    }
    output_paths: dict[str, Path] = {}

    for metric, (filename, title, ylabel, ylim, _color) in metric_defs.items():
        fig, ax = plt.subplots(1, 1, figsize=(8.5, 4.8))
        for model in MODELS:
            rows = read_epoch_rows(best_runs[model] / "epoch_metrics.csv")
            epochs = [int(row["epoch"]) for row in rows]
            values = [float(row[metric]) for row in rows]
            ax.plot(epochs, values, label=MODEL_DISPLAY_NAMES[model], linewidth=1.8)

        ax.set_title(title)
        ax.set_xlabel("Epoch")
        ax.set_ylabel(ylabel)
        if ylim is not None:
            ax.set_ylim(*ylim)
        ax.grid(True, linestyle="--", alpha=0.35)
        ax.legend(loc="best", fontsize=9)
        fig.tight_layout()
        out_path = FIG_DIR / filename
        fig.savefig(out_path, dpi=220, bbox_inches="tight")
        plt.close(fig)
        output_paths[metric] = out_path

    return output_paths


def plot_validation_grid(best_runs: dict[str, Path]) -> Path:
    fig, axes = plt.subplots(2, len(MODELS), figsize=(18, 6), sharex=False)

    for col, model in enumerate(MODELS):
        rows = read_epoch_rows(best_runs[model] / "epoch_metrics.csv")
        epochs = [int(row["epoch"]) for row in rows]
        val_loss = [float(row["val_loss"]) for row in rows]
        val_acc = [float(row["val_acc"]) for row in rows]

        loss_ax = axes[0, col]
        acc_ax = axes[1, col]

        loss_ax.plot(epochs, val_loss, linewidth=1.8, color="#1f77b4")
        loss_ax.set_title(MODEL_DISPLAY_NAMES[model], fontsize=10)
        loss_ax.set_xlabel("Epoch")
        loss_ax.set_ylabel("Val Loss")
        loss_ax.grid(True, linestyle="--", alpha=0.35)

        acc_ax.plot(epochs, val_acc, linewidth=1.8, color="#d62728")
        acc_ax.set_xlabel("Epoch")
        acc_ax.set_ylabel("Val Acc")
        acc_ax.set_ylim(0.0, 1.0)
        acc_ax.grid(True, linestyle="--", alpha=0.35)

    fig.tight_layout()
    out_path = FIG_DIR / "all_models_val_grid.png"
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_class_accuracy_and_bacc(best_runs: dict[str, Path]) -> Path:
    class_acc_by_model: dict[str, list[float]] = {}
    for model in MODELS:
        rows = read_class_accuracy_rows(best_runs[model] / "class_accuracy.csv")
        class_acc = [0.0] * len(CLASSES)
        for row in rows:
            class_name = row["class_name"]
            if class_name in CLASSES:
                class_acc[CLASSES.index(class_name)] = float(row["accuracy"])
        class_acc_by_model[model] = class_acc

    fig, ax = plt.subplots(1, 1, figsize=(12, 5.5))

    x = np.arange(len(CLASSES))
    width = 0.15
    for idx, model in enumerate(MODELS):
        offset = (idx - (len(MODELS) - 1) / 2) * width
        ax.bar(
            x + offset,
            class_acc_by_model[model],
            width=width,
            label=MODEL_DISPLAY_NAMES[model],
        )

    ax.set_title("Per-Class Accuracy Comparison")
    ax.set_ylabel("Accuracy")
    ax.set_xticks(x)
    ax.set_xticklabels(CLASSES, rotation=20)
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, axis="y", linestyle="--", alpha=0.35)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=3,
        fontsize=9,
        frameon=False,
    )

    fig.tight_layout()
    out_path = FIG_DIR / "class_accuracy.png"
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out_path


def generate_summary_table(rows: list[dict[str, str]]) -> Path:
    params_min = min(int(row["param_count"]) for row in rows)
    flops_min = min(int(row["flops_per_image"]) for row in rows)
    train_time_min = min(float(row["total_train_time_sec"]) for row in rows)
    infer_time_min = min(float(row["inference_time_per_image_ms"]) for row in rows)

    def maybe_bold(text: str, condition: bool) -> str:
        return rf"\textbf{{{text}}}" if condition else text

    lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\caption{Performance comparison of each model under its best learning rate}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"Model & Params & FLOPs & Train Time / s & Infer Time / ms \\",
        r"\midrule",
    ]

    for row in rows:
        param_count = int(row["param_count"])
        flops_per_image = int(row["flops_per_image"])
        total_train_time = float(row["total_train_time_sec"])
        infer_time = float(row["inference_time_per_image_ms"])
        lines.append(
            "{} & {} & {} & {} & {} \\\\".format(
                row["display_name"],
                maybe_bold(f"{param_count:,}", param_count == params_min),
                maybe_bold(f"{flops_per_image:,}", flops_per_image == flops_min),
                maybe_bold(f"{total_train_time:.1f}", total_train_time == train_time_min),
                maybe_bold(f"{infer_time:.3f}", infer_time == infer_time_min),
            )
        )

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\label{tab:model_compare}",
            r"\end{table*}",
        ]
    )

    out_path = TABLE_DIR / "model_comparison.tex"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def generate_sweep_table(rows: list[dict[str, str]]) -> Path:
    best_val_max = max(float(row["best_val_acc"]) for row in rows)
    test_acc_max = max(float(row["test_acc"]) for row in rows)
    def maybe_bold(text: str, condition: bool) -> str:
        return rf"\textbf{{{text}}}" if condition else text

    lines = [
        r"\begin{table*}[htbp]",
        r"\centering",
        r"\caption{Best configurations selected from learning-rate sweep}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"Model & Best LR & Best Val Acc & Test Acc \\",
        r"\midrule",
    ]

    for row in rows:
        best_val_acc = float(row["best_val_acc"])
        test_acc = float(row["test_acc"])
        lines.append(
            "{} & {} & {} & {} \\\\".format(
                row["display_name"],
                row["best_learning_rate"],
                maybe_bold(f"{best_val_acc * 100:.2f}\\%", best_val_acc == best_val_max),
                maybe_bold(f"{test_acc * 100:.2f}\\%", test_acc == test_acc_max),
            )
        )

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\label{tab:best_lr}",
            r"\end{table*}",
        ]
    )
    out_path = TABLE_DIR / "best_lr_summary.tex"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main() -> None:
    ensure_dirs()
    summary_rows: list[dict[str, str]] = []
    best_runs: dict[str, Path] = {}

    for model in MODELS:
        run_dir, best_info, summary = resolve_best_run_dir(model)
        best_runs[model] = run_dir
        plot_curves(model, run_dir)
    for model in MODELS:
        run_dir, best_info, summary = resolve_best_run_dir(model)
        summary_rows.append(
            {
                "model": model,
                "display_name": MODEL_DISPLAY_NAMES[model],
                "best_learning_rate": best_info["best_learning_rate"],
                "best_val_acc": summary["best_val_acc"],
                "best_val_epoch": summary["best_val_epoch"],
                "test_acc": summary["test_acc"],
                "param_count": summary["param_count"],
                "flops_per_image": summary["flops_per_image"],
                "total_train_time_sec": summary["total_train_time_sec"],
                "inference_time_per_image_ms": summary["inference_time_per_image_ms"],
            }
        )

    plot_combined_curves(best_runs)
    plot_metric_comparison(best_runs)
    plot_validation_grid(best_runs)
    plot_class_accuracy_and_bacc(best_runs)
    generate_summary_table(summary_rows)
    generate_sweep_table(summary_rows)

    manifest_lines = [
        "Generated figure files:",
        *[f"- 实验模板/fig/generated/{model}_curves.png" for model in MODELS],
        "- 实验模板/fig/generated/all_models_loss_curves.png",
        "- 实验模板/fig/generated/all_models_accuracy_curves.png",
        "- 实验模板/fig/generated/all_models_train_loss.png",
        "- 实验模板/fig/generated/all_models_val_loss.png",
        "- 实验模板/fig/generated/all_models_train_acc.png",
        "- 实验模板/fig/generated/all_models_val_acc.png",
        "- 实验模板/fig/generated/all_models_val_grid.png",
        "- 实验模板/fig/generated/class_accuracy.png",
        "",
        "Generated table files:",
        "- 实验模板/tables/model_comparison.tex",
        "- 实验模板/tables/best_lr_summary.tex",
    ]
    (TEMPLATE_DIR / "generated_assets_manifest.txt").write_text(
        "\n".join(manifest_lines),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
