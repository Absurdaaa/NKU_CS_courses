"""Render CSCM insight visualizations for report / PPT use.

Panels per sample:
  input | GT | optional no-CSCM pred | before CSCM (s2) | after CSCM (s2) |
  delta | attention overlay | final pred

The goal is not debugging, but visually showing the module's effect:
CSCM suppresses distractors and sharpens salient regions / boundaries.
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


def build_ref(device):
    model = build_model(
        "c3net_r18",
        pretrained=False,
        use_context=True,
        use_edge=True,
        use_deep_supervision=True,
        use_cscm=False,
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


def heat_overlay(image, heat, alpha=0.60):
    cmap = plt.get_cmap("jet")
    color = cmap(norm01(heat))[..., :3]
    return np.clip((1 - alpha) * image + alpha * color, 0, 1)


def render_sample(out_path, name, img_np, gt_np, before, after, delta, attn, pred, ref_pred=None):
    panels = [
        ("input", img_np, None),
        ("GT", gt_np, "gray"),
    ]
    if ref_pred is not None:
        panels.append(("no_cscm", ref_pred, "gray"))
    panels.extend([
        ("before", before, "magma"),
        ("after", after, "magma"),
        ("delta", delta, "inferno"),
        ("attn", heat_overlay(img_np, attn), None),
        ("pred", pred, "gray"),
    ])
    fig, axes = plt.subplots(1, len(panels), figsize=(len(panels) * 2.2, 2.8))
    for ax, (title, arr, cmap) in zip(axes, panels):
        if cmap is None:
            ax.imshow(arr)
        else:
            ax.imshow(norm01(arr), cmap=cmap, vmin=0, vmax=1)
        ax.set_title(title, fontsize=9)
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path / f"{name}.png", dpi=140, bbox_inches="tight")
    plt.close(fig)


def render_grid(out_path, rows):
    use_ref = rows and rows[0].get("ref") is not None
    cols = ["input", "GT"] + (["no_cscm"] if use_ref else []) + ["before", "after", "delta", "attn", "pred"]
    fig, axes = plt.subplots(len(rows), len(cols), figsize=(len(cols) * 2.1, len(rows) * 2.2))
    if len(rows) == 1:
        axes = np.expand_dims(axes, 0)
    for r, row in enumerate(rows):
        name = row["name"]
        items = [
            (row["input"], None),
            (row["gt"], "gray"),
        ]
        if use_ref:
            items.append((row["ref"], "gray"))
        items.extend([
            (row["before"], "magma"),
            (row["after"], "magma"),
            (row["delta"], "inferno"),
            (heat_overlay(row["input"], row["attn"]), None),
            (row["pred"], "gray"),
        ])
        for c, (arr, cmap) in enumerate(items):
            ax = axes[r, c]
            if cmap is None:
                ax.imshow(arr)
            else:
                ax.imshow(norm01(arr), cmap=cmap, vmin=0, vmax=1)
            if r == 0:
                ax.set_title(cols[c], fontsize=9)
            if c == 0:
                ax.set_ylabel(name, fontsize=9)
            ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path / "cscm_insight_grid.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/ECSSD")
    parser.add_argument("--split-file", default="splits/trainval_seed_42.json")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--ref-ckpt", default=None)
    parser.add_argument("--names", nargs="*", default=["0046", "0573", "0670"])
    parser.add_argument("--image-size", type=int, default=352)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out", default="runs/c3net_ablation/cscm_insight")
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

    model = build_full(device)
    load_state_dict_compat(model, load_checkpoint(args.ckpt, map_location=device)["model"])
    ref_model = None
    if args.ref_ckpt:
        ref_model = build_ref(device)
        load_state_dict_compat(ref_model, load_checkpoint(args.ref_ckpt, map_location=device)["model"])

    rows = []
    for name in args.names:
        if name not in name_to_idx:
            print(f"skip missing sample {name}")
            continue
        image, mask, _ = dataset[name_to_idx[name]]
        x = image.unsqueeze(0).to(device)
        vis = model.forward_collect(x)

        img_np = np.transpose(to_np(image), (1, 2, 0)).clip(0, 1)
        gt_np = to_np(mask)[0]
        before = to_np(vis["cscm_before_s2"])[0, 0]
        after = to_np(vis["cscm_after_s2"])[0, 0]
        delta = to_np(vis["cscm_delta_s2"])[0, 0]
        attn = to_np(vis["contrast_s2"])[0, 0]
        pred = to_np(vis["pred"])[0, 0]
        ref_pred = None
        if ref_model is not None:
            ref_pred = to_np(torch.sigmoid(ref_model(x)["pred"]))[0, 0]

        render_sample(out_dir, name, img_np, gt_np, before, after, delta, attn, pred, ref_pred=ref_pred)
        rows.append(
            {
                "name": name,
                "input": img_np,
                "gt": gt_np,
                "ref": ref_pred,
                "before": before,
                "after": after,
                "delta": delta,
                "attn": attn,
                "pred": pred,
            }
        )
        print(f"saved {out_dir / (name + '.png')}")

    if rows:
        render_grid(out_dir, rows)
        print(f"saved {out_dir / 'cscm_insight_grid.png'}")


if __name__ == "__main__":
    main()
