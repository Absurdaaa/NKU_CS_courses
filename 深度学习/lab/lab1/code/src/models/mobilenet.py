"""CIFAR-style MobileNetV1 implementations."""

from __future__ import annotations

import torch
import torch.nn as nn


class DepthwiseSeparableConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, stride: int = 1) -> None:
        super().__init__()
        self.depthwise = nn.Sequential(
            nn.Conv2d(
                in_channels,
                in_channels,
                kernel_size=3,
                stride=stride,
                padding=1,
                groups=in_channels,
                bias=False,
            ),
            nn.BatchNorm2d(in_channels),
            nn.ReLU(inplace=True),
        )
        self.pointwise = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.depthwise(x)
        x = self.pointwise(x)
        return x


class MobileNetV1(nn.Module):
    def __init__(
        self,
        num_classes: int = 10,
        width_multiplier: float = 1.0,
    ) -> None:
        super().__init__()

        def c(channels: int) -> int:
            return max(1, int(channels * width_multiplier))

        self.stem = nn.Sequential(
            nn.Conv2d(3, c(32), kernel_size=3, stride=1, padding=1, bias=False),# 论文里面步长为2，但是对于32来说，可能不太好
            nn.BatchNorm2d(c(32)),
            nn.ReLU(inplace=True),
        )

        self.features = nn.Sequential(
            DepthwiseSeparableConv(c(32), c(64), stride=1),
            DepthwiseSeparableConv(c(64), c(128), stride=2),
            DepthwiseSeparableConv(c(128), c(128), stride=1),
            DepthwiseSeparableConv(c(128), c(256), stride=2),
            DepthwiseSeparableConv(c(256), c(256), stride=1),
            DepthwiseSeparableConv(c(256), c(512), stride=2),
            DepthwiseSeparableConv(c(512), c(512), stride=1),
            DepthwiseSeparableConv(c(512), c(512), stride=1),
            DepthwiseSeparableConv(c(512), c(512), stride=1),
            DepthwiseSeparableConv(c(512), c(512), stride=1),
            DepthwiseSeparableConv(c(512), c(512), stride=1),
            # DepthwiseSeparableConv(c(512), c(1024), stride=2),
            # DepthwiseSeparableConv(c(1024), c(1024), stride=1),# 论文里面是这样实现的，但是这里会不会太大了
        )
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(c(512), num_classes)

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
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x


def mobilenet_v1(num_classes: int = 10) -> MobileNetV1:
    return MobileNetV1(num_classes=num_classes, width_multiplier=1.0)
