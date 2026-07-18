"""Structured-output ResNet-18 baseline."""

import torch.nn.functional as F
from torch import nn

from model.common import ConvBNReLU, DecoderBlock, ResNet18Encoder


class ResNet18(nn.Module):
    def __init__(self, pretrained=False):
        super().__init__()
        self.encoder = ResNet18Encoder(pretrained=pretrained)
        self.top = ConvBNReLU(512, 256)
        self.decode3 = DecoderBlock(256, 256, 256)
        self.decode2 = DecoderBlock(256, 128, 128)
        self.decode1 = DecoderBlock(128, 64, 64)
        self.decode0 = DecoderBlock(64, 64, 64)
        self.head = nn.Sequential(ConvBNReLU(64, 32), nn.Conv2d(32, 1, kernel_size=1))

    def forward(self, x):
        input_size = x.shape[-2:]
        c0, c1, c2, c3, c4 = self.encoder(x)
        y = self.top(c4)
        y = self.decode3(y, c3)
        y = self.decode2(y, c2)
        y = self.decode1(y, c1)
        y = self.decode0(y, c0)
        logits = F.interpolate(self.head(y), size=input_size, mode="bilinear", align_corners=False)
        return {"pred": logits}


def build_model(num_classes=1, pretrained=False):
    if num_classes != 1:
        raise ValueError("This baseline only supports num_classes=1 for binary saliency maps.")
    return ResNet18(pretrained=pretrained)
