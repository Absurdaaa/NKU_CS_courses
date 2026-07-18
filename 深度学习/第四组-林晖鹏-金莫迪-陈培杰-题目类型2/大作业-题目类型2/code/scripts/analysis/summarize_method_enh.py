#!/usr/bin/env python3
"""Summarize Wave-1 method-enhancement runs.

Reads runs/method_enh/{split}/{cfg}/{,duts/,omron/}test_metrics.json, prints the
seed-mean max-F per cfg on ECSSD-300 / DUTS-TE / DUT-OMRON, and the gain of each
enhancement over the fresh full_ref. Judge on the EXTERNAL sets (ECSSD is at ceiling).
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("runs/method_enh")
CFGS = ["full_ref", "m1_skip", "m1_d3", "m1_both", "m2_sup02", "m2_sup05", "m5_fixed",
        "m3_learnsurround", "m4_edgegate", "combo_m1m2"]
DSETS = [("ecssd", ""), ("duts", "duts"), ("omron", "omron")]
METRIC = "max_f_measure"


def load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def fmt(v):
    return f"{v:.4f}" if v is not None else "  -   "


def collect():
    # data[ds][cfg] = [values across seeds]
    data = {ds: defaultdict(list) for ds, _ in DSETS}
    if not ROOT.exists():
        return data
    for split_dir in sorted(ROOT.glob("trainval_seed_*")):
        for cfg in CFGS:
            base = split_dir / cfg
            for ds, sub in DSETS:
                m = load((base / sub / "test_metrics.json") if sub else (base / "test_metrics.json"))
                if m and METRIC in m:
                    data[ds][cfg].append(m[METRIC])
    return data


def main():
    data = collect()
    print(f"{'cfg':>10} | {'ECSSD':>8} | {'DUTS-TE':>8} | {'OMRON':>8} || "
          f"{'dDUTS':>8} | {'dOMRON':>8}")
    print("-" * 66)
    ref = {ds: mean(data[ds]["full_ref"]) for ds, _ in DSETS}
    for cfg in CFGS:
        ec = mean(data["ecssd"][cfg]); du = mean(data["duts"][cfg]); om = mean(data["omron"][cfg])
        ddu = (du - ref["duts"]) if (du is not None and ref["duts"] is not None) else None
        dom = (om - ref["omron"]) if (om is not None and ref["omron"] is not None) else None
        tag = " (ref)" if cfg == "full_ref" else ""
        print(f"{cfg:>10} | {fmt(ec):>8} | {fmt(du):>8} | {fmt(om):>8} || "
              f"{('%+.4f'%ddu) if ddu is not None else '   -   ':>8} | "
              f"{('%+.4f'%dom) if dom is not None else '   -   ':>8}{tag}")
    print("\nWinner = enhancement with positive dDUTS AND dOMRON beyond ~0.004 noise.")


if __name__ == "__main__":
    main()
