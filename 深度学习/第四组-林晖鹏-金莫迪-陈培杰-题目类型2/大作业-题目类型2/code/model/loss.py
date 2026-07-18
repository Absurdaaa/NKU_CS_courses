"""Reusable losses and supervision targets."""

import torch
from torch import nn
import torch.nn.functional as F


class StructureLoss(nn.Module):
    def forward(self, logits, mask):
        weight = 1 + 5 * torch.abs(F.avg_pool2d(mask, kernel_size=31, stride=1, padding=15) - mask)
        bce = F.binary_cross_entropy_with_logits(logits, mask, reduction="none")
        wbce = (weight * bce).sum(dim=(2, 3)) / weight.sum(dim=(2, 3))
        prob = torch.sigmoid(logits)
        inter = ((prob * mask) * weight).sum(dim=(2, 3))
        union = ((prob + mask) * weight).sum(dim=(2, 3))
        wiou = 1 - (inter + 1) / (union - inter + 1)
        return (wbce + wiou).mean()


class HybridLoss(nn.Module):
    def __init__(self, bce_weight=1.0, iou_weight=1.0, ssim_weight=1.0):
        super().__init__()
        self.bce_weight = bce_weight
        self.iou_weight = iou_weight
        self.ssim_weight = ssim_weight

    def forward(self, logits, mask):
        prob = torch.sigmoid(logits)
        loss = logits.new_tensor(0.0)
        if self.bce_weight > 0:
            loss = loss + self.bce_weight * F.binary_cross_entropy_with_logits(logits, mask)
        if self.iou_weight > 0:
            inter = (prob * mask).sum(dim=(2, 3))
            union = (prob + mask - prob * mask).sum(dim=(2, 3))
            loss = loss + self.iou_weight * (1 - (inter + 1) / (union + 1)).mean()
        if self.ssim_weight > 0:
            loss = loss + self.ssim_weight * self._ssim_loss(prob, mask)
        return loss

    @staticmethod
    def _ssim_loss(pred, target):
        kernel_size = 11
        padding = kernel_size // 2
        c1 = 0.01**2
        c2 = 0.03**2
        mu_x = F.avg_pool2d(pred, kernel_size, stride=1, padding=padding)
        mu_y = F.avg_pool2d(target, kernel_size, stride=1, padding=padding)
        sigma_x = F.avg_pool2d(pred * pred, kernel_size, stride=1, padding=padding) - mu_x * mu_x
        sigma_y = F.avg_pool2d(target * target, kernel_size, stride=1, padding=padding) - mu_y * mu_y
        sigma_xy = F.avg_pool2d(pred * target, kernel_size, stride=1, padding=padding) - mu_x * mu_y
        numerator = (2 * mu_x * mu_y + c1) * (2 * sigma_xy + c2)
        denominator = (mu_x.pow(2) + mu_y.pow(2) + c1) * (sigma_x + sigma_y + c2)
        ssim = numerator / denominator.clamp_min(1e-6)
        return ((1 - ssim.clamp(-1, 1)) * 0.5).mean()


class SobelEdgeTarget(nn.Module):
    def __init__(self, eps=1e-6):
        super().__init__()
        kernel_x = torch.tensor(
            [[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]],
            dtype=torch.float32,
        ).view(1, 1, 3, 3)
        kernel_y = torch.tensor(
            [[-1.0, -2.0, -1.0], [0.0, 0.0, 0.0], [1.0, 2.0, 1.0]],
            dtype=torch.float32,
        ).view(1, 1, 3, 3)
        self.register_buffer("kernel_x", kernel_x)
        self.register_buffer("kernel_y", kernel_y)
        self.eps = eps

    def forward(self, mask):
        edge_x = F.conv2d(mask, self.kernel_x, padding=1)
        edge_y = F.conv2d(mask, self.kernel_y, padding=1)
        edge = torch.sqrt(edge_x.pow(2) + edge_y.pow(2) + self.eps)
        edge = edge / edge.amax(dim=(2, 3), keepdim=True).clamp_min(self.eps)
        return edge.clamp(0, 1)


class BodyDetailTarget(nn.Module):
    def __init__(self, detail_kernel=9):
        super().__init__()
        if detail_kernel < 3 or detail_kernel % 2 == 0:
            raise ValueError("detail_kernel must be an odd integer >= 3.")
        self.detail_kernel = detail_kernel

    def forward(self, mask):
        padding = self.detail_kernel // 2
        dilated = F.max_pool2d(mask, kernel_size=self.detail_kernel, stride=1, padding=padding)
        eroded = -F.max_pool2d(-mask, kernel_size=self.detail_kernel, stride=1, padding=padding)
        detail = (dilated - eroded).clamp(0, 1)
        body = eroded.clamp(0, 1)
        body_sum = body.flatten(1).sum(dim=1).view(-1, 1, 1, 1)
        body = torch.where(body_sum > 0, body, mask)
        return body, detail


class PSGLoss(nn.Module):
    """Morphological closing-based missing-region penalty.

    Reference: "Progressively Self-Guided Loss for Salient Object Detection", AAAI 2022.

    Idea: apply morphological closing to the prediction; regions that were background
    before but foreground after closing are "missing" — penalise those extra hard.
    """

    def __init__(self, kernel_size=15, weight=1.0):
        super().__init__()
        p = kernel_size // 2
        self.dilate = lambda x: F.max_pool2d(x, kernel_size, stride=1, padding=p)
        self.erode = lambda x: -F.max_pool2d(-x, kernel_size, stride=1, padding=p)
        self.weight = weight

    def forward(self, pred_logits, mask):
        """Return PSG loss value (scalar)."""
        prob = torch.sigmoid(pred_logits)
        closed = self.erode(self.dilate(prob))  # morphological closing
        missing = (closed > prob).float()        # 被遗漏的区域
        if missing.sum() < 1:
            return pred_logits.new_tensor(0.0)
        loss = F.binary_cross_entropy(prob * missing, mask * missing, reduction='mean')
        return self.weight * loss
