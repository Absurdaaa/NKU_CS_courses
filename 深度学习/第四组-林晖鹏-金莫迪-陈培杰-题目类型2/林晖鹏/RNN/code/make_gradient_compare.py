from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path("/Users/linshangjin/Desktop/DeepLearning/lab2")
OUT_DIR = ROOT / "实验模板" / "fig" / "generated"

RNN_CSV = ROOT / "outputs" / "rnn" / "sweep_rnn_optadam_h128_lr0p001_bs128" / "gradient_metrics.csv"
LSTM_CSV = ROOT / "outputs" / "lstm" / "sweep_lstm_optadam_h128_lr0p01_bs128" / "gradient_metrics.csv"


def read_gradients(csv_path: Path) -> tuple[list[int], list[float]]:
    steps: list[int] = []
    grads: list[float] = []
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            steps.append(int(row["global_step"]))
            grads.append(float(row["grad_norm_before_clip"]))
    return steps, grads


def moving_average(values: list[float], window: int = 100) -> list[float]:
    if not values:
        return []
    result: list[float] = []
    running_sum = 0.0
    for idx, value in enumerate(values):
        running_sum += value
        if idx >= window:
            running_sum -= values[idx - window]
            result.append(running_sum / window)
        else:
            result.append(running_sum / (idx + 1))
    return result


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rnn_steps, rnn_grads = read_gradients(RNN_CSV)
    lstm_steps, lstm_grads = read_gradients(LSTM_CSV)

    rnn_ma = moving_average(rnn_grads, window=100)
    lstm_ma = moving_average(lstm_grads, window=100)

    rnn_mean = sum(rnn_grads) / len(rnn_grads)
    lstm_mean = sum(lstm_grads) / len(lstm_grads)

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.8), constrained_layout=True)

    sample_stride = 25
    axes[0].plot(rnn_steps[::sample_stride], rnn_grads[::sample_stride], color="#d95f02", alpha=0.18, linewidth=0.8)
    axes[0].plot(lstm_steps[::sample_stride], lstm_grads[::sample_stride], color="#1b9e77", alpha=0.18, linewidth=0.8)
    axes[0].plot(rnn_steps, rnn_ma, color="#d95f02", linewidth=2.0, label=f"RNN moving avg (mean={rnn_mean:.3f})")
    axes[0].plot(lstm_steps, lstm_ma, color="#1b9e77", linewidth=2.0, label=f"LSTM moving avg (mean={lstm_mean:.3f})")
    axes[0].set_xlabel("Global Step")
    axes[0].set_ylabel("Gradient Norm")
    axes[0].set_title("Gradient Norm over Training")
    axes[0].grid(alpha=0.25)
    axes[0].legend(fontsize=8)

    box = axes[1].boxplot(
        [rnn_grads, lstm_grads],
        labels=["RNN", "LSTM"],
        patch_artist=True,
        showfliers=False,
    )
    colors = ["#d95f02", "#1b9e77"]
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.45)
    axes[1].set_ylabel("Gradient Norm")
    axes[1].set_title("Gradient Distribution")
    axes[1].grid(alpha=0.25, axis="y")

    fig.savefig(OUT_DIR / "rnn_lstm_gradient_compare.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
