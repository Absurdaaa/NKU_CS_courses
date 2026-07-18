"""CTD-lite-R18: Complementary Trilateral Decoder on a ResNet-18 backbone.

Inspired by CTDNet (Zhao et al., "Rethinking Lightweight Salient Object
Detection via Network Depth-Width Tradeoff", 2023). Instead of stacking extra
modules onto a single decoder path (which overfits in the small-data ResNet-18
regime), the decoder is split into three function-specialised paths and then
aggregated:

  * **Semantic path**  -- "where is the object": global context (Scale-Adaptive
        Pooling) on the deepest feature, gives coarse localisation.
  * **Spatial path**   -- "the object body/structure": the top-down FPN decode.
  * **Boundary path**  -- "the edges": early fusion of a shallow and a deep
        feature, supervised by Sobel(GT).

  CAM (Cross Aggregation Module) gate-fuses the semantic and spatial features;
  BRM (Boundary Refinement Module) then sharpens the result with the boundary
  feature. This divides labour by function rather than adding raw capacity.

Output: dict with key ``pred`` (B x 1 x H x W logits) plus training-only side
heads (sem / sp / bnd) consumed by ``compute_loss``.
"""

import torch
from torch import nn
import torch.nn.functional as F

from model.c3net_r18 import CSCM
from model.common import ConvBNReLU, DecoderBlock, ResNet18Encoder
from model.loss import HybridLoss, SobelEdgeTarget, StructureLoss


class SAP(nn.Module):
    """Scale-Adaptive Pooling: lightweight multi-scale global context."""

    def __init__(self, in_channels, out_channels, scales=(1, 3, 5)):
        super().__init__()
        self.branches = nn.ModuleList([
            nn.Sequential(
                nn.AdaptiveAvgPool2d(s),
                nn.Conv2d(in_channels, out_channels, 1, bias=False),
                nn.BatchNorm2d(out_channels),
                nn.ReLU(inplace=True),
            )
            for s in scales
        ])
        self.fuse = ConvBNReLU(in_channels + out_channels * len(scales), out_channels)

    def forward(self, x):
        size = x.shape[-2:]
        feats = [x]
        for branch in self.branches:
            feats.append(F.interpolate(branch(x), size=size, mode="bilinear", align_corners=False))
        return self.fuse(torch.cat(feats, dim=1))


class CAM(nn.Module):
    """Cross Aggregation Module: gated fusion of semantic and spatial features."""

    def __init__(self, channels):
        super().__init__()
        self.gate = nn.Sequential(nn.Conv2d(channels * 2, channels, 1), nn.Sigmoid())
        self.fuse = ConvBNReLU(channels * 2, channels)

    def forward(self, semantic, spatial):
        if semantic.shape[-2:] != spatial.shape[-2:]:
            semantic = F.interpolate(semantic, size=spatial.shape[-2:], mode="bilinear", align_corners=False)
        gate = self.gate(torch.cat([semantic, spatial], dim=1))
        return self.fuse(torch.cat([semantic * gate, spatial], dim=1))

    def forward_collect(self, semantic, spatial):
        if semantic.shape[-2:] != spatial.shape[-2:]:
            semantic = F.interpolate(semantic, size=spatial.shape[-2:], mode="bilinear", align_corners=False)
        gate = self.gate(torch.cat([semantic, spatial], dim=1))
        fused = self.fuse(torch.cat([semantic * gate, spatial], dim=1))
        return fused, gate


class BRM(nn.Module):
    """Boundary Refinement Module: sharpen a feature with the boundary feature."""

    def __init__(self, channels):
        super().__init__()
        self.fuse = nn.Sequential(ConvBNReLU(channels * 2, channels), ConvBNReLU(channels, channels))

    def forward(self, feature, boundary):
        if boundary.shape[-2:] != feature.shape[-2:]:
            boundary = F.interpolate(boundary, size=feature.shape[-2:], mode="bilinear", align_corners=False)
        return feature + self.fuse(torch.cat([feature, boundary], dim=1))


class CTDNetR18(nn.Module):
    def __init__(
        self,
        pretrained=False,
        channels=64,
        use_semantic=True,
        use_boundary=True,
        use_cam=True,
        use_cscm=False,
        cscm_scales=(3, 7, 11),
        loss_type="structure",
        side_loss_weight=0.4,
        edge_loss_weight=0.3,
    ):
        super().__init__()
        c = channels
        self.use_semantic = use_semantic
        self.use_boundary = use_boundary
        self.use_cam = use_cam
        self.use_cscm = use_cscm
        self.loss_type = loss_type
        self.side_loss_weight = side_loss_weight
        self.edge_loss_weight = edge_loss_weight

        self.encoder = ResNet18Encoder(pretrained=pretrained)
        self.lat1 = ConvBNReLU(64, c, kernel_size=1, padding=0)    # c1 s4
        self.lat2 = ConvBNReLU(128, c, kernel_size=1, padding=0)   # c2 s8
        self.lat3 = ConvBNReLU(256, c, kernel_size=1, padding=0)   # c3 s16
        self.lat4 = ConvBNReLU(512, c, kernel_size=1, padding=0)   # c4 s32

        if use_semantic:
            self.sap = SAP(512, c)
            self.sem_head = nn.Conv2d(c, 1, kernel_size=1)
            if use_cam:
                self.cam = CAM(c)
            else:
                self.agg_fuse = ConvBNReLU(c * 2, c)

        # Spatial path: top-down FPN decode.
        self.dec3 = DecoderBlock(c, c, c)  # s32 -> s16
        self.dec2 = DecoderBlock(c, c, c)  # s16 -> s8
        self.dec1 = DecoderBlock(c, c, c)  # s8  -> s4
        self.sp_head = nn.Conv2d(c, 1, kernel_size=1)

        # Fusion: C3Net's Center-Surround Contrast Modulation in the spatial path
        # (the contrast prior that was C3Net's strongest single module).
        if use_cscm:
            self.cscm2 = CSCM(c, cscm_scales)
            self.cscm1 = CSCM(c, cscm_scales)

        if use_boundary:
            self.bnd_fuse = nn.Sequential(ConvBNReLU(c * 2, c), ConvBNReLU(c, c))
            self.bnd_head = nn.Conv2d(c, 1, kernel_size=1)
            self.brm = BRM(c)
            self.edge_target = SobelEdgeTarget()

        self.dec0 = DecoderBlock(c, 64, c)  # s4 -> s2 with c0
        self.head = nn.Sequential(ConvBNReLU(c, 32), nn.Conv2d(32, 1, kernel_size=1))

        self.structure_loss = StructureLoss()
        self.hybrid_loss = HybridLoss()

    def forward(self, x):
        input_size = x.shape[-2:]
        c0, c1, c2, c3, c4 = self.encoder(x)
        p1, p2, p3 = self.lat1(c1), self.lat2(c2), self.lat3(c3)

        # Semantic path (or plain projection of the top feature).
        if self.use_semantic:
            semantic = self.sap(c4)
            top = semantic
        else:
            semantic = None
            top = self.lat4(c4)

        # Spatial path (optionally enhanced by CSCM contrast modulation).
        d = self.dec3(top, p3)
        d = self.dec2(d, p2)
        if self.use_cscm:
            d = self.cscm2(d)
        spatial = self.dec1(d, p1)  # s4
        if self.use_cscm:
            spatial = self.cscm1(spatial)

        # Cross aggregation of semantic + spatial.
        if self.use_semantic:
            if self.use_cam:
                agg = self.cam(semantic, spatial)
            else:
                sem_up = F.interpolate(semantic, size=spatial.shape[-2:], mode="bilinear", align_corners=False)
                agg = self.agg_fuse(torch.cat([sem_up, spatial], dim=1))
        else:
            agg = spatial

        # Boundary path + refinement.
        boundary = None
        if self.use_boundary:
            high = F.interpolate(top, size=p1.shape[-2:], mode="bilinear", align_corners=False)
            boundary = self.bnd_fuse(torch.cat([p1, high], dim=1))  # s4
            agg = self.brm(agg, boundary)

        out = self.dec0(agg, c0)  # s2
        logits = F.interpolate(self.head(out), size=input_size, mode="bilinear", align_corners=False)
        outputs = {"pred": logits}

        if self.training:
            outputs["sp"] = F.interpolate(self.sp_head(spatial), size=input_size, mode="bilinear", align_corners=False)
            if self.use_semantic:
                outputs["sem"] = F.interpolate(self.sem_head(semantic), size=input_size, mode="bilinear", align_corners=False)
            if self.use_boundary:
                outputs["bnd"] = F.interpolate(self.bnd_head(boundary), size=input_size, mode="bilinear", align_corners=False)
        return outputs

    @torch.no_grad()
    def forward_collect(self, x):
        """Inference forward with intermediate maps for qualitative analysis."""
        self.eval()
        input_size = x.shape[-2:]
        c0, c1, c2, c3, c4 = self.encoder(x)
        p1, p2, p3 = self.lat1(c1), self.lat2(c2), self.lat3(c3)

        vis = {}
        if self.use_semantic:
            semantic = self.sap(c4)
            top = semantic
            vis["semantic_feat"] = semantic.mean(dim=1, keepdim=True)
            vis["semantic_pred"] = torch.sigmoid(self.sem_head(semantic))
        else:
            semantic = None
            top = self.lat4(c4)

        d = self.dec3(top, p3)
        d = self.dec2(d, p2)
        if self.use_cscm:
            d = self.cscm2(d)
        spatial = self.dec1(d, p1)
        if self.use_cscm:
            spatial = self.cscm1(spatial)
        vis["spatial_feat"] = spatial.mean(dim=1, keepdim=True)
        vis["spatial_pred"] = torch.sigmoid(self.sp_head(spatial))

        if self.use_semantic:
            if self.use_cam:
                agg, cam_gate = self.cam.forward_collect(semantic, spatial)
                vis["cam_gate"] = cam_gate
            else:
                sem_up = F.interpolate(semantic, size=spatial.shape[-2:], mode="bilinear", align_corners=False)
                agg = self.agg_fuse(torch.cat([sem_up, spatial], dim=1))
        else:
            agg = spatial

        boundary = None
        if self.use_boundary:
            high = F.interpolate(top, size=p1.shape[-2:], mode="bilinear", align_corners=False)
            boundary = self.bnd_fuse(torch.cat([p1, high], dim=1))
            vis["boundary_feat"] = boundary.mean(dim=1, keepdim=True)
            vis["boundary_pred"] = torch.sigmoid(self.bnd_head(boundary))
            agg = self.brm(agg, boundary)

        out = self.dec0(agg, c0)
        logits = self.head(out)
        vis["pred"] = torch.sigmoid(logits)
        vis["agg_feat"] = agg.mean(dim=1, keepdim=True)
        return {k: F.interpolate(v, size=input_size, mode="bilinear", align_corners=False) for k, v in vis.items()}

    def _pixel_loss(self, logits, mask):
        if self.loss_type == "structure":
            return self.structure_loss(logits, mask)
        if self.loss_type == "hybrid":
            return self.hybrid_loss(logits, mask)
        return F.binary_cross_entropy_with_logits(logits, mask)

    def compute_loss(self, outputs, mask):
        loss = self._pixel_loss(outputs["pred"], mask)
        for key in ("sem", "sp"):
            if key in outputs:
                loss = loss + self.side_loss_weight * self._pixel_loss(outputs[key], mask)
        if "bnd" in outputs:
            with torch.no_grad():
                edge_target = self.edge_target(mask)
            loss = loss + self.edge_loss_weight * F.binary_cross_entropy_with_logits(outputs["bnd"], edge_target)
        return loss


def build_model(
    num_classes=1,
    pretrained=False,
    channels=64,
    use_semantic=True,
    use_boundary=True,
    use_cam=True,
    use_cscm=False,
    cscm_scales=(3, 7, 11),
    loss_type="structure",
    side_loss_weight=0.4,
    edge_loss_weight=0.3,
):
    if num_classes != 1:
        raise ValueError("CTDNet-R18 only supports num_classes=1 for binary saliency maps.")
    return CTDNetR18(
        pretrained=pretrained,
        channels=channels,
        use_semantic=use_semantic,
        use_boundary=use_boundary,
        use_cam=use_cam,
        use_cscm=use_cscm,
        cscm_scales=cscm_scales,
        loss_type=loss_type,
        side_loss_weight=side_loss_weight,
        edge_loss_weight=edge_loss_weight,
    )
