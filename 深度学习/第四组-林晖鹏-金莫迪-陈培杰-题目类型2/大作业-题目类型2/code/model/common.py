"""Reusable model building blocks."""

import torch
from torch import nn
import torch.nn.functional as F
from torchvision.models import resnet18


class ConvBNReLU(nn.Sequential):
    def __init__(self, in_channels, out_channels, kernel_size=3, padding=1):
        super().__init__(
            nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, padding=padding, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )


class ConvReLU(nn.Sequential):
    def __init__(self, in_channels, out_channels, kernel_size=1, padding=0):
        super().__init__(
            nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, padding=padding, bias=True),
            nn.ReLU(inplace=True),
        )


class ResNet18Encoder(nn.Module):
    def __init__(self, pretrained=False):
        super().__init__()
        backbone = resnet18(weights="DEFAULT" if pretrained else None)
        self.stem = nn.Sequential(backbone.conv1, backbone.bn1, backbone.relu)
        self.pool = backbone.maxpool
        self.layer1 = backbone.layer1
        self.layer2 = backbone.layer2
        self.layer3 = backbone.layer3
        self.layer4 = backbone.layer4

    def forward(self, x):
        c0 = self.stem(x)
        c1 = self.layer1(self.pool(c0))
        c2 = self.layer2(c1)
        c3 = self.layer3(c2)
        c4 = self.layer4(c3)
        return c0, c1, c2, c3, c4


class DecoderBlock(nn.Module):
    def __init__(self, in_channels, skip_channels, out_channels):
        super().__init__()
        self.fuse = ConvBNReLU(in_channels + skip_channels, out_channels)
        self.refine = ConvBNReLU(out_channels, out_channels)

    def forward(self, x, skip):
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        return self.refine(self.fuse(torch.cat([x, skip], dim=1)))


class GatedDecoderBlock(nn.Module):
    def __init__(self, in_channels, skip_channels, out_channels):
        super().__init__()
        self.skip_gate = nn.Sequential(
            nn.Conv2d(in_channels + skip_channels, skip_channels, kernel_size=1),
            nn.Sigmoid(),
        )
        self.fuse = ConvBNReLU(in_channels + skip_channels, out_channels)
        self.refine = ConvBNReLU(out_channels, out_channels)

    def forward(self, x, skip, use_gate=False):
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        if use_gate:
            skip = skip * self.skip_gate(torch.cat([x, skip], dim=1))
        return self.refine(self.fuse(torch.cat([x, skip], dim=1)))
