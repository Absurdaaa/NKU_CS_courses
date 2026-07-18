"""Render failure-case analysis grid from selected samples."""

from __future__ import annotations

import argparse
import csv
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


MODEL_SPECS = {
    "resnet18": {
        "label": "R18",
        "name": "resnet18",
        "ckpt": "results/remote_sync/checkpoints/serverA/resnet18_baseline_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    "poolnet_r18": {
        "label": "PoolNet",
        "name": "poolnet_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/poolnet_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    "pfa_r18": {
        "label": "PFA",
        "name": "pfa_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/pfa_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    "egnet_r18": {
        "label": "EGNet",
        "name": "egnet_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/egnet_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    "sinet_r18": {
        "label": "SINet",
        "name": "sinet_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/sinet_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    "dss_r18": {
        "label": "DSS",
        "name": "dss_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/dss_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    "f3net_r18": {
        "label": "F3Net",
        "name": "f3net_r18",
        "ckpt": "results/remote_sync/checkpoints/serverB/f3net_r18_bestlr_seed42.pt",
        "kwargs": {"pretrained": False},
    },
    "c3net_r18": {
        "label": "C3Net",
        "name": "c3net_r18",
        "ckpt": "results/remote_sync/checkpoints/serverA/c3net_b4_full_seed42.pt",
        "kwargs": {"pretrained": False, "loss_type": "bce"},
    },
    "ctdnet_r18": {
        "label": "CTD",
        "name": "ctdnet_r18",
        "ckpt": "results/remote_sync/checkpoints/serverA/ctd_sem_seed42.pt",
        "kwargs": {"pretrained": False, "use_boundary": False, "loss_type": "bce"},
    },
}

CAT_LABELS = {
    "ours_fail": "Ours Fail",
    "baseline_better": "Baseline Better",
    "all_hard": "All Hard",
}


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


def error_map(pred, gt):
    return np.abs(pred - gt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-csv", default="results/remote_sync/failure_cases/failure_case_selection_seed42.csv")
    parser.add_argument("--image-dir", default="results/remote_sync/failure_cases/images")
    parser.add_argument("--mask-dir", default="results/remote_sync/failure_cases/masks")
    parser.add_argument("--image-size", type=int, default=352)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--out", default="docs/figures/failure_cases_seed42.png")
    args = parser.parse_args()

    device = args.device if args.device.startswith("cuda") and torch.cuda.is_available() else "cpu"
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows_meta = []
    with open(args.selection_csv, newline="") as f:
        for row in csv.DictReader(f):
            rows_meta.append(row)

    needed = {"c3net_r18", "ctdnet_r18"}
    for row in rows_meta:
        needed.add(row["best_base_name"].replace("_seed42_samples", ""))
    models = {name: load_model(MODEL_SPECS[name], device) for name in sorted(needed)}

    headers = ["Input", "GT", "Best baseline", "C3Net", "CTD", "Error(best ours)"]
    fig, axes = plt.subplots(len(rows_meta), len(headers), figsize=(2.0 * len(headers), 2.0 * len(rows_meta)))
    if len(rows_meta) == 1:
        axes = np.expand_dims(axes, axis=0)

    for r, row in enumerate(rows_meta):
        name = row["name"]
        base_key = row["best_base_name"].replace("_seed42_samples", "")
        image_path = Path(args.image_dir) / f"{name}.jpg"
        mask_path = Path(args.mask_dir) / f"{name}.png"
        image_np, mask_np, image_tensor = load_sample(image_path, mask_path, args.image_size)
        base_pred = predict(models[base_key], image_tensor, device)
        c3_pred = predict(models["c3net_r18"], image_tensor, device)
        ctd_pred = predict(models["ctdnet_r18"], image_tensor, device)
        best_ours = c3_pred if float(row["c3_iou"]) >= float(row["ctd_iou"]) else ctd_pred
        err = error_map(best_ours, mask_np)

        panels = [image_np, mask_np, base_pred, c3_pred, ctd_pred, err]
        cmaps = [None, "gray", "gray", "gray", "gray", "inferno"]
        for c, (arr, cmap) in enumerate(zip(panels, cmaps)):
            ax = axes[r, c]
            if cmap is None:
                ax.imshow(arr)
            else:
                ax.imshow(arr, cmap=cmap, vmin=0, vmax=1)
            if r == 0:
                title = headers[c]
                if c == 2:
                    title = f"{headers[c]}\n({MODEL_SPECS[base_key]['label']})"
                ax.set_title(title, fontsize=9)
            if c == 0:
                ax.set_ylabel(f"{CAT_LABELS.get(row['category'], row['category'])}\n{name}", fontsize=9)
            ax.axis("off")

    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
