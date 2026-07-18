from __future__ import annotations

import torch.nn as nn
import torch

def conv3x3(in_channels: int, out_channels: int, stride: int = 1) -> nn.Conv2d:
    return nn.Conv2d(
        in_channels,
        out_channels,
        kernel_size=3,
        stride=stride,
        padding=1,
        bias=False,
    )


class BasicBlock(nn.Module):
    expansion = 1 # 在这里似乎没有用，是为了后面更深模型的Bottleneck准备的，但是感觉ai的写法反人类，为什么不写1/4，而且这个参数不显式写入？无语，理解半天

    def __init__(self, in_channels: int, base_channels: int, stride: int = 1) -> None:
        super().__init__()
        expanded_channels = base_channels * self.expansion

        self.conv1 = conv3x3(in_channels, base_channels, stride)
        self.bn1 = nn.BatchNorm2d(base_channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = conv3x3(base_channels, expanded_channels)
        self.bn2 = nn.BatchNorm2d(expanded_channels)

        if stride != 1 or in_channels != expanded_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(
                    in_channels,
                    expanded_channels,
                    kernel_size=1,
                    stride=stride,
                    bias=False,
                ),
                nn.BatchNorm2d(expanded_channels),
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = self.shortcut(x)

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out += identity
        out = self.relu(out)
        return out


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, in_channels: int, base_channels: int, stride: int = 1) -> None:
        super().__init__()
        expanded_channels = base_channels * self.expansion

        self.conv1 = nn.Conv2d(in_channels, base_channels, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(base_channels)
        self.conv2 = conv3x3(base_channels, base_channels, stride=stride)
        self.bn2 = nn.BatchNorm2d(base_channels)
        self.conv3 = nn.Conv2d(
            base_channels,
            expanded_channels,
            kernel_size=1,
            bias=False,
        )
        self.bn3 = nn.BatchNorm2d(expanded_channels)
        self.relu = nn.ReLU(inplace=True)

        if stride != 1 or in_channels != expanded_channels:
            self.shortcut = nn.Sequential(
                nn.Conv2d(
                    in_channels,
                    expanded_channels,
                    kernel_size=1,
                    stride=stride,
                    bias=False,
                ),
                nn.BatchNorm2d(expanded_channels),
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = self.shortcut(x)

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)
        out += identity
        out = self.relu(out)
        return out


class ResNet(nn.Module):
    def __init__(
        self,
        block: type[nn.Module],
        layers: list[int],
        num_classes: int = 10,
    ) -> None:
        super().__init__()
        self.in_channels = 16

        self.stem = nn.Sequential(
            conv3x3(3, 16),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
        )

        self.layer1 = self._make_layer(block, base_channels=16, blocks=layers[0], stride=1)
        self.layer2 = self._make_layer(block, base_channels=32, blocks=layers[1], stride=2)
        self.layer3 = self._make_layer(block, base_channels=64, blocks=layers[2], stride=2)
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Linear(64 * block.expansion, num_classes)

        self._initialize_weights()

    def _make_layer(
        self,
        block: type[nn.Module],
        base_channels: int,
        blocks: int,
        stride: int,
    ) -> nn.Sequential:
        layers = [block(self.in_channels, base_channels, stride=stride)]
        self.in_channels = base_channels * block.expansion

        for _ in range(1, blocks):
            layers.append(block(self.in_channels, base_channels, stride=1))

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


def resnet20(num_classes: int = 10) -> ResNet:
    return ResNet(BasicBlock, [3, 3, 3], num_classes=num_classes)