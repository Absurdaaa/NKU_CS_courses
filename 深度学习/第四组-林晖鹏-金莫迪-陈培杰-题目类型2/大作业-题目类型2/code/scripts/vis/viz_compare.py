"""Qualitative comparison: input / GT / base / C3Net / CTD-lite predictions."""

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


def load(model_name, kw, ckpt, dev):
    m = build_model(model_name, pretrained=False, **kw).to(dev).eval()
    load_state_dict_compat(m, load_checkpoint(ckpt, map_location=dev)["model"])
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base"); ap.add_argument("--c3net"); ap.add_argument("--ctd")
    ap.add_argument("--out", default="runs/viz_compare"); ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--num", type=int, default=8)
    a = ap.parse_args()
    dev = a.device if torch.cuda.is_available() else "cpu"
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ds = ECSSDDataset("data/ECSSD", split="test", image_size=352, augment=False,
                      split_file="splits/trainval_seed_42.json")
    base = load("c3net_r18", dict(use_context=False, use_edge=False, use_deep_supervision=False, use_cscm=False, loss_type="bce"), a.base, dev)
    c3 = load("c3net_r18", dict(loss_type="bce"), a.c3net, dev)
    ctd = load("ctdnet_r18", dict(use_boundary=False, loss_type="bce"), a.ctd, dev)
    n = min(a.num, len(ds))
    idxs = [int(round(i * (len(ds) - 1) / max(n - 1, 1))) for i in range(n)]
    panels = ["input", "GT", "base", "C3Net", "CTD-lite"]
    fig, axes = plt.subplots(n, 5, figsize=(11, 2.1 * n))
    with torch.no_grad():
        for r, idx in enumerate(idxs):
            img, mask, name = ds[idx]
            x = img.unsqueeze(0).to(dev)
            pb = torch.sigmoid(base(x)["pred"])[0, 0].cpu().numpy()
            pc = torch.sigmoid(c3(x)["pred"])[0, 0].cpu().numpy()
            pt = torch.sigmoid(ctd(x)["pred"])[0, 0].cpu().numpy()
            data = [np.transpose(img.numpy(), (1, 2, 0)).clip(0, 1), mask[0].numpy(), pb, pc, pt]
            for c, (arr, ttl) in enumerate(zip(data, panels)):
                ax = axes[r, c]
                ax.imshow(arr) if c == 0 else ax.imshow(arr, cmap="gray", vmin=0, vmax=1)
                if r == 0:
                    ax.set_title(ttl, fontsize=11)
                ax.axis("off")
    fig.tight_layout()
    fig.savefig(out / "compare.png", dpi=120, bbox_inches="tight")
    print("saved", out / "compare.png")


if __name__ == "__main__":
    main()
