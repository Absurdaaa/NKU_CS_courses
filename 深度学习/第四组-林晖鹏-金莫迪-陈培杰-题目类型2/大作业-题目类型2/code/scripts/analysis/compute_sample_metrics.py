"""Compute per-sample saliency metrics for a checkpoint on ECSSD test split."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import torch
import torch.nn.functional as F

from datasets.ecssd import ECSSDDataset
from engine.trainer import resolve_prediction_tensor
from model import build_model
from utils.io import load_checkpoint, load_state_dict_compat


def iou01(pred, mask, thr=0.5):
    pred = (pred >= thr).float()
    mask = (mask >= 0.5).float()
    inter = (pred * mask).sum().item()
    union = ((pred + mask) > 0).float().sum().item()
    return inter / max(union, 1.0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/ECSSD")
    parser.add_argument("--split-file", default="splits/trainval_seed_42.json")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--image-size", type=int, default=352)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out", required=True)
    parser.add_argument("--loss-type", default=None)
    parser.add_argument("--disable-c3net-cscm", action="store_true")
    parser.add_argument("--disable-ctd-boundary", action="store_true")
    args = parser.parse_args()

    device = args.device if torch.cuda.is_available() else "cpu"
    kwargs = {"pretrained": False}
    if args.model == "c3net_r18" and args.loss_type:
        kwargs["loss_type"] = args.loss_type
        if args.disable_c3net_cscm:
            kwargs["use_cscm"] = False
    if args.model == "ctdnet_r18":
        if args.loss_type:
            kwargs["loss_type"] = args.loss_type
        if args.disable_ctd_boundary:
            kwargs["use_boundary"] = False

    model = build_model(args.model, **kwargs).to(device).eval()
    payload = load_checkpoint(args.checkpoint, map_location=device)
    load_state_dict_compat(model, payload["model"])

    dataset = ECSSDDataset(
        args.data_root,
        split=args.split,
        image_size=args.image_size,
        augment=False,
        split_file=args.split_file,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "iou", "mae"])
        writer.writeheader()
        for idx in range(len(dataset)):
            image, mask, name = dataset[idx]
            x = image.unsqueeze(0).to(device)
            gt = mask.unsqueeze(0).to(device)
            with torch.no_grad():
                pred = torch.sigmoid(resolve_prediction_tensor(model(x)))
                pred = F.interpolate(pred, size=gt.shape[-2:], mode="bilinear", align_corners=False)
            writer.writerow(
                {
                    "name": name,
                    "iou": f"{iou01(pred, gt):.6f}",
                    "mae": f"{(pred - gt).abs().mean().item():.6f}",
                }
            )
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
