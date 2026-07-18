#!/usr/bin/env python3
"""V3/H3: compare base/cscm/full (n600, 3-seed) on ECSSD vs DUTS vs CAMO.

H3 prediction: on CAMO (camouflage = low center-surround contrast) the CSCM gain
over base should vanish or go negative, in contrast to its positive gain on the
high-contrast saliency sets (ECSSD / DUTS).
"""
import json
from collections import defaultdict

SEEDS = [42, 3407, 2026]
CFGS = ["base", "cscm", "full"]
DSETS = {"ECSSD": "test_metrics.json", "DUTS": "duts/test_metrics.json", "CAMO": "camo/test_metrics.json"}
ROOT = "runs/data_efficiency"
SIZES = [100, 600]


def load(p):
    try:
        return json.load(open(p))["max_f_measure"]
    except Exception:
        return None


def table(size):
    res = defaultdict(dict)
    for ds, sub in DSETS.items():
        for cfg in CFGS:
            vals = [load(f"{ROOT}/seed{s}/{cfg}_n{size}/{sub}") for s in SEEDS]
            vals = [v for v in vals if v is not None]
            res[ds][cfg] = sum(vals) / len(vals) if vals else None
    print(f"\n=== train n={size} (3-seed max-F) ===")
    hdr = "{:>7} | {:>7} | {:>7} | {:>7} || {:>10} | {:>10}".format(
        "dataset", "base", "cscm", "full", "cscm-base", "full-base")
    print(hdr); print("-" * len(hdr))
    for ds in DSETS:
        b, c, f = res[ds]["base"], res[ds]["cscm"], res[ds]["full"]
        gc = "{:+.4f}".format(c - b) if (b and c) else "  -  "
        gf = "{:+.4f}".format(f - b) if (b and f) else "  -  "
        print("{:>7} | {:.4f} | {:.4f} | {:.4f} || {:>10} | {:>10}".format(ds, b, c, f, gc, gf))


def main():
    for s in SIZES:
        table(s)
    print("\nH3: at n=100 (where CSCM helps on SOD) the cscm-base gain should be POSITIVE on "
          "ECSSD/DUTS but vanish/negative on CAMO (camouflage = low center-surround contrast).")


if __name__ == "__main__":
    main()
