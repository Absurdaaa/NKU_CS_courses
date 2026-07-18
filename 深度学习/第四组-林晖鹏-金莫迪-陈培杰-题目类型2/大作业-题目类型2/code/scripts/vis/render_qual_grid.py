"""Render a 3 x 11 qualitative comparison grid for ECSSD samples.

Layout:
    Input | GT | R18 | PoolNet | PFA | EGNet | SINet | DSS | F3Net | C3Net | CTD

This script uses local checkpoints already synced under results/remote_sync/checkpoints
and a small local sample pack under results/remote_sync/qual_samples.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F

from datasets.transforms import build_image_transform, preprocess_sample
from engine.trainer import resolve_prediction_tensor
from model import build_model
from utils.io import load_checkpoint, load_state_dict_compat


MODEL_SPECS = [
    {
        "label": "R18",
        "name": "resnet18",
        "ckpt": "results/remote_sync/checkpoints/serverA/resnet18_baseline_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    {
        "label": "PoolNet",
        "name": "poolnet_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/poolnet_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    {
        "label": "PFA",
        "name": "pfa_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/pfa_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    {
        "label": "EGNet",
        "name": "egnet_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/egnet_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    {
        "label": "SINet",
        "name": "sinet_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/sinet_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    {
        "label": "DSS",
        "name": "dss_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/dss_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    {
        "label": "F3Net",
        "name": "f3net_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/f3net_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    {
        "label": "C3Net",
        "name": "c3net_r18",
        "ckpt": "results/remote_sync/checkpoints/serverA/c3net_b4_full_seed42.pt",
        "kwargs": {"pretrained": False, "loss_type": "bce"},
    },
    {
        "label": "CTD",
        "name": "ctdnet_r18",
        "ckpt": "results/remote_sync/checkpoints/serverA/ctd_sem_seed42.pt",
        "kwargs": {"pretrained": False, "use_boundary": False, "loss_type": "bce"},
    },
]


def load_model(spec: dict, device: str):
    model = build_model(spec["name"], **spec["kwargs"]).to(device).eval()
    payload = load_checkpoint(spec["ckpt"], map_location=device)
    load_state_dict_compat(model, payload["model"])
    return model


def load_sample(image_path: Path, mask_path: Path, image_size: int):
    image = Image.open(image_path).convert("RGB")
    mask = Image.open(mask_path).convert("L")
    proc_image, proc_mask = preprocess_sample(image, mask, image_size=image_size, train=False)
    image_np = np.asarray(proc_image).astype(np.float32) / 255.0
    mask_np = np.asarray(proc_mask).astype(np.float32) / 255.0
    image_tensor = build_image_transform(image_size)(proc_image).unsqueeze(0)
    return image_np, mask_np, image_tensor


def predict(model, image_tensor: torch.Tensor, device: str):
    with torch.no_grad():
        pred = torch.sigmoid(resolve_prediction_tensor(model(image_tensor.to(device))))
        pred = F.interpolate(pred, size=image_tensor.shape[-2:], mode="bilinear", align_corners=False)
    return pred[0, 0].cpu().numpy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--samples",
        nargs="+",
        default=["0046", "0573", "0670"],
        help="Sample stems to render.",
    )
    parser.add_argument("--image-dir", default="results/remote_sync/qual_samples/images")
    parser.add_argument("--mask-dir", default="results/remote_sync/qual_samples/masks")
    parser.add_argument("--image-size", type=int, default=352)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--out", default="docs/figures/qualitative_grid_seed42.png")
    args = parser.parse_args()

    device = args.device if args.device.startswith("cuda") and torch.cuda.is_available() else "cpu"
    image_dir = Path(args.image_dir)
    mask_dir = Path(args.mask_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    models = [(spec["label"], load_model(spec, device)) for spec in MODEL_SPECS]
    headers = ["Input", "GT"] + [label for label, _model in models]
    rows = []

    for stem in args.samples:
        image_path = image_dir / f"{stem}.jpg"
        mask_path = mask_dir / f"{stem}.png"
        image_np, mask_np, image_tensor = load_sample(image_path, mask_path, args.image_size)
        row = [image_np, mask_np]
        for _label, model in models:
            row.append(predict(model, image_tensor, device))
        rows.append(row)

    n_rows = len(rows)
    n_cols = len(headers)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(1.9 * n_cols, 1.9 * n_rows))
    if n_rows == 1:
        axes = np.expand_dims(axes, axis=0)

    for r, row in enumerate(rows):
        for c, arr in enumerate(row):
            ax = axes[r, c]
            if c == 0:
                ax.imshow(arr)
            else:
                ax.imshow(arr, cmap="gray", vmin=0, vmax=1)
            if r == 0:
                ax.set_title(headers[c], fontsize=10)
            ax.axis("off")

    fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.01, wspace=0.03, hspace=0.08)
    fig.savefig(out_path, dpi=180, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
