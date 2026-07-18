"""F3Net-R18: Fusion, Feedback and Focus Network with ResNet-18 backbone.

Reference: Wei et al., "F3Net: Fusion, Feedback and Focus for Salient Object
Detection", AAAI 2020.
"""

import torch
from torch import nn
import torch.nn.functional as F

from model.common import ResNet18Encoder
from model.loss import StructureLoss


# ---------------------------------------------------------------------------
#  Building blocks
# ---------------------------------------------------------------------------

class DepthwiseSeparableConv(nn.Sequential):
    def __init__(self, channels, dilation=1):
        super().__init__(
            nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation,
                      groups=channels, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )


class AttentionRefine(nn.Module):
    """Channel + spatial attention refinement for the enhanced variant."""

    def __init__(self, channels=64, reduction=8):
        super().__init__()
        mid = max(channels // reduction, 4)
        self.channel_gate = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(channels, mid, 1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, channels, 1, bias=False),
            nn.Sigmoid(),
        )
        self.spatial_gate = nn.Sequential(
            nn.Conv2d(2, 1, 7, padding=3, bias=False),
            nn.Sigmoid(),
        )
        self.out = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        x = x * self.channel_gate(x)
        avg = torch.mean(x, dim=1, keepdim=True)
        max_out, _ = torch.max(x, dim=1, keepdim=True)
        x = x * self.spatial_gate(torch.cat([avg, max_out], dim=1))
        return self.out(x) + x


class MultiScaleContext(nn.Module):
    """Multi-scale context with dilated depthwise convs + global pooling."""

    def __init__(self, channels=64):
        super().__init__()
        self.local = nn.Sequential(
            nn.Conv2d(channels, channels, 1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )
        self.dilated2 = DepthwiseSeparableConv(channels, dilation=2)
        self.dilated4 = DepthwiseSeparableConv(channels, dilation=4)
        self.global_pool = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(channels, channels, 1, bias=False),
            nn.ReLU(inplace=True),
        )
        self.fuse = nn.Sequential(
            nn.Conv2d(channels * 4, channels, 1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        gp = F.interpolate(self.global_pool(x), size=x.shape[2:],
                           mode='bilinear', align_corners=False)
        return self.fuse(torch.cat([self.local(x), self.dilated2(x),
                                    self.dilated4(x), gp], dim=1)) + x


# ---------------------------------------------------------------------------
#  CFM – Cross Feature Module (the "Fusion" component)
# ---------------------------------------------------------------------------

class CFM(nn.Module):
    """Cross Feature Module with element-wise multiplication fusion."""

    def __init__(self, channels=64):
        super().__init__()
        self.conv1h = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn1h = nn.BatchNorm2d(channels)
        self.conv2h = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn2h = nn.BatchNorm2d(channels)
        self.conv3h = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn3h = nn.BatchNorm2d(channels)
        self.conv4h = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn4h = nn.BatchNorm2d(channels)
        self.conv1v = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn1v = nn.BatchNorm2d(channels)
        self.conv2v = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn2v = nn.BatchNorm2d(channels)
        self.conv3v = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn3v = nn.BatchNorm2d(channels)
        self.conv4v = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn4v = nn.BatchNorm2d(channels)

    def forward(self, left, down):
        if down.shape[2:] != left.shape[2:]:
            down = F.interpolate(down, size=left.shape[2:], mode='bilinear',
                                 align_corners=False)
        out1h = F.relu(self.bn1h(self.conv1h(left)), inplace=True)
        out2h = F.relu(self.bn2h(self.conv2h(out1h)), inplace=True)
        out1v = F.relu(self.bn1v(self.conv1v(down)), inplace=True)
        out2v = F.relu(self.bn2v(self.conv2v(out1v)), inplace=True)
        fuse = out2h * out2v
        out3h = F.relu(self.bn3h(self.conv3h(fuse)), inplace=True) + out1h
        out4h = F.relu(self.bn4h(self.conv4h(out3h)), inplace=True)
        out3v = F.relu(self.bn3v(self.conv3v(fuse)), inplace=True) + out1v
        out4v = F.relu(self.bn4v(self.conv4v(out3v)), inplace=True)
        return out4h, out4v


# ---------------------------------------------------------------------------
#  Decoder – Cascaded Feedback Decoder
# ---------------------------------------------------------------------------

class Decoder(nn.Module):
    def __init__(self, channels=64):
        super().__init__()
        self.cfm45 = CFM(channels)
        self.cfm34 = CFM(channels)
        self.cfm23 = CFM(channels)

    def forward(self, out2h, out3h, out4h, out5v, fback=None):
        if fback is not None:
            refine5 = F.interpolate(fback, size=out5v.shape[2:], mode='bilinear',
                                    align_corners=False)
            refine4 = F.interpolate(fback, size=out4h.shape[2:], mode='bilinear',
                                    align_corners=False)
            refine3 = F.interpolate(fback, size=out3h.shape[2:], mode='bilinear',
                                    align_corners=False)
            refine2 = F.interpolate(fback, size=out2h.shape[2:], mode='bilinear',
                                    align_corners=False)
            out5v = out5v + refine5
            out4h, out4v = self.cfm45(out4h + refine4, out5v)
            out3h, out3v = self.cfm34(out3h + refine3, out4v)
            out2h, pred = self.cfm23(out2h + refine2, out3v)
        else:
            out4h, out4v = self.cfm45(out4h, out5v)
            out3h, out3v = self.cfm34(out3h, out4v)
            out2h, pred = self.cfm23(out2h, out3v)
        return out2h, out3h, out4h, out5v, pred


# ---------------------------------------------------------------------------
#  Enhanced loss helpers
# ---------------------------------------------------------------------------

def _boundary_map(tensor, kernel_size=5):
    """Morphological boundary (dilate - erode), matching F3Net paper / jmd."""
    pad = kernel_size // 2
    dilate = F.max_pool2d(tensor, kernel_size=kernel_size, stride=1, padding=pad)
    erode = -F.max_pool2d(-tensor, kernel_size=kernel_size, stride=1, padding=pad)
    return (dilate - erode).clamp(0, 1)


def _dice_loss(pred, mask):
    prob = torch.sigmoid(pred)
    inter = (prob * mask).sum(dim=(2, 3))
    union = prob.sum(dim=(2, 3)) + mask.sum(dim=(2, 3))
    return (1 - (2 * inter + 1) / (union + 1)).mean()


def _focal_loss(pred, mask, alpha=0.25, gamma=2.0):
    bce = F.binary_cross_entropy_with_logits(pred, mask, reduction='none')
    pt = torch.exp(-bce)
    alpha_t = alpha * mask + (1 - alpha) * (1 - mask)
    return (alpha_t * (1 - pt).pow(gamma) * bce).mean()


def _boundary_loss(pred, mask):
    pred_edge = _boundary_map(torch.sigmoid(pred))
    mask_edge = _boundary_map(mask)
    return F.l1_loss(pred_edge, mask_edge)


# ---------------------------------------------------------------------------
#  F3Net main model
# ---------------------------------------------------------------------------

class F3NetR18(nn.Module):
    """F3Net with ResNet-18 backbone.

    Returns dict with keys:
        pred   – second-pass (feedback-refined) prediction (B×1×H×W)  ← main
        pred1  – first-pass decoder prediction
        pred2  – alias for pred
        side2  – side output from decoder2, layer 2
        side3  – side output from decoder2, layer 3
        side4  – side output from decoder2, layer 4
        side5  – side output from decoder2, layer 5
    """

    # Loss weights:          pred1, pred2, side2, side3, side4, side5
    SIDE_WEIGHTS = (1.0, 1.0, 0.5, 0.25, 0.125, 0.0625)

    def __init__(self, variant='base', loss_profile='base', pretrained=False):
        super().__init__()
        if variant not in ('base', 'enhanced'):
            raise ValueError("variant must be 'base' or 'enhanced'")
        if loss_profile not in ('base', 'enhanced'):
            raise ValueError("loss_profile must be 'base' or 'enhanced'")
        self.variant = variant
        self.loss_profile = loss_profile

        # Shared encoder (from model/common.py)
        self.encoder = ResNet18Encoder(pretrained=pretrained)

        # Squeeze backbone features to 64 channels
        self.squeeze2 = nn.Sequential(
            nn.Conv2d(64, 64, 1), nn.BatchNorm2d(64), nn.ReLU(inplace=True))
        self.squeeze3 = nn.Sequential(
            nn.Conv2d(128, 64, 1), nn.BatchNorm2d(64), nn.ReLU(inplace=True))
        self.squeeze4 = nn.Sequential(
            nn.Conv2d(256, 64, 1), nn.BatchNorm2d(64), nn.ReLU(inplace=True))
        self.squeeze5 = nn.Sequential(
            nn.Conv2d(512, 64, 1), nn.BatchNorm2d(64), nn.ReLU(inplace=True))

        # Attention / context (enhanced variant only)
        if variant == 'enhanced':
            self.refine2 = AttentionRefine(64)
            self.refine3 = AttentionRefine(64)
            self.refine4 = AttentionRefine(64)
            self.refine5 = nn.Sequential(AttentionRefine(64), MultiScaleContext(64))

        # Dual decoder
        self.decoder1 = Decoder(64)
        self.decoder2 = Decoder(64)

        # Output heads
        self.linearp1 = nn.Conv2d(64, 1, 3, padding=1)
        self.linearp2 = nn.Conv2d(64, 1, 3, padding=1)
        self.linearr2 = nn.Conv2d(64, 1, 3, padding=1)
        self.linearr3 = nn.Conv2d(64, 1, 3, padding=1)
        self.linearr4 = nn.Conv2d(64, 1, 3, padding=1)
        self.linearr5 = nn.Conv2d(64, 1, 3, padding=1)

        self.structure_loss = StructureLoss()

        self.initialize()

    @staticmethod
    def _init_module(module):
        for m in module.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def initialize(self):
        # Keep torchvision-loaded encoder weights intact when pretrained=True.
        self._init_module(self.squeeze2)
        self._init_module(self.squeeze3)
        self._init_module(self.squeeze4)
        self._init_module(self.squeeze5)
        if self.variant == 'enhanced':
            self._init_module(self.refine2)
            self._init_module(self.refine3)
            self._init_module(self.refine4)
            self._init_module(self.refine5)
        self._init_module(self.decoder1)
        self._init_module(self.decoder2)
        self._init_module(self.linearp1)
        self._init_module(self.linearp2)
        self._init_module(self.linearr2)
        self._init_module(self.linearr3)
        self._init_module(self.linearr4)
        self._init_module(self.linearr5)

    def forward(self, x):
        input_size = x.shape[2:]
        c0, c1, c2, c3, c4 = self.encoder(x)
        out2h = self.squeeze2(c1)   #  64 ch
        out3h = self.squeeze3(c2)   # 128 -> 64
        out4h = self.squeeze4(c3)   # 256 -> 64
        out5v = self.squeeze5(c4)   # 512 -> 64

        if self.variant == 'enhanced':
            out2h = self.refine2(out2h)
            out3h = self.refine3(out3h)
            out4h = self.refine4(out4h)
            out5v = self.refine5(out5v)

        # Cascade: decoder1 → pred1, decoder2 (feedback from pred1) → pred2
        _, _, _, _, pred1 = self.decoder1(out2h, out3h, out4h, out5v)
        out2h2, out3h2, out4h2, out5v2, pred2 = self.decoder2(out2h, out3h, out4h, out5v, pred1)

        pred1 = F.interpolate(self.linearp1(pred1), size=input_size,
                              mode='bilinear', align_corners=False)
        pred2 = F.interpolate(self.linearp2(pred2), size=input_size,
                              mode='bilinear', align_corners=False)
        side2 = F.interpolate(self.linearr2(out2h2), size=input_size,
                              mode='bilinear', align_corners=False)
        side3 = F.interpolate(self.linearr3(out3h2), size=input_size,
                              mode='bilinear', align_corners=False)
        side4 = F.interpolate(self.linearr4(out4h2), size=input_size,
                              mode='bilinear', align_corners=False)
        side5 = F.interpolate(self.linearr5(out5v2), size=input_size,
                              mode='bilinear', align_corners=False)

        return {"pred": pred2, "pred1": pred1, "pred2": pred2,
                "side2": side2, "side3": side3, "side4": side4, "side5": side5}

    def compute_loss(self, outputs, mask):
        pred1 = outputs["pred1"]
        pred2 = outputs["pred2"]
        side2 = outputs["side2"]
        side3 = outputs["side3"]
        side4 = outputs["side4"]
        side5 = outputs["side5"]

        if self.loss_profile == 'enhanced':
            loss1u = (self.structure_loss(pred1, mask) +
                      _dice_loss(pred1, mask) * 0.5 +
                      _focal_loss(pred1, mask) * 0.25 +
                      _boundary_loss(pred1, mask) * 0.25)
            loss2u = (self.structure_loss(pred2, mask) +
                      _dice_loss(pred2, mask) * 0.5 +
                      _focal_loss(pred2, mask) * 0.25 +
                      _boundary_loss(pred2, mask) * 0.25)
        else:
            loss1u = self.structure_loss(pred1, mask)
            loss2u = self.structure_loss(pred2, mask)

        loss2r = self.structure_loss(side2, mask)
        loss3r = self.structure_loss(side3, mask)
        loss4r = self.structure_loss(side4, mask)
        loss5r = self.structure_loss(side5, mask)

        return (loss1u + loss2u) / 2 + loss2r / 2 + loss3r / 4 + loss4r / 8 + loss5r / 16


def build_model(num_classes=1, pretrained=False, variant='base', loss_profile='base'):
    if num_classes != 1:
        raise ValueError("F3Net-R18 only supports num_classes=1.")
    return F3NetR18(variant=variant, loss_profile=loss_profile, pretrained=pretrained)
