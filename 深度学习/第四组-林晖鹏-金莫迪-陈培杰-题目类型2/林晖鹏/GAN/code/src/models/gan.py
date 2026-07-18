"""全连接 GAN 模型。

本文件提供两组全连接生成器/判别器：

- ``GANGenerator`` / ``GANDiscriminator`` —— 老师提供的原始版本（单隐藏层 MLP），
  容量很小，作为对比基线。
- ``DeepGANGenerator`` / ``DeepGANDiscriminator`` —— 自由调整后的加深版本，
  生成器采用经典的 100 -> 256 -> 512 -> 1024 -> 784 阶梯结构并加入 BatchNorm，
  生成质量明显优于原始版本。
"""

from __future__ import annotations

import torch
from torch import nn


class GANGenerator(nn.Module):
    """基于 MLP 的 FashionMNIST 生成器（原始版本，单隐藏层）。"""

    def __init__(self, latent_dim: int = 100, hidden_dim: int = 128, image_size: int = 28) -> None:
        super().__init__()
        self.image_size = image_size
        self.fc1 = nn.Linear(latent_dim, hidden_dim)
        self.nonlin1 = nn.LeakyReLU(0.2)
        self.fc2 = nn.Linear(hidden_dim, image_size * image_size)

    def forward(self, noise: torch.Tensor) -> torch.Tensor:
        hidden = self.nonlin1(self.fc1(noise))
        output = torch.tanh(self.fc2(hidden))
        return output.view(output.size(0), 1, self.image_size, self.image_size)


class GANDiscriminator(nn.Module):
    """基于 MLP 的 FashionMNIST 判别器（原始版本，单隐藏层）。"""

    def __init__(self, input_dim: int = 28 * 28, hidden_dim: int = 128) -> None:
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.nonlin1 = nn.LeakyReLU(0.2)
        self.fc2 = nn.Linear(hidden_dim, 1)

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        flat = images.view(images.size(0), -1)
        hidden = self.nonlin1(self.fc1(flat))
        return torch.sigmoid(self.fc2(hidden))


class DeepGANGenerator(nn.Module):
    """加深版 MLP 生成器。

    采用经典的 100 -> 256 -> 512 -> 1024 -> 784 阶梯结构，每个隐藏层后接
    BatchNorm + LeakyReLU，最后 Tanh 输出到 [-1, 1]，与数据归一化保持一致。
    单隐藏层的小网络画不出衣物结构，所以这里用足够的容量。
    """

    def __init__(self, latent_dim: int = 100, hidden_dim: int = 128, image_size: int = 28) -> None:
        super().__init__()
        self.image_size = image_size
        output_dim = image_size * image_size

        def block(in_features: int, out_features: int) -> list[nn.Module]:
            return [
                nn.Linear(in_features, out_features),
                nn.BatchNorm1d(out_features),
                nn.LeakyReLU(0.2, inplace=True),
            ]

        self.model = nn.Sequential(
            *block(latent_dim, 256),
            *block(256, 512),
            *block(512, 1024),
            nn.Linear(1024, output_dim),
            nn.Tanh(),
        )

    def forward(self, noise: torch.Tensor) -> torch.Tensor:
        output = self.model(noise)
        return output.view(output.size(0), 1, self.image_size, self.image_size)


class DeepGANDiscriminator(nn.Module):
    """加深版 MLP 判别器。

    784 -> 512 -> 256 -> 1，隐藏层用 LeakyReLU + Dropout 防止判别器过强导致
    生成器梯度消失，最后 Sigmoid 输出真假概率（配合 BCELoss）。
    """

    def __init__(self, input_dim: int = 28 * 28, hidden_dim: int = 128, dropout: float = 0.3) -> None:
        super().__init__()
        self.model = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Dropout(dropout),
            nn.Linear(512, 256),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Dropout(dropout),
            nn.Linear(256, 1),
            nn.Sigmoid(),
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        flat = images.view(images.size(0), -1)
        return self.model(flat)
