"""PFA-R18: Pyramid Feature Attention Network with ResNet-18.

Reference: Zhao et al., "Pyramid Feature Attention Network for Saliency
Detection", CVPR 2019.

Architecture (adapted from VGG-16 to ResNet-18):
  ResNet-18 encoder (c1..c5)
  → CFE (Context Feature Extraction) on c3/c4/c5 with dilated 1,3,5,7
  → Channel Attention on fused deep context
  → Spatial Attention (asymmetric strip convs) gates shallow features
  → Concat shallow+deep → head → output

Loss: EdgeHoldLoss = 0.7 × BCE(pos_weight=1.12) + 0.3 × Laplacian edge BCE
"""

import torch
from torch import nn
import torch.nn.functional as F

from model.common import ResNet18Encoder


# ===========================================================================
#  CFE – Context Feature Extraction (dilated conv branches 1,3,5,7)
# ===========================================================================

class CFE(nn.Module):
    """Multi-scale dilated context extraction (4 branches, dilation 1/3/5/7)."""

    def __init__(self, in_c, out_c=32):
        super().__init__()
        self.b0 = nn.Conv2d(in_c, out_c, 1, bias=False)
        self.b1 = nn.Conv2d(in_c, out_c, 3, padding=3, dilation=3, bias=False)
        self.b2 = nn.Conv2d(in_c, out_c, 3, padding=5, dilation=5, bias=False)
        self.b3 = nn.Conv2d(in_c, out_c, 3, padding=7, dilation=7, bias=False)
        out_total = out_c * 4
        self.fuse = nn.Sequential(
            nn.Conv2d(out_total, out_total, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_total),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        feats = [self.b0(x), self.b1(x), self.b2(x), self.b3(x)]
        return self.fuse(torch.cat(feats, dim=1))


# ===========================================================================
#  Channel Attention (CA) – squeeze-and-excitation
# ===========================================================================

class ChannelAttention(nn.Module):
    def __init__(self, channels):
        super().__init__()
        mid = max(channels // 4, 4)
        self.gate = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(channels, mid, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, channels, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return x * self.gate(x)


# ===========================================================================
#  Spatial Attention (SA) – asymmetric strip convolutions
# ===========================================================================

class SpatialAttention(nn.Module):
    """PFAN spatial attention: asymmetric strip convs (k=9) → single-channel gate."""

    def __init__(self, in_c, k=9):
        super().__init__()
        mid = in_c // 2
        self.path1 = nn.Sequential(
            nn.Conv2d(in_c, mid, (1, k), padding=(0, k // 2), bias=False),
            nn.BatchNorm2d(mid),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, 1, (k, 1), padding=(k // 2, 0), bias=False),
        )
        self.path2 = nn.Sequential(
            nn.Conv2d(in_c, mid, (k, 1), padding=(k // 2, 0), bias=False),
            nn.BatchNorm2d(mid),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, 1, (1, k), padding=(0, k // 2), bias=False),
        )

    def forward(self, x):
        attn = torch.sigmoid(self.path1(x) + self.path2(x))
        return x * attn


# ===========================================================================
#  EdgeHoldLoss
# ===========================================================================

class EdgeHoldLoss(nn.Module):
    """0.7 × BCE(pos_weight=1.12) + 0.3 × Laplacian edge BCE."""

    def __init__(self, saliency_pos=1.12, saliency_weight=0.7, edge_weight=0.3):
        super().__init__()
        laplace = torch.tensor(
            [[-1., -1., -1.], [-1., 8., -1.], [-1., -1., -1.]],
            dtype=torch.float32).view(1, 1, 3, 3)
        self.register_buffer("laplace", laplace)
        self.saliency_pos = torch.tensor(saliency_pos)
        self.s_w = saliency_weight
        self.e_w = edge_weight

    def _laplace_edge(self, x):
        edge = F.conv2d(x, self.laplace, padding=1)
        return torch.relu(torch.tanh(edge))

    def forward(self, logits, mask):
        prob = torch.sigmoid(logits)
        # Saliency loss
        sal_loss = F.binary_cross_entropy_with_logits(
            logits, mask, pos_weight=self.saliency_pos)
        # Edge loss
        target_edge = self._laplace_edge(mask)
        pred_edge = self._laplace_edge(prob).clamp(1e-6, 1 - 1e-6)
        pred_edge_logits = torch.log(pred_edge / (1 - pred_edge))
        edge_loss = F.binary_cross_entropy_with_logits(pred_edge_logits, target_edge)
        return self.s_w * sal_loss + self.e_w * edge_loss


# ===========================================================================
#  PFA-R18 main model
# ===========================================================================

class PFAR18(nn.Module):
    """Pyramid Feature Attention Network with ResNet-18.

    Returns dict with key ``pred`` (B×1×H×W logits).
    """

    def __init__(self, pretrained=False):
        super().__init__()
        self.encoder = ResNet18Encoder(pretrained=pretrained)

        # Shallow feature projections
        self.c1_proj = nn.Sequential(
            nn.Conv2d(64, 64, 3, padding=1, bias=False),
            nn.BatchNorm2d(64), nn.ReLU(inplace=True))
        self.c2_proj = nn.Sequential(
            nn.Conv2d(64, 64, 3, padding=1, bias=False),
            nn.BatchNorm2d(64), nn.ReLU(inplace=True))

        # CFE on deep layers (c3,c4,c5)
        self.c3_cfe = CFE(128, 32)   # 128 → 128
        self.c4_cfe = CFE(256, 32)   # 256 → 128
        self.c5_cfe = CFE(512, 32)   # 512 → 128

        # Channel attention on fused deep features (128×3=384)
        self.channel_attn = ChannelAttention(384)
        self.c345_proj = nn.Sequential(
            nn.Conv2d(384, 64, 1), nn.BatchNorm2d(64), nn.ReLU(inplace=True))

        # Shallow fusion + spatial attention
        self.c12_proj = nn.Sequential(
            nn.Conv2d(128, 64, 3, padding=1, bias=False),
            nn.BatchNorm2d(64), nn.ReLU(inplace=True))
        self.spatial_attn = SpatialAttention(64, k=9)

        # Head
        self.head = nn.Conv2d(128, 1, 3, padding=1)

        # Loss
        self.loss_fn = EdgeHoldLoss()

    def forward(self, x):
        input_size = x.shape[2:]
        c1, c2, c3, c4, c5 = self.encoder(x)

        # Shallow features
        c1 = self.c1_proj(c1)   # s2, 64
        c2 = self.c2_proj(c2)   # s4, 64

        # Deep context (CFE) → align to c3 spatial size (s8)
        c3_cfe = self.c3_cfe(c3)                                       # s8, 128
        c4_cfe = F.interpolate(self.c4_cfe(c4), size=c3_cfe.shape[2:],
                                mode='bilinear', align_corners=False)  # s8, 128
        c5_cfe = F.interpolate(self.c5_cfe(c5), size=c3_cfe.shape[2:],
                                mode='bilinear', align_corners=False)  # s8, 128

        # Fuse deep → channel attention → project
        c345 = torch.cat([c3_cfe, c4_cfe, c5_cfe], dim=1)  # 384 ch
        c345 = self.channel_attn(c345)
        c345 = self.c345_proj(c345)                          # 64 ch
        c345 = F.interpolate(c345, size=c1.shape[2:],
                             mode='bilinear', align_corners=False)

        # Shallow fusion → spatial attention from deep context
        c2 = F.interpolate(c2, size=c1.shape[2:],
                           mode='bilinear', align_corners=False)
        c12 = self.c12_proj(torch.cat([c1, c2], dim=1))      # 64 ch
        c12 = self.spatial_attn(c345) * c12                   # deep-attended shallow

        # Final fusion + prediction
        logits = self.head(torch.cat([c12, c345], dim=1))     # 128 → 1
        logits = F.interpolate(logits, size=input_size,
                               mode='bilinear', align_corners=False)
        return {"pred": logits}

    def compute_loss(self, outputs, mask):
        return self.loss_fn(outputs["pred"], mask)


def build_model(num_classes=1, pretrained=False):
    if num_classes != 1:
        raise ValueError("PFA-R18 only supports num_classes=1.")
    return PFAR18(pretrained=pretrained)
