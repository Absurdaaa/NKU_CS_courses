#!/usr/bin/env python3
"""Project entrypoint for conditional name generation experiments."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

from src.generation_config import parse_generation_config
from src.generation_data import GEN_OUTPUT_SIZE, NameGenerationDataset
from src.generation_engine import run_generation_training
from src.models.name_generator import build_generation_model
from src.utils.io import ensure_dir, save_model_summary, save_run_metadata
from src.utils.runtime import set_seed, setup_matplotlib


def build_run_name(config) -> str:
    if config.run_name:
        return config.run_name
    lr_string = str(config.lr).replace(".", "p")
    return f"{config.model}_h{config.hidden_size}_lr{lr_string}"


def main() -> None:
    config = parse_generation_config(PROJECT_ROOT)
    setup_matplotlib(PROJECT_ROOT)
    set_seed(config.seed)
    from src.utils.plotting import save_generation_loss_curve

    output_dir = config.output_dir / build_run_name(config)
    ensure_dir(output_dir)

    dataset = NameGenerationDataset(config.data_root)
    model = build_generation_model(
        model_name=config.model,
        num_categories=len(dataset.class_names),
        input_size=GEN_OUTPUT_SIZE - 1,
        hidden_size=config.hidden_size,
        output_size=GEN_OUTPUT_SIZE,
        dropout=config.dropout,
    ).to(config.device)

    print(f"Using device: {config.device}")
    print(f"Run name: {output_dir.name}")
    print(f"Sample count: {len(dataset)}")
    print(f"Class count: {len(dataset.class_names)}")
    print("\nModel structure:\n")
    print(model)

    save_model_summary(model, str(config.device), output_dir / "model_structure.txt")
    save_run_metadata(
        {
            "task": "conditional_name_generation",
            "model": config.model,
            "run_name": output_dir.name,
            "epochs": config.epochs,
            "batch_size": config.batch_size,
            "max_samples_per_epoch": config.max_samples_per_epoch,
            "optimizer": config.optimizer,
            "lr": config.lr,
            "hidden_size": config.hidden_size,
            "dropout": config.dropout,
            "clip_grad_norm": config.clip_grad_norm,
            "seed": config.seed,
            "device": str(config.device),
            "sample_count": len(dataset),
            "class_count": len(dataset.class_names),
            "class_names": dataset.class_names,
            "sample_categories": config.sample_categories,
            "samples_per_category": config.samples_per_category,
        },
        output_dir / "run_metadata.json",
    )

    history, summary, generated_samples = run_generation_training(
        model=model,
        dataset=dataset,
        config=config,
        output_dir=output_dir,
    )
    save_generation_loss_curve(history, output_dir / "training_loss_curve.png")

    print(f"\nSaved outputs to: {output_dir}")
    print(f"- model structure: {output_dir / 'model_structure.txt'}")
    print(f"- epoch logs: {output_dir / 'epoch_metrics.csv'}")
    print(f"- summary metrics: {output_dir / 'summary_metrics.csv'}")
    print(f"- run metadata: {output_dir / 'run_metadata.json'}")
    print(f"- training curve: {output_dir / 'training_loss_curve.png'}")
    print(f"- generated samples: {output_dir / 'generated_samples.txt'}")
    print(f"- generated metrics: {output_dir / 'generated_metrics.csv'}")
    print(f"- best checkpoint: {output_dir / 'best_model.pth'}")
    print(f"- best train loss: {summary['best_train_loss']:.4f}")
    print("\nPreview:")
    for category_name, samples in generated_samples.items():
        print(f"[{category_name}]")
        for sample in samples:
            print(f"  {sample}")


if __name__ == "__main__":
    main()
