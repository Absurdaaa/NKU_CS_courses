"""C3Net-R18 with CA-ASPP context in place of PPM.

Compared with PPM, CA-ASPP uses parallel atrous convolutions to capture
multi-scale semantics without collapsing all context into pooled bins. A
lightweight contrast-aware gate then re-weights the fused context so strong
center-surround responses are emphasised before decoding.
"""

import torch
from torch import nn
import torch.nn.functional as F

from model.common import ConvBNReLU, DecoderBlock, ResNet18Encoder
from model.loss import BodyDetailTarget, HybridLoss, SobelEdgeTarget, StructureLoss


# ---------------------------------------------------------------------------
#  Context -- Contrast-Aware ASPP
# ---------------------------------------------------------------------------

class _ASPPBranch(nn.Module):
    def __init__(self, in_channels, out_channels, dilation):
        super().__init__()
        if dilation == 1:
            kernel_size = 1
            padding = 0
        else:
            kernel_size = 3
            padding = dilation
        self.block = nn.Sequential(
            nn.Conv2d(
                in_channels,
                out_channels,
                kernel_size=kernel_size,
                padding=padding,
                dilation=dilation,
                bias=False,
            ),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class CA_ASPP(nn.Module):
    """Atrous multi-scale context with a contrast-aware spatial gate.

    PPM aggregates only pooled global bins. CA-ASPP keeps richer local semantics
    via parallel dilated convolutions (1/3/5/7) plus image-level pooling, then
    uses a small gate driven by both the input feature and fused context to
    amplify salient spatial contrast:

        out = context * (1 + sigmoid(gate))
    """

    def __init__(self, in_channels=512, out_channels=256, dilations=(1, 3, 5, 7)):
        super().__init__()
        branch_ch = out_channels // 4
        self.branches = nn.ModuleList([
            _ASPPBranch(in_channels, branch_ch, d) for d in dilations
        ])
        self.image_pool = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(in_channels, branch_ch, kernel_size=1, bias=False),
            nn.BatchNorm2d(branch_ch),
            nn.ReLU(inplace=True),
        )
        fused_channels = branch_ch * (len(dilations) + 1)
        self.project = ConvBNReLU(fused_channels, out_channels)
        self.input_proj = ConvBNReLU(in_channels, out_channels, kernel_size=1, padding=0)
        hidden = max(out_channels // 4, 32)
        self.gate = nn.Sequential(
            nn.Conv2d(out_channels * 2, hidden, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(hidden),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, 1, kernel_size=1),
        )
    def forward(self, x):
        size = x.shape[-2:]
        feats = [branch(x) for branch in self.branches]
        feats.append(F.interpolate(self.image_pool(x), size=size, mode="bilinear", align_corners=False))
        context = self.project(torch.cat(feats, dim=1))
        gate = torch.sigmoid(self.gate(torch.cat([self.input_proj(x), context], dim=1)))
        return context * (1 + gate)


# ---------------------------------------------------------------------------
#  Contrast -- Center-Surround Contrast Modulation (the special module)
# ---------------------------------------------------------------------------

class CSCM(nn.Module):
    """Center-Surround Contrast Modulation.

    For each radius ``r`` compute a center-surround contrast response and use the
    multi-scale bank to enhance the feature. The contrast prior (saliency = local
    center-vs-surround contrast) is made explicit instead of being left for the
    decoder to discover implicitly.

    Variants (for the special-module ablation / Plan B):
        variant="diff": ``d_r = f - avg_pool_r(f)`` -- a Mexican-hat /
            Difference-of-Gaussians response.
        variant="norm": ``d_r = (f - mu_r) / sqrt(var_r + eps)`` -- local
            contrast (divisive) normalization, i.e. a local z-score. Motivated by
            V1 divisive normalization (Carandini & Heeger, 2012) and Local
            Contrast Normalization (Jarrett et al., ICCV 2009); the response is
            invariant to absolute feature magnitude, giving a purer signal.

    Modes:
        mode="gate": spatial attention ``A=sigmoid(conv(bank))``; modulate as
            ``f * (1 + gamma*A)`` (residual gating) or ``f * A`` (pure gating).
        mode="inject": project the contrast bank back as a residual feature,
            ``f + gamma * proj(bank)`` -- richer than a single-channel gate (B1).
    """

    def __init__(self, channels, scales=(3, 7, 11), residual=True,
                 variant="diff", mode="gate", gamma=1.0, eps=1e-2, fixed=False,
                 learn_surround=False):
        super().__init__()
        self.scales = tuple(scales)
        self.residual = residual
        self.variant = variant
        self.mode = mode
        self.gamma = gamma
        self.eps = eps
        self.fixed = fixed
        self.learn_surround = learn_surround
        bank_ch = channels * len(self.scales)
        if learn_surround:
            self.surround = nn.ModuleList([
                nn.Conv2d(channels, channels, r, padding=r // 2, groups=channels, bias=False)
                for r in self.scales])
            for conv, r in zip(self.surround, self.scales):
                nn.init.constant_(conv.weight, 1.0 / (r * r))
        if mode == "inject":
            self.proj = ConvBNReLU(bank_ch, channels)
        elif fixed:
            self.fixed_scale = nn.Parameter(torch.tensor(4.0))
            self.fixed_bias = nn.Parameter(torch.tensor(0.0))
        else:
            hidden = max(channels // 4, 16)
            self.attn = nn.Sequential(
                nn.Conv2d(bank_ch, hidden, 3, padding=1, bias=False),
                nn.BatchNorm2d(hidden),
                nn.ReLU(inplace=True),
                nn.Conv2d(hidden, 1, 1),
            )

    def _contrast(self, f, r, surround=None):
        mu = surround(f) if surround is not None else F.avg_pool2d(f, kernel_size=r, stride=1, padding=r // 2)
        if self.variant == "norm":
            mu2 = F.avg_pool2d(f * f, kernel_size=r, stride=1, padding=r // 2)
            var = (mu2 - mu * mu).clamp_min(0.0)
            return (f - mu) / torch.sqrt(var + self.eps)
        return f - mu

    def forward(self, f, gate=None, return_attn=False):
        if self.learn_surround:
            bank = torch.cat([self._contrast(f, r, self.surround[i]) for i, r in enumerate(self.scales)], dim=1)
        else:
            bank = torch.cat([self._contrast(f, r) for r in self.scales], dim=1)
        if self.mode == "inject":
            injected = self.proj(bank)
            if gate is not None:
                injected = injected * gate
            out = f + self.gamma * injected
            return (out, gate if gate is not None else None) if return_attn else out
        if self.fixed:
            mag = bank.abs().mean(dim=1, keepdim=True)
            mu = mag.mean(dim=(2, 3), keepdim=True)
            sd = mag.std(dim=(2, 3), keepdim=True) + self.eps
            attn = torch.sigmoid(self.fixed_scale * (mag - mu) / sd + self.fixed_bias)
        else:
            attn = torch.sigmoid(self.attn(bank))
        if gate is not None:
            attn = attn * gate
        out = f * (1 + self.gamma * attn) if self.residual else f * attn
        return (out, attn) if return_attn else out


class C3NetR18(nn.Module):
    def __init__(
        self,
        pretrained=False,
        use_context=True,
        use_edge=True,
        use_deep_supervision=True,
        use_cscm=True,
        cscm_scales=(3, 7, 11),
        cscm_residual=True,
        cscm_variant="diff",
        cscm_mode="gate",
        cscm_gamma=1.0,
        cscm_gate="none",
        cscm_fixed=False,
        cscm_sup_weight=0.0,
        use_cscm_skip=False,
        use_cscm_d3=False,
        cscm_learn_surround=False,
        coarse_loss_weight=0.4,
        loss_type="structure",
        edge_loss_weight=0.3,
        side_loss_weight=0.4,
        use_body_detail=False,
        detail_kernel=9,
        body_loss_weight=0.4,
        detail_loss_weight=0.4,
        freq_loss_weight=0.0,
    ):
        super().__init__()
        self.use_context = use_context
        self.use_edge = use_edge
        self.use_deep_supervision = use_deep_supervision
        self.use_cscm = use_cscm
        self.cscm_gate = cscm_gate
        self.cscm_sup_weight = cscm_sup_weight
        self.use_cscm_skip = use_cscm_skip
        self.use_cscm_d3 = use_cscm_d3
        self.coarse_loss_weight = coarse_loss_weight
        self.loss_type = loss_type
        self.edge_loss_weight = edge_loss_weight
        self.side_loss_weight = side_loss_weight
        self.use_body_detail = use_body_detail
        self.body_loss_weight = body_loss_weight
        self.detail_loss_weight = detail_loss_weight
        self.freq_loss_weight = freq_loss_weight

        self.encoder = ResNet18Encoder(pretrained=pretrained)
        self.top = CA_ASPP(512, 256) if use_context else ConvBNReLU(512, 256)
        self.decode3 = DecoderBlock(256, 256, 256)
        self.decode2 = DecoderBlock(256, 128, 128)
        self.decode1 = DecoderBlock(128, 64, 64)
        self.decode0 = DecoderBlock(64, 64, 64)

        if use_cscm:
            cscm_kw = dict(scales=cscm_scales, residual=cscm_residual,
                           variant=cscm_variant, mode=cscm_mode, gamma=cscm_gamma,
                           fixed=cscm_fixed, learn_surround=cscm_learn_surround)
            self.cscm2 = CSCM(128, **cscm_kw)
            self.cscm1 = CSCM(64, **cscm_kw)
            self.cscm0 = CSCM(64, **cscm_kw)
            if use_cscm_d3:
                self.cscm3 = CSCM(256, **cscm_kw)
            if use_cscm_skip:
                self.cscm_skip3 = CSCM(256, **cscm_kw)
                self.cscm_skip2 = CSCM(128, **cscm_kw)
                self.cscm_skip1 = CSCM(64, **cscm_kw)

        if cscm_gate == "uncertainty":
            self.coarse_head = nn.Sequential(ConvBNReLU(256, 64), nn.Conv2d(64, 1, kernel_size=1))

        self.head = nn.Sequential(ConvBNReLU(64, 32), nn.Conv2d(32, 1, kernel_size=1))

        if use_deep_supervision:
            self.side3 = nn.Conv2d(256, 1, kernel_size=1)
            self.side2 = nn.Conv2d(128, 1, kernel_size=1)
            self.side1 = nn.Conv2d(64, 1, kernel_size=1)

        if use_edge:
            self.edge_head = nn.Sequential(ConvBNReLU(64, 32), nn.Conv2d(32, 1, kernel_size=1))
            self.edge_target = SobelEdgeTarget()

        if cscm_sup_weight > 0:
            self.cscm_sup_target = SobelEdgeTarget()

        if use_body_detail:
            self.body_head = nn.Sequential(ConvBNReLU(64, 32), nn.Conv2d(32, 1, kernel_size=1))
            self.detail_head = nn.Sequential(ConvBNReLU(64, 32), nn.Conv2d(32, 1, kernel_size=1))
            self.body_detail_target = BodyDetailTarget(detail_kernel=detail_kernel)

        self.structure_loss = StructureLoss()
        self.hybrid_loss = HybridLoss()

    def forward(self, x):
        input_size = x.shape[-2:]
        c0, c1, c2, c3, c4 = self.encoder(x)
        collect_attn = self.training and self.cscm_sup_weight > 0
        attns = []

        if self.use_cscm and self.use_cscm_skip:
            c3 = self._cscm(self.cscm_skip3, c3, None, attns, collect_attn)
            c2 = self._cscm(self.cscm_skip2, c2, None, attns, collect_attn)
            c1 = self._cscm(self.cscm_skip1, c1, None, attns, collect_attn)

        t = self.top(c4)
        d3 = self.decode3(t, c3)

        coarse_logits = None
        gate_map = None
        if self.cscm_gate == "uncertainty":
            coarse_logits = self.coarse_head(d3)
            coarse_prob = torch.sigmoid(coarse_logits).detach()
            gate_map = 1.0 - 2.0 * (coarse_prob - 0.5).abs()
        elif self.cscm_gate == "edge":
            gate_map = self._image_edge(x)

        if self.use_cscm and self.use_cscm_d3:
            d3 = self._cscm(self.cscm3, d3, self._resize_gate(gate_map, d3), attns, collect_attn)

        d2 = self.decode2(d3, c2)
        if self.use_cscm:
            d2 = self._cscm(self.cscm2, d2, self._resize_gate(gate_map, d2), attns, collect_attn)
        d1 = self.decode1(d2, c1)
        if self.use_cscm:
            d1 = self._cscm(self.cscm1, d1, self._resize_gate(gate_map, d1), attns, collect_attn)
        d0 = self.decode0(d1, c0)
        if self.use_cscm:
            d0 = self._cscm(self.cscm0, d0, self._resize_gate(gate_map, d0), attns, collect_attn)

        logits = F.interpolate(self.head(d0), size=input_size, mode="bilinear", align_corners=False)
        outputs = {"pred": logits}
        if collect_attn and attns:
            outputs["cscm_attn"] = attns
        if self.training and coarse_logits is not None:
            outputs["coarse"] = F.interpolate(coarse_logits, size=input_size, mode="bilinear", align_corners=False)
        if self.training and self.use_deep_supervision:
            outputs["side3"] = F.interpolate(self.side3(d3), size=input_size, mode="bilinear", align_corners=False)
            outputs["side2"] = F.interpolate(self.side2(d2), size=input_size, mode="bilinear", align_corners=False)
            outputs["side1"] = F.interpolate(self.side1(d1), size=input_size, mode="bilinear", align_corners=False)
        if self.training and self.use_edge:
            outputs["edge"] = F.interpolate(self.edge_head(d0), size=input_size, mode="bilinear", align_corners=False)
        if self.training and self.use_body_detail:
            outputs["body"] = F.interpolate(self.body_head(d0), size=input_size, mode="bilinear", align_corners=False)
            outputs["detail"] = F.interpolate(self.detail_head(d0), size=input_size, mode="bilinear", align_corners=False)
        return outputs

    @torch.no_grad()
    def forward_collect(self, x):
        self.eval()
        input_size = x.shape[-2:]
        c0, c1, c2, c3, c4 = self.encoder(x)
        t = self.top(c4)
        d3 = self.decode3(t, c3)

        vis = {}
        vis["top_s32"] = self._feature_map(t)
        vis["decode3_s16"] = self._feature_map(d3)
        uncertainty = None
        if self.cscm_gate == "uncertainty":
            coarse_prob = torch.sigmoid(self.coarse_head(d3))
            uncertainty = 1.0 - 2.0 * (coarse_prob - 0.5).abs()
            vis["coarse"] = coarse_prob
            vis["uncertainty"] = uncertainty

        d2 = self.decode2(d3, c2)
        if self.use_cscm:
            before = d2
            d2, a2 = self.cscm2(d2, self._resize_gate(uncertainty, d2), return_attn=True)
            vis["cscm_before_s8"] = self._feature_map(before)
            vis["cscm_after_s8"] = self._feature_map(d2)
            vis["cscm_delta_s8"] = self._feature_map(d2 - before)
            if a2 is not None:
                vis["contrast_s8"] = a2
        vis["decode2_s8"] = self._feature_map(d2)
        d1 = self.decode1(d2, c1)
        if self.use_cscm:
            before = d1
            d1, a1 = self.cscm1(d1, self._resize_gate(uncertainty, d1), return_attn=True)
            vis["cscm_before_s4"] = self._feature_map(before)
            vis["cscm_after_s4"] = self._feature_map(d1)
            vis["cscm_delta_s4"] = self._feature_map(d1 - before)
            if a1 is not None:
                vis["contrast_s4"] = a1
        vis["decode1_s4"] = self._feature_map(d1)
        d0 = self.decode0(d1, c0)
        if self.use_cscm:
            before = d0
            d0, a0 = self.cscm0(d0, self._resize_gate(uncertainty, d0), return_attn=True)
            vis["cscm_before_s2"] = self._feature_map(before)
            vis["cscm_after_s2"] = self._feature_map(d0)
            vis["cscm_delta_s2"] = self._feature_map(d0 - before)
            if a0 is not None:
                vis["contrast_s2"] = a0
        vis["decode0_s2"] = self._feature_map(d0)

        vis["pred"] = torch.sigmoid(self.head(d0))
        if self.use_deep_supervision:
            vis["side3"] = torch.sigmoid(self.side3(d3))
            vis["side2"] = torch.sigmoid(self.side2(d2))
            vis["side1"] = torch.sigmoid(self.side1(d1))
        if self.use_edge:
            vis["edge"] = torch.sigmoid(self.edge_head(d0))
        return {k: F.interpolate(v, size=input_size, mode="bilinear", align_corners=False) for k, v in vis.items()}

    @staticmethod
    def _feature_map(feature):
        return feature.abs().mean(dim=1, keepdim=True)

    @staticmethod
    def _cscm(module, feat, gate, attns, collect):
        if collect:
            out, a = module(feat, gate, return_attn=True)
            if a is not None:
                attns.append(a)
            return out
        return module(feat, gate)

    @staticmethod
    def _image_edge(x):
        gray = x.mean(dim=1, keepdim=True)
        kx = torch.tensor([[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]],
                          dtype=x.dtype, device=x.device).view(1, 1, 3, 3)
        ky = kx.transpose(2, 3)
        gx = F.conv2d(gray, kx, padding=1)
        gy = F.conv2d(gray, ky, padding=1)
        mag = torch.sqrt(gx * gx + gy * gy + 1e-6)
        flat = mag.flatten(1)
        mn = flat.min(1)[0].view(-1, 1, 1, 1)
        mx = flat.max(1)[0].view(-1, 1, 1, 1)
        return (mag - mn) / (mx - mn + 1e-6)

    @staticmethod
    def _resize_gate(gate, feature):
        if gate is None:
            return None
        if gate.shape[-2:] == feature.shape[-2:]:
            return gate
        return F.interpolate(gate, size=feature.shape[-2:], mode="bilinear", align_corners=False)

    def _pixel_loss(self, logits, mask):
        if self.loss_type == "structure":
            return self.structure_loss(logits, mask)
        if self.loss_type == "hybrid":
            return self.hybrid_loss(logits, mask)
        return F.binary_cross_entropy_with_logits(logits, mask)

    def compute_loss(self, outputs, mask):
        loss = self._pixel_loss(outputs["pred"], mask)
        if "coarse" in outputs:
            loss = loss + self.coarse_loss_weight * self._pixel_loss(outputs["coarse"], mask)
        if self.use_deep_supervision:
            for key in ("side3", "side2", "side1"):
                if key in outputs:
                    loss = loss + self.side_loss_weight * self._pixel_loss(outputs[key], mask)
        if self.use_edge and "edge" in outputs:
            with torch.no_grad():
                edge_target = self.edge_target(mask)
            loss = loss + self.edge_loss_weight * F.binary_cross_entropy_with_logits(outputs["edge"], edge_target)
        if self.use_body_detail and "body" in outputs:
            with torch.no_grad():
                body_target, detail_target = self.body_detail_target(mask)
            loss = loss + self.body_loss_weight * F.binary_cross_entropy_with_logits(outputs["body"], body_target)
            loss = loss + self.detail_loss_weight * F.binary_cross_entropy_with_logits(outputs["detail"], detail_target)
        if self.cscm_sup_weight > 0 and "cscm_attn" in outputs:
            with torch.no_grad():
                contrast_target = self.cscm_sup_target(mask)
            sup = 0.0
            for a in outputs["cscm_attn"]:
                a_up = F.interpolate(a, size=mask.shape[-2:], mode="bilinear",
                                     align_corners=False).clamp(1e-6, 1 - 1e-6)
                sup = sup + F.binary_cross_entropy(a_up, contrast_target)
            loss = loss + self.cscm_sup_weight * sup / len(outputs["cscm_attn"])
        if self.freq_loss_weight > 0:
            prob = torch.sigmoid(outputs["pred"])
            pf = torch.fft.rfft2(prob, norm="ortho").abs()
            mf = torch.fft.rfft2(mask, norm="ortho").abs()
            loss = loss + self.freq_loss_weight * (pf - mf).abs().mean()
        return loss


def build_model(
    num_classes=1,
    pretrained=False,
    use_context=True,
    use_edge=True,
    use_deep_supervision=True,
    use_cscm=True,
    cscm_scales=(3, 7, 11),
    cscm_residual=True,
    cscm_variant="diff",
    cscm_mode="gate",
    cscm_gamma=1.0,
    cscm_gate="none",
    cscm_fixed=False,
    cscm_sup_weight=0.0,
    use_cscm_skip=False,
    use_cscm_d3=False,
    cscm_learn_surround=False,
    coarse_loss_weight=0.4,
    loss_type="structure",
    edge_loss_weight=0.3,
    side_loss_weight=0.4,
    use_body_detail=False,
    detail_kernel=9,
    body_loss_weight=0.4,
    detail_loss_weight=0.4,
    freq_loss_weight=0.0,
):
    if num_classes != 1:
        raise ValueError("C3Net-R18 only supports num_classes=1 for binary saliency maps.")
    return C3NetR18(
        pretrained=pretrained,
        use_context=use_context,
        use_edge=use_edge,
        use_deep_supervision=use_deep_supervision,
        use_cscm=use_cscm,
        cscm_scales=cscm_scales,
        cscm_residual=cscm_residual,
        cscm_variant=cscm_variant,
        cscm_mode=cscm_mode,
        cscm_gamma=cscm_gamma,
        cscm_gate=cscm_gate,
        cscm_fixed=cscm_fixed,
        cscm_sup_weight=cscm_sup_weight,
        use_cscm_skip=use_cscm_skip,
        use_cscm_d3=use_cscm_d3,
        cscm_learn_surround=cscm_learn_surround,
        coarse_loss_weight=coarse_loss_weight,
        loss_type=loss_type,
        edge_loss_weight=edge_loss_weight,
        side_loss_weight=side_loss_weight,
        use_body_detail=use_body_detail,
        detail_kernel=detail_kernel,
        body_loss_weight=body_loss_weight,
        detail_loss_weight=detail_loss_weight,
        freq_loss_weight=freq_loss_weight,
    )



