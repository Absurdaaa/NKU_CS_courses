from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import parse_config
from src.data import build_dataloaders
from src.engine import compute_validation_score, run_training
from src.models import build_model
from src.utils.io import ensure_dir
from src.utils.paths import build_run_name
from src.utils.runtime import set_seed


def test_parse_config_resolves_model_specific_image_size() -> None:
    gan_config = parse_config(
        PROJECT_ROOT,
        argv=[
            "--model",
            "gan",
            "--epochs",
            "1",
            "--batch-size",
            "8",
        ],
    )
    dcgan_config = parse_config(
        PROJECT_ROOT,
        argv=[
            "--model",
            "dcgan",
            "--epochs",
            "1",
            "--batch-size",
            "8",
        ],
    )

    assert gan_config.image_size == 28
    assert dcgan_config.image_size == 28
    assert gan_config.seed == 42
    assert dcgan_config.seed == 42


def test_build_dataloaders_returns_expected_batch_shape() -> None:
    config = parse_config(
        PROJECT_ROOT,
        argv=[
            "--model",
            "gan",
            "--epochs",
            "1",
            "--batch-size",
            "8",
            "--max-train-samples",
            "16",
            "--max-val-samples",
            "8",
            "--max-test-samples",
            "8",
        ],
    )

    dataloaders = build_dataloaders(config)
    batch = next(iter(dataloaders.train_loader))

    assert batch["images"].shape == (8, 1, 28, 28)
    assert batch["labels"].shape == (8,)
    assert dataloaders.class_names[0] == "T-shirt/top"


def test_run_training_smoke(tmp_path: Path) -> None:
    config = parse_config(
        PROJECT_ROOT,
        argv=[
            "--model",
            "gan",
            "--epochs",
            "1",
            "--batch-size",
            "8",
            "--max-train-samples",
            "16",
            "--max-val-samples",
            "8",
            "--max-test-samples",
            "8",
            "--output-dir",
            str(tmp_path),
        ],
    )
    set_seed(config.seed)
    dataloaders = build_dataloaders(config)
    output_dir = config.output_dir / config.model / build_run_name(config)
    ensure_dir(output_dir)

    generator, discriminator = build_model(
        config.model,
        latent_dim=config.latent_dim,
        hidden_dim=config.hidden_dim,
        image_size=config.image_size,
        image_channels=config.image_channels,
        generator_base_channels=config.generator_base_channels,
        discriminator_base_channels=config.discriminator_base_channels,
    )

    summary = run_training(
        generator=generator,
        discriminator=discriminator,
        dataloaders=dataloaders,
        config=config,
        output_dir=output_dir,
    )

    assert "best_val_generator_loss" in summary
    assert "best_validation_score" in summary
    assert (output_dir / "epoch_metrics.csv").exists()
    assert (output_dir / "summary_metrics.csv").exists()
    assert (output_dir / "best_model.pth").exists()
    assert (output_dir / "generated_samples.png").exists()


def test_compute_validation_score_penalizes_inverted_discriminator() -> None:
    collapsed_score = compute_validation_score(
        generator_loss=0.00018,
        discriminator_loss=16.01,
        d_real_mean=0.02,
        d_fake_mean=0.9998,
    )
    stable_score = compute_validation_score(
        generator_loss=1.15,
        discriminator_loss=1.12,
        d_real_mean=0.58,
        d_fake_mean=0.37,
    )

    assert stable_score < collapsed_score
