"""Render C3Net / UG-CSCM qualitative visualizations.

For a few ECSSD test images, lay out side by side:
  input | GT | base pred | full pred | uncertainty u | contrast attention | edge

The uncertainty and contrast panels make the UG-CSCM insight visible: contrast
is amplified exactly where the model is unsure (object boundaries).

Example:
  PYTHONPATH=. python scripts/visualize_c3net.py \
    --full-ckpt runs/c3net_ablation/trainval_seed_42/b4_ug/best.pt \
    --base-ckpt runs/c3net_ablation/trainval_seed_42/a0_base/best.pt \
    --num 6 --out runs/c3net_ablation/visuals
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from datasets.ecssd import ECSSDDataset
from model import build_model
from utils.io import load_checkpoint, load_state_dict_compat


def build_full(device):
    model = build_model(
        "c3net_r18", pretrained=False, use_context=True, use_edge=True,
        use_deep_supervision=True, use_cscm=True, cscm_gate="uncertainty", loss_type="bce",
    )
    return model.to(device).eval()


def build_base(device):
    model = build_model(
        "c3net_r18", pretrained=False, use_context=False, use_edge=False,
        use_deep_supervision=False, use_cscm=False, loss_type="bce",
    )
    return model.to(device).eval()


def to_np(t):
    return t.detach().cpu().float().numpy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/ECSSD")
    parser.add_argument("--split-file", default="splits/trainval_seed_42.json")
    parser.add_argument("--full-ckpt", required=True)
    parser.add_argument("--base-ckpt", default=None)
    parser.add_argument("--num", type=int, default=6)
    parser.add_argument("--image-size", type=int, default=352)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out", default="runs/c3net_ablation/visuals")
    args = parser.parse_args()

    device = args.device if torch.cuda.is_available() else "cpu"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset = ECSSDDataset(args.data_root, split="test", image_size=args.image_size,
                           augment=False, split_file=args.split_file)

    full = build_full(device)
    load_state_dict_compat(full, load_checkpoint(args.full_ckpt, map_location=device)["model"])
    base = None
    if args.base_ckpt:
        base = build_base(device)
        load_state_dict_compat(base, load_checkpoint(args.base_ckpt, map_location=device)["model"])

    # Spread sample indices across the test set for variety.
    n = min(args.num, len(dataset))
    indices = [int(round(i * (len(dataset) - 1) / max(n - 1, 1))) for i in range(n)]

    panels = ["input", "GT", "base", "full", "uncertainty", "contrast", "edge"]
    for idx in indices:
        image, mask, name = dataset[idx]
        x = image.unsqueeze(0).to(device)
        vis = full.forward_collect(x)

        img_np = np.transpose(to_np(image), (1, 2, 0)).clip(0, 1)
        gt_np = to_np(mask)[0]
        full_pred = to_np(vis["pred"])[0, 0]
        unc = to_np(vis["uncertainty"])[0, 0] if "uncertainty" in vis else np.zeros_like(gt_np)
        contrast = to_np(vis.get("contrast_s2", vis.get("contrast_s4")))[0, 0] if any(k.startswith("contrast") for k in vis) else np.zeros_like(gt_np)
        edge = to_np(vis["edge"])[0, 0] if "edge" in vis else np.zeros_like(gt_np)
        base_pred = np.zeros_like(gt_np)
        if base is not None:
            base_pred = to_np(torch.sigmoid(base(x)["pred"]))[0, 0]

        data = {
            "input": (img_np, None), "GT": (gt_np, "gray"), "base": (base_pred, "gray"),
            "full": (full_pred, "gray"), "uncertainty": (unc, "jet"),
            "contrast": (contrast, "jet"), "edge": (edge, "gray"),
        }
        fig, axes = plt.subplots(1, len(panels), figsize=(len(panels) * 2.2, 2.6))
        for ax, key in zip(axes, panels):
            arr, cmap = data[key]
            ax.imshow(arr, cmap=cmap, vmin=0, vmax=1) if cmap else ax.imshow(arr)
            ax.set_title(key, fontsize=9)
            ax.axis("off")
        fig.suptitle(f"{name}", fontsize=10)
        fig.tight_layout()
        fig.savefig(out_dir / f"{name}.png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"saved {out_dir / (name + '.png')}")

    print(f"DONE: {n} visualizations in {out_dir}")


if __name__ == "__main__":
    main()
