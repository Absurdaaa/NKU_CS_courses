"""卷积版 DCGAN 模型。"""

from __future__ import annotations

import torch
from torch import nn


class DCGANGenerator(nn.Module):
    """基于转置卷积的 DCGAN 生成器。"""

    def __init__(
        self,
        latent_dim: int = 100,
        image_channels: int = 1,
        base_channels: int = 64,
    ) -> None:
        super().__init__()
        self.main = nn.Sequential(
            nn.ConvTranspose2d(latent_dim, base_channels * 4, 7, 1, 0, bias=False),
            nn.BatchNorm2d(base_channels * 4),
            nn.ReLU(True),
            nn.ConvTranspose2d(base_channels * 4, base_channels * 2, 4, 2, 1, bias=False),
            nn.BatchNorm2d(base_channels * 2),
            nn.ReLU(True),
            nn.ConvTranspose2d(base_channels * 2, base_channels, 4, 2, 1, bias=False),
            nn.BatchNorm2d(base_channels),
            nn.ReLU(True),
            nn.ConvTranspose2d(base_channels, image_channels, 3, 1, 1, bias=False),
            nn.Tanh(),
        )

    def forward(self, noise: torch.Tensor) -> torch.Tensor:
        return self.main(noise)


class DCGANDiscriminator(nn.Module):
    """基于卷积的 DCGAN 判别器。"""

    def __init__(self, image_channels: int = 1, base_channels: int = 64) -> None:
        super().__init__()
        self.main = nn.Sequential(
            nn.Conv2d(image_channels, base_channels, 4, 2, 1, bias=False),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(base_channels, base_channels * 2, 4, 2, 1, bias=False),
            nn.BatchNorm2d(base_channels * 2),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(base_channels * 2, base_channels * 4, 7, 1, 0, bias=False),
            nn.BatchNorm2d(base_channels * 4),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(base_channels * 4, 1, 1, 1, 0, bias=False),
            nn.Sigmoid(),
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        return self.main(images)
