#!/usr/bin/env python3
"""Lab4 学习率扫描入口。"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TRAIN_SCRIPT = PROJECT_ROOT / "train.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Learning-rate sweep helper for lab4")
    parser.add_argument("--model", required=True, choices=("gan", "gan_deep", "dcgan"), help="Model name.")
    parser.add_argument("--lrs", nargs="+", type=float, required=True, help="Learning rates to sweep.")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs.")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size.")
    parser.add_argument(
        "--optimizer",
        type=str,
        default="adam",
        choices=("adam", "sgd", "adamw"),
        help="Optimizer name.",
    )
    parser.add_argument("--beta1", type=float, default=0.5, help="Beta1 for Adam/AdamW.")
    parser.add_argument("--latent-dim", type=int, default=100, help="Latent dimension.")
    parser.add_argument("--hidden-dim", type=int, default=128, help="Hidden size for vanilla GAN.")
    parser.add_argument("--image-size", type=int, default=28, help="Training image size.")
    parser.add_argument("--image-channels", type=int, default=1, help="Image channels.")
    parser.add_argument("--generator-base-channels", type=int, default=64, help="DCGAN generator base channels.")
    parser.add_argument("--discriminator-base-channels", type=int, default=64, help="DCGAN discriminator base channels.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--num-workers", type=int, default=0, help="DataLoader workers.")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation ratio.")
    parser.add_argument("--max-train-samples", type=int, default=0, help="Optional cap for train split.")
    parser.add_argument("--max-val-samples", type=int, default=0, help="Optional cap for val split.")
    parser.add_argument("--max-test-samples", type=int, default=0, help="Optional cap for test split.")
    parser.add_argument("--fixed-noise-count", type=int, default=64, help="Fixed noise count for visualization.")
    parser.add_argument("--fid-eval-every", type=int, default=5, help="Compute FID every N epochs (0 disables).")
    parser.add_argument("--fid-samples", type=int, default=5000, help="Samples per FID computation.")
    parser.add_argument("--data-root", type=str, default=str(PROJECT_ROOT / "data"), help="Dataset root.")
    parser.add_argument("--output-dir", type=str, default=str(PROJECT_ROOT / "outputs"), help="Output root.")
    parser.add_argument("--device", type=str, default=None, help="Optional device override.")
    parser.add_argument("--sweep-name", type=str, default="sweep", help="Sweep run-name prefix.")
    return parser.parse_args()


def format_float_tag(value: float) -> str:
    return f"{value:.8g}".replace("-", "m").replace(".", "p")


def build_run_name(args: argparse.Namespace, lr: float) -> str:
    return (
        f"{args.sweep_name}_{args.model}_opt{args.optimizer}_"
        f"img{args.image_size}_z{args.latent_dim}_lr{format_float_tag(lr)}_bs{args.batch_size}"
    )


def build_training_command(args: argparse.Namespace, lr: float) -> tuple[list[str], Path]:
    run_name = build_run_name(args, lr)
    cmd = [
        sys.executable,
        str(TRAIN_SCRIPT),
        "--model",
        args.model,
        "--run-name",
        run_name,
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--lr",
        str(lr),
        "--optimizer",
        args.optimizer,
        "--beta1",
        str(args.beta1),
        "--latent-dim",
        str(args.latent_dim),
        "--hidden-dim",
        str(args.hidden_dim),
        "--image-size",
        str(args.image_size),
        "--image-channels",
        str(args.image_channels),
        "--generator-base-channels",
        str(args.generator_base_channels),
        "--discriminator-base-channels",
        str(args.discriminator_base_channels),
        "--seed",
        str(args.seed),
        "--num-workers",
        str(args.num_workers),
        "--val-ratio",
        str(args.val_ratio),
        "--max-train-samples",
        str(args.max_train_samples),
        "--max-val-samples",
        str(args.max_val_samples),
        "--max-test-samples",
        str(args.max_test_samples),
        "--fixed-noise-count",
        str(args.fixed_noise_count),
        "--fid-eval-every",
        str(args.fid_eval_every),
        "--fid-samples",
        str(args.fid_samples),
        "--data-root",
        args.data_root,
        "--output-dir",
        args.output_dir,
    ]
    if args.device:
        cmd.extend(["--device", args.device])
    summary_csv = Path(args.output_dir) / args.model / run_name / "summary_metrics.csv"
    return cmd, summary_csv


def load_summary_metrics(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {row["metric"]: row["value"] for row in reader}


def load_run_metadata(path: Path) -> dict[str, str]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def collect_summary_row(summary_csv: Path) -> dict[str, str]:
    summary = load_summary_metrics(summary_csv)
    metadata = load_run_metadata(summary_csv.parent / "run_metadata.json")
    return {
        "run_name": summary_csv.parent.name,
        "model": str(metadata["model"]),
        "optimizer": str(metadata["optimizer"]),
        "learning_rate": str(metadata["lr"]),
        "best_fid": summary.get("best_fid", ""),
        "best_fid_epoch": summary.get("best_fid_epoch", ""),
        "best_validation_score": summary.get("best_validation_score", summary["best_val_generator_loss"]),
        "best_val_generator_loss": summary["best_val_generator_loss"],
        "best_val_discriminator_loss": summary["best_val_discriminator_loss"],
        "best_epoch": summary["best_epoch"],
        "test_generator_loss": summary["test_generator_loss"],
        "test_discriminator_loss": summary["test_discriminator_loss"],
    }


def summarize_runs(output_root: Path, model: str, optimizer: str, rows: list[dict[str, str]]) -> tuple[Path, Path]:
    model_dir = output_root / model
    model_dir.mkdir(parents=True, exist_ok=True)

    def sort_key(item: dict[str, str]) -> float:
        # 优先按 FID（越低越好）选最优学习率；FID 缺失时退回均衡分。
        fid = item.get("best_fid", "")
        try:
            value = float(fid)
            if value == value and value != float("inf"):  # 非 NaN/inf
                return value
        except (TypeError, ValueError):
            pass
        return float(item.get("best_validation_score", item["best_val_generator_loss"]))

    rows = sorted(rows, key=sort_key)
    summary_path = model_dir / f"{model}_{optimizer}_lr_sweep_summary.csv"
    best_lr_path = model_dir / f"{model}_{optimizer}_best_lr.txt"

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    best_lr_path.write_text(rows[0]["learning_rate"], encoding="utf-8")
    return summary_path, best_lr_path


def main() -> None:
    args = parse_args()
    rows: list[dict[str, str]] = []

    total = len(args.lrs)
    for index, lr in enumerate(args.lrs, start=1):
        cmd, summary_csv = build_training_command(args, lr)
        run_name = build_run_name(args, lr)
        print(
            f"== [{index}/{total}] Sweep {args.model} lr={lr} run_name={run_name} ==",
            flush=True,
        )
        if not summary_csv.exists():
            print("Launching training run...", flush=True)
            subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
        else:
            print(f"Skip existing run: {summary_csv.parent}", flush=True)
        rows.append(collect_summary_row(summary_csv))
        print(
            f"Completed lr={lr}, best_validation_score={rows[-1]['best_validation_score']}",
            flush=True,
        )

    summary_path, best_lr_path = summarize_runs(Path(args.output_dir), args.model, args.optimizer, rows)
    print(f"Saved sweep summary to: {summary_path}", flush=True)
    print(f"Saved best lr to: {best_lr_path}", flush=True)


if __name__ == "__main__":
    main()
