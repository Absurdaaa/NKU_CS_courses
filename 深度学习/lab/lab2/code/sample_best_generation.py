#!/usr/bin/env python3
"""Load the best trained generation model and resample more names without retraining."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

import torch

from src.generation_data import GEN_OUTPUT_SIZE, NameGenerationDataset
from src.generation_engine import (
    build_generated_metrics,
    build_start_letter_pool,
    resolve_sample_categories,
    sample_name,
    save_generated_metrics,
    save_generated_samples,
)
from src.generation_config import GenerationConfig
from src.models.name_generator import build_generation_model
from src.utils.io import ensure_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resample names from the best generation checkpoints.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["rnn_gen", "lstm_gen", "gru_gen"],
        choices=("rnn_gen", "lstm_gen", "gru_gen"),
        help="Generation models to resample.",
    )
    parser.add_argument(
        "--runs",
        nargs="*",
        default=None,
        help="Optional explicit generation run directories. If provided, --models is ignored for selection order.",
    )
    parser.add_argument(
        "--data-root",
        default=str(PROJECT_ROOT / "data" / "names"),
        help="Directory containing per-language name files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "outputs" / "generation" / "resampled"),
        help="Where to save resampled names.",
    )
    parser.add_argument(
        "--sample-categories",
        default="Russian,German,Spanish,Chinese",
        help='Categories to sample, comma-separated, or "all".',
    )
    parser.add_argument("--samples-per-category", type=int, default=50, help="How many names to generate per category.")
    parser.add_argument("--sample-max-length", type=int, default=20, help="Maximum generated length.")
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Inference device.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for start-letter sampling.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_best_run_for_model(generation_root: Path, model_name: str) -> Path:
    best_run = None
    best_loss = None
    for run_dir in sorted(generation_root.glob(f"{model_name}_opt*")):
        summary_path = run_dir / "summary_metrics.csv"
        if not summary_path.exists():
            continue
        metrics: dict[str, str] = {}
        with summary_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            for row in reader:
                if len(row) >= 2:
                    metrics[row[0]] = row[1]
        if "best_train_loss" not in metrics:
            continue
        loss = float(metrics["best_train_loss"])
        if best_loss is None or loss < best_loss:
            best_loss = loss
            best_run = run_dir
    if best_run is None:
        raise FileNotFoundError(f"No completed sweep run found for {model_name} under {generation_root}.")
    return best_run


def build_sampling_config(meta: dict[str, object], args: argparse.Namespace) -> GenerationConfig:
    return GenerationConfig(
        model=str(meta["model"]),
        run_name=str(meta.get("run_name", "")),
        epochs=int(meta.get("epochs", 0)),
        batch_size=int(meta.get("batch_size", 1)),
        max_samples_per_epoch=int(meta.get("max_samples_per_epoch", 0)),
        lr=float(meta.get("lr", 0.0)),
        optimizer=str(meta.get("optimizer", "adam")),
        hidden_size=int(meta["hidden_size"]),
        dropout=float(meta.get("dropout", 0.0)),
        clip_grad_norm=float(meta.get("clip_grad_norm", 0.0)),
        seed=int(args.seed),
        data_root=Path(args.data_root),
        output_dir=Path(args.output_dir),
        device=torch.device(args.device),
        sample_max_length=int(args.sample_max_length),
        sample_categories=str(args.sample_categories),
        samples_per_category=int(args.samples_per_category),
    )


def resample_from_run(run_dir: Path, args: argparse.Namespace, dataset: NameGenerationDataset, rng: random.Random) -> Path:
    meta = load_json(run_dir / "run_metadata.json")
    config = build_sampling_config(meta, args)
    output_dir = Path(args.output_dir) / f"{run_dir.name}_resampled"
    ensure_dir(output_dir)

    model = build_generation_model(
        model_name=str(meta["model"]),
        num_categories=len(dataset.class_names),
        input_size=GEN_OUTPUT_SIZE - 1,
        hidden_size=int(meta["hidden_size"]),
        output_size=GEN_OUTPUT_SIZE,
        dropout=float(meta.get("dropout", 0.0)),
    ).to(config.device)
    state_dict = torch.load(run_dir / "best_model.pth", map_location=config.device)
    model.load_state_dict(state_dict)
    model.eval()

    generated_samples: dict[str, list[str]] = {}
    for category_name in resolve_sample_categories(dataset, config):
        if category_name not in dataset.class_names:
            continue
        category_index = dataset.class_names.index(category_name)
        start_letter_pool = build_start_letter_pool(dataset, category_name)
        generated_samples[category_name] = []
        for _ in range(config.samples_per_category):
            start_letter = rng.choice(start_letter_pool)
            generated_samples[category_name].append(
                sample_name(model, category_index, len(dataset.class_names), start_letter, config)
            )

    save_generated_samples(output_dir / "generated_samples.txt", generated_samples)
    save_generated_metrics(output_dir / "generated_metrics.csv", build_generated_metrics(dataset, generated_samples))
    (output_dir / "source_run.txt").write_text(run_dir.as_posix() + "\n", encoding="utf-8")
    (output_dir / "resample_metadata.json").write_text(
        json.dumps(
            {
                "source_run": run_dir.as_posix(),
                "model": meta["model"],
                "sample_categories": args.sample_categories,
                "samples_per_category": args.samples_per_category,
                "sample_max_length": args.sample_max_length,
                "seed": args.seed,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return output_dir


def main() -> None:
    args = parse_args()
    dataset = NameGenerationDataset(Path(args.data_root))
    generation_root = PROJECT_ROOT / "outputs" / "generation"
    rng = random.Random(args.seed)

    run_dirs: list[Path]
    if args.runs:
        run_dirs = [Path(path).resolve() for path in args.runs]
    else:
        run_dirs = [find_best_run_for_model(generation_root, model_name) for model_name in args.models]

    for run_dir in run_dirs:
        output_dir = resample_from_run(run_dir, args, dataset, rng)
        print(f"Saved resampled names to: {output_dir}")
        print(f"- generated samples: {output_dir / 'generated_samples.txt'}")
        print(f"- generated metrics: {output_dir / 'generated_metrics.csv'}")


if __name__ == "__main__":
    main()
