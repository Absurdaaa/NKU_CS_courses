"""EGNet-R18: Edge Guidance Network with ResNet-18 backbone.

Reference: Zhao et al., "EGNet: Edge Guidance Network for Salient Object
Detection", ICCV 2019.

Matches cpj/EGNet/model.py architecture exactly.
"""

import torch
from torch import nn
import torch.nn.functional as F

from model.common import ResNet18Encoder


# ---------------------------------------------------------------------------
#  Building blocks
# ---------------------------------------------------------------------------

class Conv3Block(nn.Module):
    """Two consecutive Conv+BN+ReLU blocks (bias=True like cpj/EGNet)."""

    def __init__(self, in_channels, out_channels, kernel_size):
        super().__init__()
        p = kernel_size // 2
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size, padding=p),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size, padding=p),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.conv(x)


class MergeLayer1(nn.Module):
    """Fuse x1 into x2: project x1→x2_c, element-wise add, Conv3Block.

    Used as the basic block for both PSFEM and NLSEM in cpj/EGNet.
    """

    def __init__(self, x1_channels, x2_channels, kernel_size):
        super().__init__()
        self.pre_process = nn.Sequential(
            nn.Conv2d(x1_channels, x2_channels, 1),
            nn.BatchNorm2d(x2_channels),
            nn.ReLU(inplace=True),
        )
        self.conv = Conv3Block(x2_channels, x2_channels, kernel_size)

    def forward(self, x1, x2):
        x1 = self.pre_process(x1)
        if x1.shape[2:] != x2.shape[2:]:
            x1 = F.interpolate(x1, size=x2.shape[2:], mode='bilinear',
                               align_corners=False)
        return self.conv(x1 + x2)


class PSFEM(nn.Module):
    """Progressive Scale Feature Enhancement Module.

    x1 (high-level) fused into x2 (low-level), producing mask side output.
    """

    def __init__(self, x1_channels, x2_channels, kernel_size):
        super().__init__()
        self.merge = MergeLayer1(x1_channels, x2_channels, kernel_size)
        self.mask_head = nn.Conv2d(x2_channels, 1, 3, padding=1)

    def forward(self, x1, x2):
        f = self.merge(x1, x2)
        mask = self.mask_head(f)
        return f, mask


class NLSEM(nn.Module):
    """Non-Local Saliency Edge Module. Same structure as PSFEM."""

    def __init__(self, x1_channels, x2_channels, kernel_size):
        super().__init__()
        self.merge = MergeLayer1(x1_channels, x2_channels, kernel_size)
        self.mask_head = nn.Conv2d(x2_channels, 1, 3, padding=1)

    def forward(self, x1, x2):
        f = self.merge(x1, x2)
        mask = self.mask_head(f)
        return f, mask


class O2OGM(nn.Module):
    """One-to-One Guidance Module: project edge→sal_c, add to saliency feature."""

    def __init__(self, x1_channels, x2_channels):
        super().__init__()
        self.pre_process = nn.Sequential(
            nn.Conv2d(x1_channels, x2_channels, 1),
            nn.BatchNorm2d(x2_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x1, x2):
        x1 = self.pre_process(x1)
        if x1.shape[2:] != x2.shape[2:]:
            x1 = F.interpolate(x1, size=x2.shape[2:], mode='bilinear',
                               align_corners=False)
        return x1 + x2


# ---------------------------------------------------------------------------
#  EGNet-R18 main model
# ---------------------------------------------------------------------------

class EGNetR18(nn.Module):
    """EGNet with ResNet-18 backbone.

    Matches cpj/EGNet/model.py architecture line-for-line.

    Returns dict:
        pred       – final fused saliency logits                ← main
        edge       – edge mask logits (from NLSEM)
        sal1..sal4 – O2OGM-refined saliency masks (4 scales)
        psfem1..psfem3 – PSFEM side outputs
    """

    def __init__(self, pretrained=False):
        super().__init__()
        self.encoder = ResNet18Encoder(pretrained=pretrained)

        # Top processing: c4 → f4
        self.top = Conv3Block(512, 512, kernel_size=7)

        # PSFEM chain (top-down saliency pyramid)
        self.psfem3 = PSFEM(512, 256, kernel_size=5)
        self.psfem2 = PSFEM(256, 128, kernel_size=3)
        self.psfem1 = PSFEM(128, 64, kernel_size=3)

        # NLSEM: edge path (f4 + f1 → edge)
        self.nlsem = NLSEM(512, 64, kernel_size=3)

        # O2OGM: edge feature → guide saliency at each scale
        self.o2ogm4 = O2OGM(64, 512)
        self.o2ogm3 = O2OGM(64, 256)
        self.o2ogm2 = O2OGM(64, 128)
        self.o2ogm1 = O2OGM(64, 64)

        # Final convolution blocks per scale
        self.last_conv4 = Conv3Block(512, 512, kernel_size=7)
        self.last_conv3 = Conv3Block(256, 256, kernel_size=5)
        self.last_conv2 = Conv3Block(128, 128, kernel_size=3)
        self.last_conv1 = Conv3Block(64, 64, kernel_size=3)

        # Mask heads
        self.mask_head4 = nn.Conv2d(512, 1, 3, padding=1)
        self.mask_head3 = nn.Conv2d(256, 1, 3, padding=1)
        self.mask_head2 = nn.Conv2d(128, 1, 3, padding=1)
        self.mask_head1 = nn.Conv2d(64, 1, 3, padding=1)

        # Final fusion: concat 4 masks → 1 mask (1x1 conv)
        self.last_merge = nn.Sequential(nn.Conv2d(4, 1, 1))

    def forward(self, x):
        input_size = x.shape[2:]
        c0, c1, c2, c3, c4 = self.encoder(x)

        # --- Saliency pyramid (PSFEM) ---
        f4 = self.top(c4)
        f3, mask3_psfem = self.psfem3(f4, c3)
        f2, mask2_psfem = self.psfem2(f3, c2)
        f1, mask1_psfem = self.psfem1(f2, c1)

        # --- Edge path (NLSEM) ---
        F_E, edge_mask = self.nlsem(f4, f1)

        # --- Edge-guided refinement (O2OGM) ---
        f_fused4 = self.o2ogm4(F_E, f4)
        f_fused3 = self.o2ogm3(F_E, f3)
        f_fused2 = self.o2ogm2(F_E, f2)
        f_fused1 = self.o2ogm1(F_E, f1)

        # --- Multi-scale saliency masks ---
        mask4 = self.mask_head4(self.last_conv4(f_fused4))
        mask3 = self.mask_head3(self.last_conv3(f_fused3))
        mask2 = self.mask_head2(self.last_conv2(f_fused2))
        mask1 = self.mask_head1(self.last_conv1(f_fused1))

        # --- Final fusion ---
        m4u = F.interpolate(mask4, size=mask1.shape[2:], mode='bilinear',
                            align_corners=False)
        m3u = F.interpolate(mask3, size=mask1.shape[2:], mode='bilinear',
                            align_corners=False)
        m2u = F.interpolate(mask2, size=mask1.shape[2:], mode='bilinear',
                            align_corners=False)
        final = self.last_merge(torch.cat([mask1, m2u, m3u, m4u], dim=1))
        final = F.interpolate(final, size=input_size, mode='bilinear',
                              align_corners=False)

        return {
            "pred": final,
            "edge": F.interpolate(edge_mask, size=input_size, mode='bilinear',
                                  align_corners=False),
            "sal1": mask1, "sal2": mask2, "sal3": mask3, "sal4": mask4,
            "psfem1": mask1_psfem, "psfem2": mask2_psfem,
            "psfem3": mask3_psfem,
        }

    @staticmethod
    def _extract_edge(mask, kernel_size=3):
        """Edge GT via morphological dilation - erosion (matches cpj/EGNet)."""
        p = kernel_size // 2
        d = F.max_pool2d(mask, kernel_size, stride=1, padding=p)
        e = -F.max_pool2d(-mask, kernel_size, stride=1, padding=p)
        return ((d - e) > 0.5).float()

    def compute_loss(self, outputs, mask):
        """All BCE terms, equal weight (matches cpj/EGNet/train.py).

        Multi-scale outputs are matched to their native resolution mask.
        """
        edge_gt = self._extract_edge(mask)
        loss = F.binary_cross_entropy_with_logits(outputs["pred"], mask)
        # edge is already upsampled to input_size in forward
        loss = loss + F.binary_cross_entropy_with_logits(outputs["edge"], edge_gt)
        for k in range(1, 5):
            s = outputs[f"sal{k}"]
            m = F.interpolate(mask, size=s.shape[2:], mode='bilinear',
                              align_corners=False) if s.shape[2:] != mask.shape[2:] else mask
            loss = loss + F.binary_cross_entropy_with_logits(s, m)
        for k in range(1, 4):
            s = outputs[f"psfem{k}"]
            m = F.interpolate(mask, size=s.shape[2:], mode='bilinear',
                              align_corners=False) if s.shape[2:] != mask.shape[2:] else mask
            loss = loss + F.binary_cross_entropy_with_logits(s, m)
        return loss


def build_model(num_classes=1, pretrained=False):
    if num_classes != 1:
        raise ValueError("EGNet-R18 only supports num_classes=1.")
    return EGNetR18(pretrained=pretrained)
