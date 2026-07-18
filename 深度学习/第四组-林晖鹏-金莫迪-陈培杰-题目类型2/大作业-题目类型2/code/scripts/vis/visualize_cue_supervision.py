"""Render C3Net cue supervision visualization for one or a few samples.

Panels:
  input | GT | side3 | side2 | side1 | edge | pred
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


def render(rows, out_path):
    cols = ["input", "GT", "side3", "side2", "side1", "edge", "pred"]
    fig, axes = plt.subplots(len(rows), len(cols), figsize=(len(cols) * 2.1, len(rows) * 2.2))
    if len(rows) == 1:
        axes = np.expand_dims(axes, 0)
    for r, row in enumerate(rows):
        items = [
            (row["input"], None),
            (row["gt"], "gray"),
            (row["side3"], "gray"),
            (row["side2"], "gray"),
            (row["side1"], "gray"),
            (row["edge"], "gray"),
            (row["pred"], "gray"),
        ]
        for c, (arr, cmap) in enumerate(items):
            ax = axes[r, c]
            if cmap is None:
                ax.imshow(arr)
            else:
                ax.imshow(arr, cmap=cmap, vmin=0, vmax=1)
            if r == 0:
                ax.set_title(cols[c], fontsize=9)
            if c == 0:
                ax.set_ylabel(row["name"], fontsize=9)
            ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def save_panel(out_dir, sample_name, panel_name, arr, cmap=None):
    fig, ax = plt.subplots(1, 1, figsize=(2.8, 2.8))
    if cmap is None:
        ax.imshow(arr)
    else:
        ax.imshow(arr, cmap=cmap, vmin=0, vmax=1)
    ax.axis("off")
    fig.tight_layout(pad=0)
    fig.savefig(out_dir / f"{sample_name}_{panel_name}.png", dpi=180, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/ECSSD")
    parser.add_argument("--split-file", default="splits/trainval_seed_42.json")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--names", nargs="*", default=["0303"])
    parser.add_argument("--image-size", type=int, default=352)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out", default="runs/c3net_ablation/cue_vis_seed42")
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
                "side3": to_np(vis["side3"])[0, 0],
                "side2": to_np(vis["side2"])[0, 0],
                "side1": to_np(vis["side1"])[0, 0],
                "edge": to_np(vis["edge"])[0, 0],
                "pred": to_np(vis["pred"])[0, 0],
            }
        )
        sample_dir = out_dir / name
        sample_dir.mkdir(parents=True, exist_ok=True)
        save_panel(sample_dir, name, "input", rows[-1]["input"], None)
        save_panel(sample_dir, name, "gt", rows[-1]["gt"], "gray")
        save_panel(sample_dir, name, "side3", rows[-1]["side3"], "gray")
        save_panel(sample_dir, name, "side2", rows[-1]["side2"], "gray")
        save_panel(sample_dir, name, "side1", rows[-1]["side1"], "gray")
        save_panel(sample_dir, name, "edge", rows[-1]["edge"], "gray")
        save_panel(sample_dir, name, "pred", rows[-1]["pred"], "gray")

    if rows:
        render(rows, out_dir / "cue_supervision_grid.png")
        print(f"saved {out_dir / 'cue_supervision_grid.png'}")


if __name__ == "__main__":
    main()
