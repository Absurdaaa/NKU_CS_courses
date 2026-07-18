"""CIFAR-style Res2Net implementations based on the ResNeXt-29 baseline."""

from __future__ import annotations

import torch
import torch.nn as nn


def conv3x3(
    in_channels: int,
    out_channels: int,
    stride: int = 1,
    groups: int = 1,
) -> nn.Conv2d:
    return nn.Conv2d(
        in_channels,
        out_channels,
        kernel_size=3,
        stride=stride,
        padding=1,
        groups=groups,
        bias=False,
    )


class Bottle2neck(nn.Module):
    expansion = 4

    def __init__(
        self,
        in_channels: int,
        base_channels: int,
        stride: int = 1,
        base_width: int = 64,
        scale: int = 4,
        cardinality: int = 8,
        stype: str = "normal",
    ) -> None:
        super().__init__()
        if scale < 2:
            raise ValueError("Res2Net scale must be at least 2.")

        width = cardinality * base_width
        inner_channels = width * scale
        out_channels = base_channels * self.expansion

        self.width = width
        self.scale = scale
        self.stype = stype
        self.cardinality = cardinality
        self.relu = nn.ReLU(inplace=True)

        self.conv1 = nn.Conv2d(in_channels, inner_channels, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(inner_channels)

        self.convs = nn.ModuleList(
            [
                conv3x3(width, width, stride=stride, groups=cardinality)
                for _ in range(scale - 1)
            ]
        )
        self.bns = nn.ModuleList([nn.BatchNorm2d(width) for _ in range(scale - 1)])

        self.pool = (
            nn.AvgPool2d(kernel_size=3, stride=stride, padding=1)
            if stype == "stage"
            else None
        )

        self.conv3 = nn.Conv2d(inner_channels, out_channels, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(out_channels)

        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(
                    in_channels,
                    out_channels,
                    kernel_size=1,
                    stride=stride,
                    bias=False,
                ),
                nn.BatchNorm2d(out_channels),
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = self.shortcut(x)

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        splits = torch.split(out, self.width, dim=1)
        outputs = []

        for idx in range(self.scale - 1):
            if idx == 0 or self.stype == "stage":
                sp = splits[idx]
            else:
                sp = splits[idx] + outputs[idx - 1]
            sp = self.convs[idx](sp)
            sp = self.bns[idx](sp)
            sp = self.relu(sp)
            outputs.append(sp)

        if self.stype == "normal":
            outputs.append(splits[-1])
        else:
            outputs.append(self.pool(splits[-1]))

        out = torch.cat(outputs, dim=1)
        out = self.conv3(out)
        out = self.bn3(out)
        out += identity
        out = self.relu(out)
        return out


class Res2Net(nn.Module):
    def __init__(
        self,
        layers: list[int],
        num_classes: int = 10,
        base_width: int = 64,
        scale: int = 4,
        cardinality: int = 8,
    ) -> None:
        super().__init__()
        self.in_channels = 64
        self.base_width = base_width
        self.scale = scale
        self.cardinality = cardinality

        self.stem = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
        )

        self.layer1 = self._make_layer(base_channels=64, blocks=layers[0], stride=1)
        self.layer2 = self._make_layer(base_channels=128, blocks=layers[1], stride=2)
        self.layer3 = self._make_layer(base_channels=256, blocks=layers[2], stride=2)
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(256 * Bottle2neck.expansion, num_classes)

        self._initialize_weights()

    def _make_layer(self, base_channels: int, blocks: int, stride: int) -> nn.Sequential:
        layers = [
            Bottle2neck(
                self.in_channels,
                base_channels,
                stride=stride,
                base_width=self.base_width,
                scale=self.scale,
                cardinality=self.cardinality,
                stype="stage",
            )
        ]
        self.in_channels = base_channels * Bottle2neck.expansion

        for _ in range(1, blocks):
            layers.append(
                Bottle2neck(
                    self.in_channels,
                    base_channels,
                    stride=1,
                    base_width=self.base_width,
                    scale=self.scale,
                    cardinality=self.cardinality,
                    stype="normal",
                )
            )
        return nn.Sequential(*layers)

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
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.fc(x)
        return x


def res2net29_8c64w(num_classes: int = 10) -> Res2Net:
    return Res2Net(
        layers=[3, 3, 3],
        num_classes=num_classes,
        base_width=16,
        scale=4,
        cardinality=4,
    )
