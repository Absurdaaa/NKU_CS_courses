#!/usr/bin/env python3
"""E2: visualize the CSCM contrast attention of a trained C3Net.

Loads a full-C3Net checkpoint, runs forward_collect on a few test images, and saves
a panel [image | GT | prediction | contrast attention (s4, s2)] so we can see that
the contrast module focuses on object-vs-background high-contrast boundaries.

Usage:
  python scripts/viz_cscm_attn.py --checkpoint runs/method_enh/trainval_seed_42/full_ref/best.pt \
      --split-file splits/trainval_seed_42.json --num 6 --out docs/figures/cscm_attention.png
"""
import argparse
from pathlib import Path

import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from datasets.ecssd import ECSSDDataset
from model import build_model

IM_MEAN = np.array([0.485, 0.456, 0.406])
IM_STD = np.array([0.229, 0.224, 0.225])


def denorm(t):
    img = t.permute(1, 2, 0).cpu().numpy() * IM_STD + IM_MEAN
    return np.clip(img, 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--data-root", default="data/ECSSD")
    ap.add_argument("--split-file", default="splits/trainval_seed_42.json")
    ap.add_argument("--split", default="test")
    ap.add_argument("--image-size", type=int, default=352)
    ap.add_argument("--num", type=int, default=6)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default="docs/figures/cscm_attention.png")
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

    cols = ["image", "GT", "prediction", "contrast s4", "contrast s2"]
    n = min(args.num, len(ds))
    fig, axes = plt.subplots(n, len(cols), figsize=(2.4 * len(cols), 2.4 * n))
    if n == 1:
        axes = axes[None, :]

    for i in range(n):
        image, mask, name = ds[i]
        with torch.no_grad():
            vis = model.forward_collect(image[None].to(args.device))
        panels = [
            denorm(image),
            mask[0].cpu().numpy(),
            vis["pred"][0, 0].cpu().numpy(),
            vis.get("contrast_s4", vis["pred"])[0, 0].cpu().numpy(),
            vis.get("contrast_s2", vis["pred"])[0, 0].cpu().numpy(),
        ]
        for j, (ax, p) in enumerate(zip(axes[i], panels)):
            if j == 0:
                ax.imshow(p)
            else:
                ax.imshow(p, cmap="magma" if j >= 3 else "gray", vmin=0, vmax=1)
            ax.set_xticks([]); ax.set_yticks([])
            if i == 0:
                ax.set_title(cols[j], fontsize=11)
        axes[i][0].set_ylabel(name, fontsize=8)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=130, bbox_inches="tight")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
