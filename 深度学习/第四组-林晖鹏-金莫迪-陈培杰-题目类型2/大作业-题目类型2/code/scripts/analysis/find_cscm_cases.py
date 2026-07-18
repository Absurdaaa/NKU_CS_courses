"""Find ECSSD test samples where CSCM gives the clearest gain.

Compare full C3Net (`b4_full`) against the closest no-CSCM counterpart
(`b3_cue`: context + cue, but no CSCM) and rank samples by binary IoU gain.
"""

import argparse
import csv
from pathlib import Path

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


def build_model_ref(device):
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


def iou01(pred, mask, thr=0.5):
    pred = (pred >= thr).float()
    mask = (mask >= 0.5).float()
    inter = (pred * mask).sum().item()
    union = ((pred + mask) > 0).float().sum().item()
    return inter / max(union, 1.0)


def mae(pred, mask):
    return (pred - mask).abs().mean().item()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", default="data/ECSSD")
    parser.add_argument("--split-file", default="splits/trainval_seed_42.json")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--full-ckpt", required=True)
    parser.add_argument("--ref-ckpt", required=True)
    parser.add_argument("--image-size", type=int, default=352)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--out", default="runs/c3net_ablation/cscm_case_ranking.csv")
    parser.add_argument("--topk", type=int, default=20)
    args = parser.parse_args()

    device = args.device if torch.cuda.is_available() else "cpu"
    dataset = ECSSDDataset(
        args.data_root,
        split=args.split,
        image_size=args.image_size,
        augment=False,
        split_file=args.split_file,
    )

    full = build_model_full(device)
    ref = build_model_ref(device)
    load_state_dict_compat(full, load_checkpoint(args.full_ckpt, map_location=device)["model"])
    load_state_dict_compat(ref, load_checkpoint(args.ref_ckpt, map_location=device)["model"])

    rows = []
    for idx in range(len(dataset)):
        image, mask, name = dataset[idx]
        x = image.unsqueeze(0).to(device)
        gt = mask.unsqueeze(0).to(device)
        with torch.no_grad():
            p_full = torch.sigmoid(full(x)["pred"])
            p_ref = torch.sigmoid(ref(x)["pred"])
        full_iou = iou01(p_full, gt)
        ref_iou = iou01(p_ref, gt)
        full_mae = mae(p_full, gt)
        ref_mae = mae(p_ref, gt)
        rows.append(
            {
                "name": name,
                "full_iou": full_iou,
                "ref_iou": ref_iou,
                "delta_iou": full_iou - ref_iou,
                "full_mae": full_mae,
                "ref_mae": ref_mae,
                "delta_mae": ref_mae - full_mae,
            }
        )

    rows.sort(key=lambda r: (r["delta_iou"], r["delta_mae"]), reverse=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["name", "full_iou", "ref_iou", "delta_iou", "full_mae", "ref_mae", "delta_mae"],
        )
        writer.writeheader()
        writer.writerows(rows)

    for row in rows[: args.topk]:
        print(
            f"{row['name']}, delta_iou={row['delta_iou']:.4f}, "
            f"full_iou={row['full_iou']:.4f}, ref_iou={row['ref_iou']:.4f}, "
            f"delta_mae={row['delta_mae']:.4f}"
        )
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
