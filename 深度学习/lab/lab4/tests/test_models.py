from __future__ import annotations

import sys
from pathlib import Path

import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models import build_model


def test_build_gan_models_forward_shapes() -> None:
    generator, discriminator = build_model("gan", latent_dim=100)

    noise = torch.randn(4, 100)
    fake_images = generator(noise)
    scores = discriminator(fake_images)

    assert fake_images.shape == (4, 1, 28, 28)
    assert scores.shape == (4, 1)


def test_build_dcgan_models_forward_shapes() -> None:
    generator, discriminator = build_model(
        "dcgan",
        latent_dim=100,
        image_channels=1,
        generator_base_channels=32,
        discriminator_base_channels=32,
    )

    noise = torch.randn(4, 100, 1, 1)
    fake_images = generator(noise)
    scores = discriminator(fake_images)

    assert fake_images.shape == (4, 1, 28, 28)
    assert scores.shape == (4, 1, 1, 1)
