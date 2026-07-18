from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt


ROOT = Path("/Users/linshangjin/Desktop/DeepLearning/lab2")
OUT_DIR = ROOT / "实验模板" / "fig" / "generated"

RUNS = {
    "RNN": ROOT / "outputs" / "rnn" / "sweep_rnn_optadam_h128_lr0p001_bs128",
    "myLSTM": ROOT / "outputs" / "myLSTM" / "sweep_myLSTM_optadam_h128_lr0p01_bs128",
    "myGRU": ROOT / "outputs" / "myGRU" / "sweep_myGRU_optadam_h128_lr0p005_bs128",
}


def read_epoch_metrics(csv_path: Path) -> dict[str, list[float]]:
    metrics: dict[str, list[float]] = {
        "epoch": [],
        "train_loss": [],
        "val_loss": [],
        "train_acc": [],
        "val_acc": [],
    }
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            for key in metrics:
                metrics[key].append(float(row[key]))
    return metrics


def make_curve_grid() -> None:
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 7.2), constrained_layout=True)
    for column, (model_name, run_dir) in enumerate(RUNS.items()):
        metrics = read_epoch_metrics(run_dir / "epoch_metrics.csv")
        epochs = metrics["epoch"]

        loss_ax = axes[0, column]
        loss_ax.plot(epochs, metrics["train_loss"], label="Train Loss", linewidth=1.6)
        loss_ax.plot(epochs, metrics["val_loss"], label="Val Loss", linewidth=1.6)
        loss_ax.set_xlabel("Epoch")
        loss_ax.set_ylabel("Loss")
        loss_ax.grid(alpha=0.25)
        if column == 0:
            loss_ax.legend(fontsize=8)

        acc_ax = axes[1, column]
        acc_ax.plot(epochs, metrics["train_acc"], label="Train Acc", linewidth=1.6)
        acc_ax.plot(epochs, metrics["val_acc"], label="Val Acc", linewidth=1.6)
        acc_ax.set_xlabel("Epoch")
        acc_ax.set_ylabel("Accuracy")
        acc_ax.grid(alpha=0.25)
        if column == 0:
            acc_ax.legend(fontsize=8)

    fig.savefig(OUT_DIR / "rnn_mylstm_mygru_curves_grid.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def make_confusion_grid() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4), constrained_layout=True)
    for axis, (_, run_dir) in zip(axes, RUNS.items()):
        image = mpimg.imread(run_dir / "val_confusion_matrix.png")
        axis.imshow(image)
        axis.axis("off")

    fig.savefig(OUT_DIR / "rnn_mylstm_mygru_confusion_grid.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    make_curve_grid()
    make_confusion_grid()


if __name__ == "__main__":
    main()
