#!/usr/bin/env python3
"""E1: quantify that the CSCM attention concentrates on high-contrast GT boundaries.

Over the test set, for each image compute the CSCM contrast attention (contrast_s2,
upsampled to input res) and measure its alignment with the Sobel boundary of the GT:
  - Pearson correlation(attention, Sobel(GT))
  - mean attention on boundary pixels vs off-boundary pixels (and their ratio)
A high correlation / ratio supports the claim that the explicit contrast module is
attending to object-vs-background contrast edges, not arbitrary regions.

Usage:
  python scripts/analyze_contrast_corr.py --checkpoint runs/method_enh/trainval_seed_42/full_ref/best.pt \
      --split-file splits/trainval_seed_42.json
"""
import argparse

import numpy as np
import torch

from datasets.ecssd import ECSSDDataset
from model import build_model
from model.loss import SobelEdgeTarget


def pearson(a, b):
    a = a - a.mean(); b = b - b.mean()
    denom = (a.std() * b.std())
    return float((a * b).mean() / denom) if denom > 1e-8 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--data-root", default="data/ECSSD")
    ap.add_argument("--split-file", default="splits/trainval_seed_42.json")
    ap.add_argument("--split", default="test")
    ap.add_argument("--image-size", type=int, default=352)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--cscm-fixed", action="store_true")
    ap.add_argument("--cscm-skip", action="store_true")
    ap.add_argument("--cscm-d3", action="store_true")
    args = ap.parse_args()

    ds = ECSSDDataset(args.data_root, split=args.split, image_size=args.image_size,
                      augment=False, split_file=args.split_file)
    model = build_model("c3net_r18", pretrained=False, cscm_fixed=args.cscm_fixed,
                        use_cscm_skip=args.cscm_skip, use_cscm_d3=args.cscm_d3)
    ckpt = torch.load(args.checkpoint, map_location="cpu")
    model.load_state_dict(ckpt["model"] if "model" in ckpt else ckpt)
    model.to(args.device).eval()
    sobel = SobelEdgeTarget()

    n = len(ds) if args.limit <= 0 else min(args.limit, len(ds))
    corrs, ratios, on_b, off_b = [], [], [], []
    for i in range(n):
        image, mask, _ = ds[i]
        with torch.no_grad():
            vis = model.forward_collect(image[None].to(args.device))
            edge = sobel(mask[None].to(args.device))[0, 0].cpu().numpy()
        if "contrast_s2" not in vis:
            print("checkpoint has no CSCM attention (use_cscm off?)"); return
        attn = vis["contrast_s2"][0, 0].cpu().numpy()
        b = edge > 0.5
        corrs.append(pearson(attn.ravel(), edge.ravel()))
        if b.any() and (~b).any():
            mb, mo = attn[b].mean(), attn[~b].mean()
            on_b.append(float(mb)); off_b.append(float(mo))
            ratios.append(float(mb / (mo + 1e-6)))

    print(f"images={n}")
    print(f"Pearson(attention, Sobel-GT-boundary): mean={np.mean(corrs):.4f} (std {np.std(corrs):.4f})")
    print(f"attention on boundary={np.mean(on_b):.4f}  off boundary={np.mean(off_b):.4f}  "
          f"ratio={np.mean(ratios):.3f}x")
    print("Interpretation: positive correlation and ratio>1 mean the CSCM attention "
          "concentrates on high-contrast object boundaries, as the motivation predicts.")


if __name__ == "__main__":
    main()
