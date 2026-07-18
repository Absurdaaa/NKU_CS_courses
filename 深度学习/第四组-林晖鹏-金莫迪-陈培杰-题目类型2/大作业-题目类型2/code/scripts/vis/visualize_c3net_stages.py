"""Render stage-by-stage C3Net feature visualizations for a few samples.

Panels:
  input | GT | top_s32 | decode3_s16 | decode2_s8 | decode1_s4 | decode0_s2 | pred
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


def build_model_full(device):
    model = build_model(
        "c3net_r18",
        pretrained=False,
        use_context=True,
        use_edge=True,
        use_deep_supervision=True,
        use_cscm=True,
        cscm_gate="none",
        loss_type="bce",
    )
    return model.to(device).eval()


def to_np(t):
    return t.detach().cpu().float().numpy()


def norm01(arr):
    arr = np.asarray(arr, dtype=np.float32)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi - lo < 1e-8:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def render_grid(rows, out_path):
    cols = ["input", "GT", "top_s32", "d3_s16", "d2_s8", "d1_s4", "d0_s2", "pred"]
    fig, axes = plt.subplots(len(rows), len(cols), figsize=(len(cols) * 2.1, len(rows) * 2.2))
    if len(rows) == 1:
        axes = np.expand_dims(axes, 0)
    for r, row in enumerate(rows):
        items = [
            (row["input"], None),
            (row["gt"], "gray"),
            (row["top_s32"], "magma"),
            (row["decode3_s16"], "magma"),
            (row["decode2_s8"], "magma"),
            (row["decode1_s4"], "magma"),
            (row["decode0_s2"], "magma"),
            (row["pred"], "gray"),
        ]
        for c, (arr, cmap) in enumerate(items):
            ax = axes[r, c]
            if cmap is None:
                ax.imshow(arr)
            else:
                ax.imshow(norm01(arr), cmap=cmap, vmin=0, vmax=1)
            if r == 0:
                ax.set_title(cols[c], fontsize=9)
            if c == 0:
                ax.set_ylabel(row["name"], fontsize=9)
            ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/ECSSD")
    parser.add_argument("--split-file", default="splits/trainval_seed_42.json")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--names", nargs="*", default=["0303", "0747", "0694"])
    parser.add_argument("--image-size", type=int, default=352)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out", default="runs/c3net_ablation/c3net_stages_seed42")
    args = parser.parse_args()

    device = args.device if torch.cuda.is_available() else "cpu"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset = ECSSDDataset(
        args.data_root,
        split=args.split,
        image_size=args.image_size,
        augment=False,
        split_file=args.split_file,
    )
    name_to_idx = {}
    for i in range(len(dataset)):
        _, _, name = dataset[i]
        name_to_idx[name] = i

    model = build_model_full(device)
    load_state_dict_compat(model, load_checkpoint(args.ckpt, map_location=device)["model"])

    rows = []
    for name in args.names:
        if name not in name_to_idx:
            print(f"skip missing sample {name}")
            continue
        image, mask, _ = dataset[name_to_idx[name]]
        vis = model.forward_collect(image.unsqueeze(0).to(device))
        rows.append(
            {
                "name": name,
                "input": np.transpose(to_np(image), (1, 2, 0)).clip(0, 1),
                "gt": to_np(mask)[0],
                "top_s32": to_np(vis["top_s32"])[0, 0],
                "decode3_s16": to_np(vis["decode3_s16"])[0, 0],
                "decode2_s8": to_np(vis["decode2_s8"])[0, 0],
                "decode1_s4": to_np(vis["decode1_s4"])[0, 0],
                "decode0_s2": to_np(vis["decode0_s2"])[0, 0],
                "pred": to_np(vis["pred"])[0, 0],
            }
        )

    if rows:
        render_grid(rows, out_dir / "c3net_stages_grid.png")
        print(f"saved {out_dir / 'c3net_stages_grid.png'}")


if __name__ == "__main__":
    main()
