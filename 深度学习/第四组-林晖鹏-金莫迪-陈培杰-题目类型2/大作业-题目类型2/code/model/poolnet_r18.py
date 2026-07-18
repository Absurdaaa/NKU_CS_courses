"""PoolNet-R18: A Simple Pooling-Based Design with ResNet-18 backbone.

Reference: Liu et al., "A Simple Pooling-Based Design for Real-Time Salient
Object Detection", CVPR 2019.

Architecture:
  ResNet-18 → Convert (1x1) → GGM (PPM @ out5) → FAM (DeepPool × 5) → Score
"""

import torch
from torch import nn
import torch.nn.functional as F

from model.common import ResNet18Encoder


# ---------------------------------------------------------------------------
#  GGM – Global Guidance Module (Pyramid Pooling)
# ---------------------------------------------------------------------------

class GGM(nn.Module):
    """Pyramid Pooling Module on the top-level feature.

    Pools at scales [1, 3, 5], producing 512-channel global guidance.
    Side infos are projected to match backbone lateral sizes.
    """

    def __init__(self, in_channels=512, out_channels=512, pool_scales=(1, 3, 5)):
        super().__init__()
        self.ppm_pre = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 1, bias=False),
            nn.ReLU(inplace=True),
        )
        self.pools = nn.ModuleList([
            nn.Sequential(
                nn.AdaptiveAvgPool2d(s),
                nn.Conv2d(in_channels, out_channels, 1, bias=False),
                nn.ReLU(inplace=True),
            )
            for s in pool_scales
        ])
        pp_cat = (1 + len(pool_scales)) * out_channels
        self.ppm_cat = nn.Sequential(
            nn.Conv2d(pp_cat, out_channels, 3, padding=1, bias=False),
            nn.ReLU(inplace=True),
        )

        # Guidance projections: one per decoder level (matched to lateral sizes)
        # Original: [512, 256, 256, 128] projected at [out5, out4, out3, out2] sizes
        self.infos = nn.ModuleList([
            nn.Sequential(
                nn.Conv2d(out_channels, ch, 3, padding=1, bias=False),
                nn.ReLU(inplace=True),
            )
            for ch in (512, 256, 256, 128)
        ])

    def forward(self, x, lateral_sizes):
        """x: top feature, lateral_sizes: list of (H,W) for each info target."""
        x = self.ppm_pre(x)
        ppm_list = [x]
        for pool in self.pools:
            ppm_list.append(F.interpolate(pool(x), size=x.shape[2:],
                                          mode='bilinear', align_corners=False))
        xls = self.ppm_cat(torch.cat(ppm_list, dim=1))

        infos = []
        for k in range(len(self.infos)):
            target_size = lateral_sizes[len(self.infos) - 1 - k]
            infos.append(self.infos[k](F.interpolate(
                xls, size=target_size, mode='bilinear', align_corners=False)))
        return xls, infos


# ---------------------------------------------------------------------------
#  FAM – Feature Aggregation Module (DeepPool)
# ---------------------------------------------------------------------------

class FAM(nn.Module):
    """Feature Aggregation Module with multi-scale pooling + lateral fusion.

    Matching the paper design:
      1.  strided avg pool @ [2, 4, 8] → 3x3 conv → upsample → element-wise add
      2.  (optional) upsample 2× (aligns with next finer feature)
      3.  3x3 conv k→k_out
      4.  (optional) fuse with backbone lateral x2 + GGM info x3
         (spatial sizes auto-aligned)
    """

    def __init__(self, in_channels, out_channels, pool_sizes=(2, 4, 8),
                 need_x2=False, need_fuse=False):
        super().__init__()
        self.need_x2 = need_x2
        self.need_fuse = need_fuse
        self.pools = nn.ModuleList([nn.AvgPool2d(s, stride=s) for s in pool_sizes])
        self.convs = nn.ModuleList([
            nn.Conv2d(in_channels, in_channels, 3, padding=1, bias=False)
            for _ in pool_sizes
        ])
        self.relu = nn.ReLU(inplace=True)
        self.conv_sum = nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False)
        if need_fuse:
            self.conv_sum_c = nn.Conv2d(out_channels, out_channels, 3, padding=1,
                                        bias=False)

    def forward(self, x, x2=None, x3=None):
        x_size = x.shape[2:]
        out = x
        for pool, conv in zip(self.pools, self.convs):
            pooled = pool(x)
            out = out + F.interpolate(conv(pooled), size=x_size,
                                      mode='bilinear', align_corners=False)
        out = self.relu(out)

        if self.need_x2 and x2 is not None:
            out = F.interpolate(out, size=x2.shape[2:],
                                mode='bilinear', align_corners=False)

        out = self.relu(self.conv_sum(out))

        if self.need_fuse and x2 is not None and x3 is not None:
            tgt = out.shape[2:]
            if x2.shape[2:] != tgt:
                x2 = F.interpolate(x2, size=tgt, mode='bilinear',
                                   align_corners=False)
            if x3.shape[2:] != tgt:
                x3 = F.interpolate(x3, size=tgt, mode='bilinear',
                                   align_corners=False)
            out = self.relu(self.conv_sum_c(out + x2 + x3))

        return out


# ---------------------------------------------------------------------------
#  PoolNet-R18 main model
# ---------------------------------------------------------------------------

class PoolNetR18(nn.Module):
    """PoolNet with ResNet-18 backbone.

    Feature flow (spatial strides in parens):
      Encoder:  c0(s2,64)  c1(s4,64)  c2(s8,128)  c3(s16,256)  c4(s32,512)
      Convert:  r1(s2,128) r2(s4,256) r3(s8,256)  r4(s16,512)  r5(s32,512)
      Reversed: [r5, r4, r3, r2, r1]  (coarse → fine)

      GGM on r5(s32) → infos projected to [r4, r3, r2, r1] sizes:
        info[0]@s16(512)  info[1]@s8(256)  info[2]@s4(256)  info[3]@s2(128)

      FAM decoder:
        FAM[0](r5,          x2=r4, x3=info0)  s32→s16, 512→512
        FAM[1](512,         x2=r3, x3=info1)  s16→s8,  512→256
        FAM[2](256,         x2=r2, x3=info2)  s8→s4,   256→256
        FAM[3](256,         x2=r1, x3=info3)  s4→s2,   256→128
        FAM[4](128)                            s2→s2,   128→128

    Returns dict with key ``pred`` (B×1×H×W logits).
    """

    # FAM config: (in_c, out_c, need_x2, need_fuse)
    FAM_CFG = [
        (512, 512, True,  True),   # 0: r5@32 → up to r4@16 → 512, fuse r4+info0
        (512, 256, True,  True),   # 1: @16 → up to r3@8 → 256, fuse r3+info1
        (256, 256, True,  True),   # 2: @8 → up to r2@4 → 256, fuse r2+info2
        (256, 128, True,  True),   # 3: @4 → up to r1@2 → 128, fuse r1+info3
        (128, 128, False, False),  # 4: @2 → 128, no lateral
    ]

    SCORE_CH = 128

    def __init__(self, pretrained=False):
        super().__init__()
        self.encoder = ResNet18Encoder(pretrained=pretrained)

        # 1×1 projection for backbone features
        # c0(64)→128, c1(64)→256, c2(128)→256, c3(256)→512, c4(512)→512
        self.convert_c0 = nn.Sequential(
            nn.Conv2d(64, 128, 1, bias=False), nn.ReLU(inplace=True))
        self.convert_c1 = nn.Sequential(
            nn.Conv2d(64, 256, 1, bias=False), nn.ReLU(inplace=True))
        self.convert_c2 = nn.Sequential(
            nn.Conv2d(128, 256, 1, bias=False), nn.ReLU(inplace=True))
        self.convert_c3 = nn.Sequential(
            nn.Conv2d(256, 512, 1, bias=False), nn.ReLU(inplace=True))
        self.convert_c4 = nn.Sequential(
            nn.Conv2d(512, 512, 1, bias=False), nn.ReLU(inplace=True))

        # GGM on top-level (r5, 512 ch)
        self.ggm = GGM(in_channels=512)

        # FAM decoder
        self.fams = nn.ModuleList([
            FAM(in_c, out_c, need_x2=need_x2, need_fuse=need_fuse)
            for in_c, out_c, need_x2, need_fuse in self.FAM_CFG
        ])

        # Score head: 3×3 refine → 1×1 project
        self.score = nn.Sequential(
            nn.Conv2d(self.SCORE_CH, self.SCORE_CH, 3, padding=1, bias=True),
            nn.ReLU(inplace=True),
            nn.Conv2d(self.SCORE_CH, 1, 1, bias=True),
        )

    def forward(self, x):
        input_size = x.shape[2:]
        c0, c1, c2, c3, c4 = self.encoder(x)

        # Convert
        r1 = self.convert_c0(c0)   # s2, 128
        r2 = self.convert_c1(c1)   # s4, 256
        r3 = self.convert_c2(c2)   # s8, 256
        r4 = self.convert_c3(c3)   # s16, 512
        r5 = self.convert_c4(c4)   # s32, 512

        # GGM on r5, info sizes aligned to [r4, r3, r2, r1]
        lateral_sizes = [r.shape[2:] for r in (r1, r2, r3, r4)]
        _, infos = self.ggm(r5, lateral_sizes)

        # FAM decoder (top-down)
        d = self.fams[0](r5, r4, infos[0])        # s32→s16, 512→512
        d = self.fams[1](d, r3, infos[1])          # s16→s8,  512→256
        d = self.fams[2](d, r2, infos[2])          # s8→s4,   256→256
        d = self.fams[3](d, r1, infos[3])          # s4→s2,   256→128
        d = self.fams[4](d)                         # s2→s2,   128→128

        logits = self.score(d)
        logits = F.interpolate(logits, size=input_size, mode='bilinear',
                               align_corners=False)
        return {"pred": logits}


def build_model(num_classes=1, pretrained=False):
    if num_classes != 1:
        raise ValueError("PoolNet-R18 only supports num_classes=1.")
    return PoolNetR18(pretrained=pretrained)
