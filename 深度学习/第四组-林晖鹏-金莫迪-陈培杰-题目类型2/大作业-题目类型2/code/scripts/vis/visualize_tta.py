"""Render TTA visualization assets for PPT/report use.

Outputs:
  - a compact grid:
      input | GT | single | disagreement | fused
  - per-sample panels saved into split folders

Sample selection is automatic:
  - one "helps" case with large IoU gain from TTA
  - one "little_gain" case with near-zero IoU gain
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from datasets.ecssd import ECSSDDataset
from engine.trainer import resolve_prediction_tensor
from model import build_model
from utils.io import load_checkpoint, load_state_dict_compat
from utils.metrics import compute_iou


def build_c3net(device):
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


def to_np(tensor):
    return tensor.detach().cpu().float().numpy()


def norm01(arr):
    arr = np.asarray(arr, dtype=np.float32)
    lo = float(arr.min())
    hi = float(arr.max())
    if hi - lo < 1e-8:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def _tta_view_probs(model, images, scales=(0.75, 1.0, 1.25)):
    height, width = images.shape[-2:]
    views = []
    labels = []
    for scale in scales:
        if scale == 1.0:
            scaled = images
        else:
            new_h = max(32, int(round(height * scale / 32)) * 32)
            new_w = max(32, int(round(width * scale / 32)) * 32)
            scaled = F.interpolate(images, size=(new_h, new_w), mode="bilinear", align_corners=False)
        for flip in (False, True):
            view = torch.flip(scaled, dims=[-1]) if flip else scaled
            prob = torch.sigmoid(resolve_prediction_tensor(model(view)))
            if flip:
                prob = torch.flip(prob, dims=[-1])
            if prob.shape[-2:] != (height, width):
                prob = F.interpolate(prob, size=(height, width), mode="bilinear", align_corners=False)
            views.append(prob)
            labels.append(f"s{scale:g}" + ("_flip" if flip else ""))
    return labels, views


@torch.no_grad()
def collect_rows(model, dataset, device, scales):
    rows = []
    for idx in range(len(dataset)):
        image, mask, name = dataset[idx]
        x = image.unsqueeze(0).to(device)
        y = mask.unsqueeze(0).to(device)

        single = torch.sigmoid(resolve_prediction_tensor(model(x)))
        view_labels, views = _tta_view_probs(model, x, scales=scales)
        fused = torch.stack(views, dim=0).mean(dim=0)
        disagreement = torch.stack(views, dim=0).std(dim=0, unbiased=False)
        delta = torch.abs(fused - single)

        rows.append(
            {
                "name": name,
                "input": np.transpose(to_np(image), (1, 2, 0)).clip(0, 1),
                "gt": to_np(mask)[0],
                "single": to_np(single)[0, 0],
                "fused": to_np(fused)[0, 0],
                "disagreement": to_np(disagreement)[0, 0],
                "delta": to_np(delta)[0, 0],
                "single_iou": compute_iou(single, y),
                "fused_iou": compute_iou(fused, y),
                "view_labels": view_labels,
            }
        )
    for row in rows:
        row["delta_iou"] = row["fused_iou"] - row["single_iou"]
    return rows


def choose_samples(rows):
    helps = sorted(rows, key=lambda r: (r["delta_iou"], r["fused_iou"]), reverse=True)
    little = sorted(rows, key=lambda r: (abs(r["delta_iou"]), -r["fused_iou"]))

    helps_row = helps[0]
    little_row = next((r for r in little if r["name"] != helps_row["name"]), little[0])

    return [
        ("tta_helps", helps_row),
        ("tta_little_gain", little_row),
    ]


def save_panel(out_dir, sample_name, panel_name, arr, cmap=None):
    fig, ax = plt.subplots(1, 1, figsize=(2.8, 2.8))
    if cmap is None:
        ax.imshow(arr)
    else:
        ax.imshow(norm01(arr), cmap=cmap, vmin=0, vmax=1)
    ax.axis("off")
    fig.tight_layout(pad=0)
    fig.savefig(out_dir / f"{sample_name}_{panel_name}.png", dpi=180, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def save_grid(rows, out_path):
    cols = ["input", "GT", "single", "disagreement", "fused"]
    fig, axes = plt.subplots(len(rows), len(cols), figsize=(len(cols) * 2.2, len(rows) * 2.4))
    if len(rows) == 1:
        axes = np.expand_dims(axes, 0)
    for r, (tag, row) in enumerate(rows):
        items = [
            (row["input"], None),
            (row["gt"], "gray"),
            (row["single"], "gray"),
            (row["disagreement"], "inferno"),
            (row["fused"], "gray"),
        ]
        ylabel = f"{tag}\n{row['name']}\nΔIoU={row['delta_iou']:+.4f}"
        for c, (arr, cmap) in enumerate(items):
            ax = axes[r, c]
            if cmap is None:
                ax.imshow(arr)
            else:
                ax.imshow(norm01(arr), cmap=cmap, vmin=0, vmax=1)
            if r == 0:
                ax.set_title(cols[c], fontsize=9)
            if c == 0:
                ax.set_ylabel(ylabel, fontsize=9)
            ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def save_selection(rows, out_path):
    lines = ["tag,name,single_iou,fused_iou,delta_iou"]
    for tag, row in rows:
        lines.append(
            f"{tag},{row['name']},{row['single_iou']:.6f},{row['fused_iou']:.6f},{row['delta_iou']:.6f}"
        )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/ECSSD")
    parser.add_argument("--split-file", default="splits/trainval_seed_42.json")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--image-size", type=int, default=352)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out", default="runs/c3net_ablation/tta_vis_seed42")
    parser.add_argument("--scales", nargs="*", type=float, default=[0.75, 1.0, 1.25])
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
    model = build_c3net(device)
    ckpt = load_checkpoint(args.ckpt, map_location=device)
    load_state_dict_compat(model, ckpt["model"])

    rows = collect_rows(model, dataset, device, scales=tuple(args.scales))
    selected = choose_samples(rows)

    for tag, row in selected:
        sample_dir = out_dir / tag / row["name"]
        sample_dir.mkdir(parents=True, exist_ok=True)
        save_panel(sample_dir, row["name"], "input", row["input"], None)
        save_panel(sample_dir, row["name"], "gt", row["gt"], "gray")
        save_panel(sample_dir, row["name"], "single", row["single"], "gray")
        save_panel(sample_dir, row["name"], "disagreement", row["disagreement"], "inferno")
        save_panel(sample_dir, row["name"], "fused", row["fused"], "gray")
        save_panel(sample_dir, row["name"], "delta", row["delta"], "inferno")

    save_grid(selected, out_dir / "tta_grid.png")
    save_selection(selected, out_dir / "tta_selection.csv")
    print(f"saved {out_dir / 'tta_grid.png'}")
    print(f"saved {out_dir / 'tta_selection.csv'}")


if __name__ == "__main__":
    main()
