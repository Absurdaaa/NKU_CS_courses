"""Render CTD-lite qualitative visualizations with semantic/boundary internals."""

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


def to_np(tensor):
    return tensor.detach().cpu().float().numpy()


def build_ctd(device):
    model = build_model("ctdnet_r18", pretrained=False, loss_type="bce")
    return model.to(device).eval()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/ECSSD")
    parser.add_argument("--split-file", default="splits/trainval_seed_42.json")
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--num", type=int, default=6)
    parser.add_argument("--image-size", type=int, default=352)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out", default="runs/ctdnet_ablation/visuals_seed42")
    args = parser.parse_args()

    device = args.device if torch.cuda.is_available() else "cpu"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset = ECSSDDataset(
        args.data_root,
        split="test",
        image_size=args.image_size,
        augment=False,
        split_file=args.split_file,
    )
    model = build_ctd(device)
    load_state_dict_compat(model, load_checkpoint(args.ckpt, map_location=device)["model"])

    n = min(args.num, len(dataset))
    indices = [int(round(i * (len(dataset) - 1) / max(n - 1, 1))) for i in range(n)]
    panels = ["input", "GT", "semantic", "boundary", "CAM", "final"]

    for idx in indices:
        image, mask, name = dataset[idx]
        x = image.unsqueeze(0).to(device)
        vis = model.forward_collect(x)

        img_np = np.transpose(to_np(image), (1, 2, 0)).clip(0, 1)
        gt_np = to_np(mask)[0]
        sem = to_np(vis.get("semantic_pred", vis.get("semantic_feat")))[0, 0]
        bnd = to_np(vis.get("boundary_pred", vis.get("boundary_feat", torch.zeros_like(vis["pred"]))))[0, 0]
        cam = to_np(vis.get("cam_gate", vis.get("agg_feat")))[0, 0]
        pred = to_np(vis["pred"])[0, 0]

        data = {
            "input": (img_np, None),
            "GT": (gt_np, "gray"),
            "semantic": (sem, "gray"),
            "boundary": (bnd, "gray"),
            "CAM": (cam, "jet"),
            "final": (pred, "gray"),
        }
        fig, axes = plt.subplots(1, len(panels), figsize=(len(panels) * 2.2, 2.6))
        for ax, key in zip(axes, panels):
            arr, cmap = data[key]
            ax.imshow(arr, cmap=cmap, vmin=0, vmax=1) if cmap else ax.imshow(arr)
            ax.set_title(key, fontsize=9)
            ax.axis("off")
        fig.suptitle(name, fontsize=10)
        fig.tight_layout()
        fig.savefig(out_dir / f"{name}.png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        print(f"saved {out_dir / (name + '.png')}")

    print(f"DONE: {n} visualizations in {out_dir}")


if __name__ == "__main__":
    main()
