"""DSS-R18: Deeply Supervised Salient Object Detection with ResNet-18.

Reference: Hou et al., "Deeply Supervised Salient Object Detection with Short
Connections", CVPR 2017.

Paper architecture:
  VGG-16 → 5 side outputs (1×1 conv on each stage) → short connections
  (ALL higher-level sides → deconv → concat → 1×1 conv) → final fusion
  (concat 5 refined sides → 1×1 conv → 1)

Adapted to ResNet-18 encoder (c0..c4), otherwise faithful to paper.
"""

import torch
from torch import nn
import torch.nn.functional as F

from model.common import ResNet18Encoder


# ---------------------------------------------------------------------------
#  Building blocks
# ---------------------------------------------------------------------------

class SideOutput(nn.Module):
    """1×1 conv → 1 channel (paper: "a 1×1 convolutional layer with 1 channel")."""

    def __init__(self, in_channels):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, 1, 1)

    def forward(self, x):
        return self.conv(x)


class ShortConnection(nn.Module):
    """Paper short connection: upsample ALL higher-level sides, concat, 1×1 conv.

    For a side at stage i with downsample factor s_i, receives sides from all
    higher stages j>i at downsample factor s_j. Each higher side is upsampled
    by factor s_j / s_i via ConvTranspose2d, then all concatenated and fused.
    """

    def __init__(self, num_higher, upsample_ratios):
        super().__init__()
        self.upsample_ratios = upsample_ratios
        self.deconvs = nn.ModuleList([
            nn.ConvTranspose2d(1, 1, ratio * 2, stride=ratio,
                               padding=ratio // 2)
            for ratio in upsample_ratios
        ])
        # concat: 1 (self) + num_higher → 1 channel
        self.fuse = nn.Conv2d(1 + num_higher, 1, 1)

    def forward(self, x, higher_sides):
        to_cat = [x]
        for deconv, side in zip(self.deconvs, higher_sides):
            to_cat.append(deconv(side))
        return self.fuse(torch.cat(to_cat, dim=1))


# ---------------------------------------------------------------------------
#  DSS-R18 main model
# ---------------------------------------------------------------------------

class DSSR18(nn.Module):
    """Deeply Supervised Salient Object Detection with ResNet-18.

    Paper structure:
      - 5 side outputs (1×1 conv on c0..c4)
      - Short connections: each side receives ALL higher-level sides
      - Final fusion: concat all 5 refined sides → 1×1 conv → 1
      - Loss: BCE on all 6 outputs, equal weight

    Returns dict:
        pred    – final fused output (1×1 conv on 5 concat sides) ← main
        side0..side4 – short-connection-refined side outputs
    """

    # Backbone channels & downsample factors (relative to input)
    ENC_CH = [64, 64, 128, 256, 512]
    SCALES = [2, 4, 8, 16, 32]

    def __init__(self, pretrained=False):
        super().__init__()
        self.encoder = ResNet18Encoder(pretrained=pretrained)

        # Side outputs: 1×1 conv → 1 channel (paper style)
        self.sides = nn.ModuleList([
            SideOutput(ch) for ch in self.ENC_CH
        ])

        # Short connections: each level receives ALL higher-level sides
        self.short_conns = nn.ModuleList()
        for i in range(len(self.SCALES)):
            num_higher = len(self.SCALES) - i - 1
            if num_higher > 0:
                ratios = [self.SCALES[j] // self.SCALES[i]
                          for j in range(i + 1, len(self.SCALES))]
            else:
                ratios = []
            self.short_conns.append(ShortConnection(num_higher, ratios))

        # Final fusion: concat 5 refined sides → 1×1 conv → 1
        self.fuse = nn.Conv2d(5, 1, 1)

    def forward(self, x):
        input_size = x.shape[2:]
        c0, c1, c2, c3, c4 = self.encoder(x)
        features = [c0, c1, c2, c3, c4]

        # Raw side predictions (all at their native resolution)
        raw = [side(f) for side, f in zip(self.sides, features)]

        # Short connections (bottom-up: refine side i using sides i+1..4)
        refined = []
        for i in range(len(self.SCALES)):
            if i < len(self.SCALES) - 1:
                higher = raw[i + 1:]  # ALL higher-level sides
            else:
                higher = []
            r = self.short_conns[i](raw[i], higher)
            # Upsample to input size for side supervision
            if r.shape[2:] != input_size:
                r = F.interpolate(r, size=input_size, mode='bilinear',
                                  align_corners=False)
            refined.append(r)

        # Final fusion: concat all 5 refined sides → 1×1 conv → 1
        fused = self.fuse(torch.cat(refined, dim=1))

        return {
            "pred": fused,
            "side0": refined[0], "side1": refined[1],
            "side2": refined[2], "side3": refined[3], "side4": refined[4],
        }

    def compute_loss(self, outputs, mask):
        """Paper: BCE on fused + all 5 sides, equal weight (1.0 each)."""
        loss = F.binary_cross_entropy_with_logits(outputs["pred"], mask)
        for k in range(5):
            loss = loss + F.binary_cross_entropy_with_logits(
                outputs[f"side{k}"], mask)
        return loss


def build_model(num_classes=1, pretrained=False):
    if num_classes != 1:
        raise ValueError("DSS-R18 only supports num_classes=1.")
    return DSSR18(pretrained=pretrained)
