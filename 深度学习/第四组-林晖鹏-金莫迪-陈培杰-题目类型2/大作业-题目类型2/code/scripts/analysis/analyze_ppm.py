"""Analyze whether PPM helps: compare full C3Net (with PPM) vs the leave-one-out
model without PPM, per image, and render the cases where PPM helps / hurts most.
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


def max_f(prob, mask):
    p = prob.flatten(); m = (mask.flatten() > 0.5).float()
    best = 0.0
    for t in torch.linspace(0, 1, 50):
        pb = (p >= t).float()
        tp = (pb * m).sum()
        prec = tp / (pb.sum() + 1e-8); rec = tp / (m.sum() + 1e-8)
        f = 1.3 * prec * rec / (0.3 * prec + rec + 1e-8)
        best = max(best, f.item())
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full-ckpt", required=True)
    ap.add_argument("--noppm-ckpt", required=True)
    ap.add_argument("--out", default="runs/ppm_analysis")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--topk", type=int, default=6)
    args = ap.parse_args()
    dev = args.device if torch.cuda.is_available() else "cpu"
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    ds = ECSSDDataset("data/ECSSD", split="test", image_size=352, augment=False,
                      split_file="splits/trainval_seed_42.json")

    full = build_model("c3net_r18", pretrained=False, loss_type="bce").to(dev).eval()
    load_state_dict_compat(full, load_checkpoint(args.full_ckpt, map_location=dev)["model"])
    noppm = build_model("c3net_r18", pretrained=False, use_context=False, loss_type="bce").to(dev).eval()
    load_state_dict_compat(noppm, load_checkpoint(args.noppm_ckpt, map_location=dev)["model"])

    rows = []
    with torch.no_grad():
        for i in range(len(ds)):
            img, mask, name = ds[i]
            x = img.unsqueeze(0).to(dev)
            pf = torch.sigmoid(full(x)["pred"])[0, 0].cpu()
            pn = torch.sigmoid(noppm(x)["pred"])[0, 0].cpu()
            ff = max_f(pf, mask[0]); fn = max_f(pn, mask[0])
            rows.append((name, ff, fn, ff - fn, img, mask, pf, pn))

    deltas = np.array([r[3] for r in rows])
    helped = (deltas > 0.01).sum(); hurt = (deltas < -0.01).sum(); neutral = len(rows) - helped - hurt
    print(f"PPM helps: {helped}/{len(rows)}  hurts: {hurt}/{len(rows)}  neutral(|d|<=0.01): {neutral}")
    print(f"mean delta(full-noPPM) maxF = {deltas.mean():+.4f}")

    rows.sort(key=lambda r: r[3])
    cases = rows[-args.topk:][::-1] + rows[:args.topk]  # most-helped then most-hurt
    panels = ["input", "GT", "with PPM", "no PPM"]
    for tag, group in [("ppm_helps", rows[-args.topk:][::-1]), ("ppm_hurts", rows[:args.topk])]:
        fig, axes = plt.subplots(len(group), 4, figsize=(9, 2.2 * len(group)))
        for r_i, (name, ff, fn, d, img, mask, pf, pn) in enumerate(group):
            data = [np.transpose(img.numpy(), (1, 2, 0)).clip(0, 1), mask[0].numpy(), pf.numpy(), pn.numpy()]
            for c_i, (arr, ttl) in enumerate(zip(data, panels)):
                ax = axes[r_i, c_i] if len(group) > 1 else axes[c_i]
                ax.imshow(arr, cmap=None if c_i == 0 else "gray", vmin=0, vmax=1) if c_i else ax.imshow(arr)
                ax.imshow(arr, cmap="gray", vmin=0, vmax=1) if c_i else None
                if r_i == 0:
                    ax.set_title(ttl, fontsize=10)
                ax.axis("off")
            (axes[r_i, 0] if len(group) > 1 else axes[0]).set_ylabel(
                f"{name}\nd={d:+.3f}", fontsize=8, rotation=0, labelpad=28, va="center")
        fig.suptitle(f"PPM analysis: {tag}  (full {ff:.3f} vs noPPM {fn:.3f})", fontsize=11)
        fig.tight_layout()
        fig.savefig(out / f"{tag}.png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        print("saved", out / f"{tag}.png")


if __name__ == "__main__":
    main()
