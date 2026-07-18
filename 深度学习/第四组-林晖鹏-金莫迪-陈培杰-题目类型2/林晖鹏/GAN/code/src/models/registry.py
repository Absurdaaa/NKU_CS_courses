"""统一维护模型名与构建入口。"""

from __future__ import annotations

from torch import nn

from src.models.dcgan import DCGANDiscriminator, DCGANGenerator
from src.models.gan import (
    DeepGANDiscriminator,
    DeepGANGenerator,
    GANDiscriminator,
    GANGenerator,
)
from src.constants import AVAILABLE_MODELS


def init_weights(module: nn.Module) -> None:
    """DCGAN 论文式权重初始化：卷积/线性层 N(0, 0.02)，BatchNorm 权重 N(1, 0.02)。"""

    classname = module.__class__.__name__
    if isinstance(module, (nn.Conv2d, nn.ConvTranspose2d, nn.Linear)):
        nn.init.normal_(module.weight.data, 0.0, 0.02)
        if module.bias is not None:
            nn.init.constant_(module.bias.data, 0.0)
    elif "BatchNorm" in classname:
        nn.init.normal_(module.weight.data, 1.0, 0.02)
        nn.init.constant_(module.bias.data, 0.0)


def build_model(model_name: str, *args: object, **kwargs: object) -> tuple[object, object]:
    """按模型名构建 generator / discriminator。"""

    if model_name not in AVAILABLE_MODELS:
        raise ValueError(f"Unsupported model: {model_name}")

    if model_name in ("gan", "gan_deep"):
        latent_dim = int(kwargs.get("latent_dim", 100))
        hidden_dim = int(kwargs.get("hidden_dim", 128))
        image_size = int(kwargs.get("image_size", 28))
        gen_cls = GANGenerator if model_name == "gan" else DeepGANGenerator
        generator: nn.Module = gen_cls(latent_dim=latent_dim, hidden_dim=hidden_dim, image_size=image_size)
        if model_name == "gan":
            discriminator: nn.Module = GANDiscriminator(input_dim=image_size * image_size, hidden_dim=hidden_dim)
        else:
            disc_dropout = float(kwargs.get("disc_dropout", 0.3))
            discriminator = DeepGANDiscriminator(
                input_dim=image_size * image_size, hidden_dim=hidden_dim, dropout=disc_dropout
            )
    else:
        latent_dim = int(kwargs.get("latent_dim", 100))
        image_channels = int(kwargs.get("image_channels", 1))
        generator_base_channels = int(kwargs.get("generator_base_channels", 64))
        discriminator_base_channels = int(kwargs.get("discriminator_base_channels", 64))
        generator = DCGANGenerator(
            latent_dim=latent_dim,
            image_channels=image_channels,
            base_channels=generator_base_channels,
        )
        discriminator = DCGANDiscriminator(
            image_channels=image_channels,
            base_channels=discriminator_base_channels,
        )

    generator.apply(init_weights)
    discriminator.apply(init_weights)
    return generator, discriminator
