#!/usr/bin/env python3
"""Lab4 正式训练入口。"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

from src.utils.runtime import set_seed, setup_matplotlib

setup_matplotlib(PROJECT_ROOT)

from src.config import parse_config
from src.data import build_dataloaders
from src.engine import run_training
from src.models import build_model
from src.utils.io import ensure_dir, save_model_summary, save_run_metadata
from src.utils.paths import build_run_name


def main() -> None:
    config = parse_config(PROJECT_ROOT)
    set_seed(config.seed)

    output_dir = config.output_dir / config.model / build_run_name(config)
    ensure_dir(output_dir)

    dataloaders = build_dataloaders(config)
    generator, discriminator = build_model(
        config.model,
        latent_dim=config.latent_dim,
        hidden_dim=config.hidden_dim,
        image_size=config.image_size,
        image_channels=config.image_channels,
        generator_base_channels=config.generator_base_channels,
        discriminator_base_channels=config.discriminator_base_channels,
        disc_dropout=config.disc_dropout,
    )

    print(f"Using device: {config.device}")
    print(f"Run name: {output_dir.name}")
    print(f"Train size: {len(dataloaders.train_loader.dataset)}")
    print(f"Val size: {len(dataloaders.val_loader.dataset)}")
    print(f"Test size: {len(dataloaders.test_loader.dataset)}")
    print("\nGenerator structure:\n")
    print(generator)
    print("\nDiscriminator structure:\n")
    print(discriminator)

    save_model_summary(generator, discriminator, str(config.device), output_dir / "model_structure.txt")
    save_run_metadata(
        {
            "model": config.model,
            "run_name": output_dir.name,
            "epochs": config.epochs,
            "batch_size": config.batch_size,
            "lr": config.lr,
            "optimizer": config.optimizer,
            "beta1": config.beta1,
            "latent_dim": config.latent_dim,
            "hidden_dim": config.hidden_dim,
            "image_size": config.image_size,
            "image_channels": config.image_channels,
            "generator_base_channels": config.generator_base_channels,
            "discriminator_base_channels": config.discriminator_base_channels,
            "label_smoothing": config.label_smoothing,
            "d_lr": config.d_lr,
            "disc_dropout": config.disc_dropout,
            "seed": config.seed,
            "device": str(config.device),
            "train_size": len(dataloaders.train_loader.dataset),
            "val_size": len(dataloaders.val_loader.dataset),
            "test_size": len(dataloaders.test_loader.dataset),
            "class_names": list(dataloaders.class_names),
        },
        output_dir / "run_metadata.json",
    )

    summary = run_training(
        generator=generator,
        discriminator=discriminator,
        dataloaders=dataloaders,
        config=config,
        output_dir=output_dir,
    )

    print(f"\nSaved outputs to: {output_dir}")
    print(f"- model structure: {output_dir / 'model_structure.txt'}")
    print(f"- epoch logs: {output_dir / 'epoch_metrics.csv'}")
    print(f"- summary metrics: {output_dir / 'summary_metrics.csv'}")
    print(f"- run metadata: {output_dir / 'run_metadata.json'}")
    print(f"- training curves: {output_dir / 'training_curves.png'}")
    print(f"- generated samples: {output_dir / 'generated_samples.png'}")
    print(f"- best checkpoint: {output_dir / 'best_model.pth'}")
    print(f"- best val generator loss: {summary['best_val_generator_loss']:.6f}")


if __name__ == "__main__":
    main()
