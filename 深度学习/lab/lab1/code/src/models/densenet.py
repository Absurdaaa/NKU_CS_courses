from __future__ import annotations

import torch
import torch.nn as nn
from typing import Sequence

# 稠密层
class DenseLayer(nn.Module):
    def __init__(
        self,
        in_channels: int,
        growth_rate: int,
        bottleneck_width: int = 4,
        dropout_rate: float = 0.0,
    ) -> None:
        super().__init__()
        # 瓶颈层，以减少输入特征映射数量，从而提高计算效率
        inner_channels = bottleneck_width * growth_rate
        self.norm1 = nn.BatchNorm2d(in_channels)
        self.relu1 = nn.ReLU(inplace=True)
        self.conv1 = nn.Conv2d(
            in_channels,
            inner_channels,
            kernel_size=1,
            stride=1,
            bias=False,
        )
        self.norm2 = nn.BatchNorm2d(inner_channels)
        self.relu2 = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(
            inner_channels,
            growth_rate,
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False,
        )
        self.dropout = nn.Dropout2d(dropout_rate) if dropout_rate > 0 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.norm1(x)
        out = self.relu1(out)
        out = self.conv1(out)
        out = self.norm2(out)
        out = self.relu2(out)
        out = self.conv2(out)
        out = self.dropout(out)
        return torch.cat([x, out], dim=1)

# 稠密块
class DenseBlock(nn.Module):
    def __init__(
        self,
        num_layers: int,
        in_channels: int,
        growth_rate: int,
        bottleneck_width: int = 4,
        dropout_rate: float = 0.0,
    ) -> None:
        super().__init__()
        layers = []
        current_channels = in_channels
        for _ in range(num_layers):
            layers.append(
                DenseLayer(
                    current_channels,
                    growth_rate,
                    bottleneck_width=bottleneck_width,
                    dropout_rate=dropout_rate,
                )
            )
            current_channels += growth_rate
        self.layers = nn.Sequential(*layers)
        self.out_channels = current_channels

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


class TransitionLayer(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.BatchNorm2d(in_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels, out_channels, kernel_size=1, bias=False),
            nn.AvgPool2d(kernel_size=2, stride=2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


class DenseNet(nn.Module):
    def __init__(
        self,
        growth_rate: int = 12,
        block_layers: Sequence[int] = (16, 16, 16),
        compression: float = 0.5,
        bottleneck_width: int = 4,
        dropout_rate: float = 0.0,
        num_classes: int = 10,
    ) -> None:
        super().__init__()
        if len(block_layers) == 0:
            raise ValueError("block_layers must contain at least one dense block.")

        channels = growth_rate * 2

        self.stem = nn.Conv2d(
            3,
            channels,
            kernel_size=3,
            stride=1,
            padding=1,
            bias=False,
        )

        self.blocks = nn.ModuleList()
        self.transitions = nn.ModuleList()

        for block_index, num_layers in enumerate(block_layers):
            block = DenseBlock(
                num_layers,
                channels,
                growth_rate,
                bottleneck_width=bottleneck_width,
                dropout_rate=dropout_rate,
            )
            self.blocks.append(block)
            channels = block.out_channels

            if block_index != len(block_layers) - 1:
                reduced_channels = int(channels * compression)
                self.transitions.append(TransitionLayer(channels, reduced_channels))
                channels = reduced_channels

        self.norm = nn.BatchNorm2d(channels)
        self.relu = nn.ReLU(inplace=True)
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(channels, num_classes)

        self._initialize_weights()

    def _initialize_weights(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, mode="fan_out", nonlinearity="relu")
            elif isinstance(module, nn.BatchNorm2d):
                nn.init.constant_(module.weight, 1)
                nn.init.constant_(module.bias, 0)
            elif isinstance(module, nn.Linear):
                nn.init.normal_(module.weight, 0, 0.01)
                nn.init.constant_(module.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        for block_index, block in enumerate(self.blocks):
            x = block(x)
            if block_index < len(self.transitions):
                x = self.transitions[block_index](x)
        x = self.norm(x)
        x = self.relu(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x


def densenet_bc_100(num_classes: int = 10) -> DenseNet:
    return DenseNet(
        growth_rate=12,
        block_layers=(16, 16, 16),
        compression=0.5,
        bottleneck_width=4,
        dropout_rate=0.0,
        num_classes=num_classes,
    )
