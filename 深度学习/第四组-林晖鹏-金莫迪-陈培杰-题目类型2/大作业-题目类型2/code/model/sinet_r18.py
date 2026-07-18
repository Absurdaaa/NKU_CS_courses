"""SINet-R18: Search & Identification Network with ResNet-18 dual-branch backbone.

Reference: Fan et al., "Camouflaged Object Detection", CVPR 2020.
Adapted for the basic framework with structured dict outputs.
"""

import math

import torch
from torch import nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
#  Dual-branch ResNet-18 backbone
# ---------------------------------------------------------------------------

class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super().__init__()
        self.conv1 = nn.Conv2d(inplanes, planes, 3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(planes, planes, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample

    def forward(self, x):
        residual = x
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        if self.downsample is not None:
            residual = self.downsample(x)
        out += residual
        out = self.relu(out)
        return out


class ResNet2Branch(nn.Module):
    """Dual-branch ResNet-18: layer1/layer2 shared, layer3/layer4 duplicated."""

    def __init__(self):
        super().__init__()
        self.inplanes = 64

        self.conv1 = nn.Conv2d(3, 64, 7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        self.layer1 = self._make_layer(BasicBlock, 64, 2)
        self.layer2 = self._make_layer(BasicBlock, 128, 2, stride=2)
        self.layer3_1 = self._make_layer(BasicBlock, 256, 2, stride=2)
        self.layer4_1 = self._make_layer(BasicBlock, 512, 2, stride=2)

        self.inplanes = 128
        self.layer3_2 = self._make_layer(BasicBlock, 256, 2, stride=2)
        self.layer4_2 = self._make_layer(BasicBlock, 512, 2, stride=2)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2.0 / n))
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion, 1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )
        layers = [block(self.inplanes, planes, stride, downsample)]
        self.inplanes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes))
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.relu(self.bn1(self.conv1(x)))
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x1 = self.layer4_1(self.layer3_1(x))
        x2 = self.layer4_2(self.layer3_2(x))
        return x1, x2


# ---------------------------------------------------------------------------
#  Search Attention (SA)
# ---------------------------------------------------------------------------

def _gaussian_kernel(kernlen=16, nsig=3):
    """Create a normalized 2D Gaussian kernel without scipy dependency."""
    interval = (2 * nsig + 1.0) / kernlen
    x = torch.linspace(-nsig - interval / 2.0, nsig + interval / 2.0, kernlen + 1)
    cdf = 0.5 * (1.0 + torch.erf(x / math.sqrt(2.0)))
    kern1d = cdf[1:] - cdf[:-1]
    # Use manual outer product for DataParallel compatibility
    kernel_raw = torch.sqrt(kern1d.unsqueeze(1) * kern1d.unsqueeze(0))
    return kernel_raw / kernel_raw.sum()


class SA(nn.Module):
    """Search Attention: Gaussian blur + min-max norm + hard attention gating."""

    def __init__(self):
        super().__init__()
        kernel = _gaussian_kernel(31, 4).view(1, 1, 31, 31).float()
        self.register_buffer("gaussian_kernel", kernel)

    @staticmethod
    def _min_max_norm(x):
        max_v = x.amax(dim=(2, 3), keepdim=True)
        min_v = x.amin(dim=(2, 3), keepdim=True)
        return (x - min_v) / (max_v - min_v + 1e-8)

    def forward(self, attention, x):
        soft_attention = F.conv2d(attention, self.gaussian_kernel, padding=15)
        soft_attention = self._min_max_norm(soft_attention)
        return torch.mul(x, soft_attention.max(attention))


# ---------------------------------------------------------------------------
#  BasicConv2d & RF (Receptive Field) block
# ---------------------------------------------------------------------------

class BasicConv2d(nn.Module):
    def __init__(self, in_planes, out_planes, kernel_size, stride=1,
                 padding=0, dilation=1):
        super().__init__()
        self.conv = nn.Conv2d(in_planes, out_planes, kernel_size=kernel_size,
                              stride=stride, padding=padding, dilation=dilation,
                              bias=False)
        self.bn = nn.BatchNorm2d(out_planes)

    def forward(self, x):
        return self.bn(self.conv(x))


class RF(nn.Module):
    """Receptive Field block with asymmetric conv branches."""

    def __init__(self, in_channel, out_channel):
        super().__init__()
        self.relu = nn.ReLU(inplace=True)
        self.branch0 = nn.Sequential(BasicConv2d(in_channel, out_channel, 1))
        self.branch1 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 3), padding=(0, 1)),
            BasicConv2d(out_channel, out_channel, kernel_size=(3, 1), padding=(1, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=3, dilation=3),
        )
        self.branch2 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 5), padding=(0, 2)),
            BasicConv2d(out_channel, out_channel, kernel_size=(5, 1), padding=(2, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=5, dilation=5),
        )
        self.branch3 = nn.Sequential(
            BasicConv2d(in_channel, out_channel, 1),
            BasicConv2d(out_channel, out_channel, kernel_size=(1, 7), padding=(0, 3)),
            BasicConv2d(out_channel, out_channel, kernel_size=(7, 1), padding=(3, 0)),
            BasicConv2d(out_channel, out_channel, 3, padding=7, dilation=7),
        )
        self.conv_cat = BasicConv2d(4 * out_channel, out_channel, 3, padding=1)
        self.conv_res = BasicConv2d(in_channel, out_channel, 1)

    def forward(self, x):
        x_cat = self.conv_cat(torch.cat([
            self.branch0(x), self.branch1(x), self.branch2(x), self.branch3(x),
        ], dim=1))
        return self.relu(x_cat + self.conv_res(x))


# ---------------------------------------------------------------------------
#  PDC – Partial Decoder Components
# ---------------------------------------------------------------------------

class PDC_SM(nn.Module):
    """PDC for Search Module (4 inputs)."""

    def __init__(self, channel):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
        self.conv_upsample1 = BasicConv2d(channel, channel, 3, padding=1)
        self.conv_upsample2 = BasicConv2d(channel, channel, 3, padding=1)
        self.conv_upsample3 = BasicConv2d(channel, channel, 3, padding=1)
        self.conv_upsample4 = BasicConv2d(channel, channel, 3, padding=1)
        self.conv_upsample5 = BasicConv2d(2 * channel, 2 * channel, 3, padding=1)
        self.conv_concat2 = BasicConv2d(2 * channel, 2 * channel, 3, padding=1)
        self.conv_concat3 = BasicConv2d(4 * channel, 4 * channel, 3, padding=1)
        self.conv4 = BasicConv2d(4 * channel, 4 * channel, 3, padding=1)
        self.conv5 = nn.Conv2d(4 * channel, 1, 1)

    def forward(self, x1, x2, x3, x4):
        x1_1 = x1
        x2_1 = self.conv_upsample1(self.upsample(x1)) * x2
        x3_1 = (self.conv_upsample2(self.upsample(self.upsample(x1))) *
                self.conv_upsample3(self.upsample(x2)) * x3)
        x2_2 = self.conv_concat2(torch.cat([x2_1, self.conv_upsample4(self.upsample(x1_1))], 1))
        x3_2 = self.conv_concat3(torch.cat([x3_1, self.conv_upsample5(self.upsample(x2_2)), x4], 1))
        return self.conv5(self.conv4(x3_2))


class PDC_IM(nn.Module):
    """PDC for Identification Module (3 inputs)."""

    def __init__(self, channel):
        super().__init__()
        self.upsample = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
        self.conv_upsample1 = BasicConv2d(channel, channel, 3, padding=1)
        self.conv_upsample2 = BasicConv2d(channel, channel, 3, padding=1)
        self.conv_upsample3 = BasicConv2d(channel, channel, 3, padding=1)
        self.conv_upsample4 = BasicConv2d(channel, channel, 3, padding=1)
        self.conv_upsample5 = BasicConv2d(2 * channel, 2 * channel, 3, padding=1)
        self.conv_concat2 = BasicConv2d(2 * channel, 2 * channel, 3, padding=1)
        self.conv_concat3 = BasicConv2d(3 * channel, 3 * channel, 3, padding=1)
        self.conv4 = BasicConv2d(3 * channel, 3 * channel, 3, padding=1)
        self.conv5 = nn.Conv2d(3 * channel, 1, 1)

    def forward(self, x1, x2, x3):
        x1_1 = x1
        x2_1 = self.conv_upsample1(self.upsample(x1)) * x2
        x3_1 = (self.conv_upsample2(self.upsample(self.upsample(x1))) *
                self.conv_upsample3(self.upsample(x2)) * x3)
        x2_2 = self.conv_concat2(torch.cat([x2_1, self.conv_upsample4(self.upsample(x1_1))], 1))
        x3_2 = self.conv_concat3(torch.cat([x3_1, self.conv_upsample5(self.upsample(x2_2))], 1))
        return self.conv5(self.conv4(x3_2))


# ---------------------------------------------------------------------------
#  SINet-R18 main model
# ---------------------------------------------------------------------------

class SINetR18(nn.Module):
    """SINet-R18: Search & Identification Network for salient / camouflaged object
    detection.

    Returns dict with keys:
        pred  – identification module output (B×1×H×W)  ← main
        sm    – search module output (B×1×H×W)
    """

    def __init__(self, channel=32, pretrained=True):
        super().__init__()
        self.resnet = ResNet2Branch()
        self.down_sample = nn.MaxPool2d(2, stride=2)
        self.rf_low_sm = RF(128, channel)
        self.rf2_sm = RF(896, channel)
        self.rf3_sm = RF(768, channel)
        self.rf4_sm = RF(512, channel)
        self.pdc_sm = PDC_SM(channel)
        self.rf2_im = RF(128, channel)
        self.rf3_im = RF(256, channel)
        self.rf4_im = RF(512, channel)
        self.pdc_im = PDC_IM(channel)
        self.upsample_2 = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
        self.upsample_8 = nn.Upsample(scale_factor=8, mode="bilinear", align_corners=True)
        self.search_attention = SA()

        if pretrained:
            self._init_from_torchvision()

    def _init_from_torchvision(self):
        """Load pretrained ResNet-18 weights, duplicating for dual branches."""
        from torchvision.models import ResNet18_Weights, resnet18
        try:
            pretrained_dict = resnet18(weights=ResNet18_Weights.DEFAULT).state_dict()
        except Exception:
            return  # skip if weights unavailable (e.g. offline)
        own_state = self.resnet.state_dict()
        all_params = {}
        for key in own_state:
            if key in pretrained_dict:
                all_params[key] = pretrained_dict[key]
            elif "_1" in key:
                name = key.replace("_1", "")
                if name in pretrained_dict:
                    all_params[key] = pretrained_dict[name]
            elif "_2" in key:
                name = key.replace("_2", "")
                if name in pretrained_dict:
                    all_params[key] = pretrained_dict[name]
        self.resnet.load_state_dict(all_params, strict=False)

    def forward(self, x):
        # --- Backbone ---
        x0 = self.resnet.relu(self.resnet.bn1(self.resnet.conv1(x)))
        x0 = self.resnet.maxpool(x0)
        x1 = self.resnet.layer1(x0)
        x2 = self.resnet.layer2(x1)

        # --- Search Module (SM) ---
        x01 = torch.cat([x0, x1], dim=1)
        x01_down = self.down_sample(x01)
        x01_sm_rf = self.rf_low_sm(x01_down)
        x2_sm = x2
        x3_sm = self.resnet.layer3_1(x2_sm)
        x4_sm = self.resnet.layer4_1(x3_sm)
        x2_sm_cat = torch.cat([x2_sm, self.upsample_2(x3_sm),
                               self.upsample_2(self.upsample_2(x4_sm))], dim=1)
        x3_sm_cat = torch.cat([x3_sm, self.upsample_2(x4_sm)], dim=1)
        camouflage_map_sm = self.pdc_sm(
            self.rf4_sm(x4_sm),
            self.rf3_sm(x3_sm_cat),
            self.rf2_sm(x2_sm_cat),
            x01_sm_rf,
        )

        # --- Identification Module (IM) ---
        x2_sa = self.search_attention(camouflage_map_sm.sigmoid(), x2)
        x3_im = self.resnet.layer3_2(x2_sa)
        x4_im = self.resnet.layer4_2(x3_im)
        camouflage_map_im = self.pdc_im(
            self.rf4_im(x4_im),
            self.rf3_im(x3_im),
            self.rf2_im(x2_sa),
        )

        return {"pred": self.upsample_8(camouflage_map_im),
                "sm": self.upsample_8(camouflage_map_sm)}

    def compute_loss(self, outputs, mask):
        loss_sm = F.binary_cross_entropy_with_logits(outputs["sm"], mask)
        loss_im = F.binary_cross_entropy_with_logits(outputs["pred"], mask)
        return loss_sm + loss_im


def build_model(num_classes=1, pretrained=True, channel=32):
    if num_classes != 1:
        raise ValueError("SINet-R18 only supports num_classes=1.")
    return SINetR18(channel=channel, pretrained=pretrained)
