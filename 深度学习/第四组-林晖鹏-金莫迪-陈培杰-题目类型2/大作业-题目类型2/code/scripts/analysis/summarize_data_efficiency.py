#!/usr/bin/env python3
"""Summarize the V1 data-efficiency runs into a table + gain-vs-size view.

Reads runs/data_efficiency/seed{SEED}/{cfg}_n{SIZE}/test_metrics.json (ECSSD-300)
and .../duts/test_metrics.json (DUTS-TE external), prints per-(cfg,size) seed-mean
max-F for both datasets, plus the gain of cscm/full over base at each size.
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path("runs/data_efficiency")
CFGS = ["base", "cscm", "cscmfix", "full"]
SIZES = [100, 200, 400, 600]
METRIC = "max_f_measure"


def load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def collect():
    # data[dataset][cfg][size] = list of metric values across seeds
    data = {"ecssd": defaultdict(lambda: defaultdict(list)),
            "duts": defaultdict(lambda: defaultdict(list))}
    if not ROOT.exists():
        return data
    for seed_dir in sorted(ROOT.glob("seed*")):
        for cfg in CFGS:
            for size in SIZES:
                out = seed_dir / f"{cfg}_n{size}"
                m_ec = load(out / "test_metrics.json")
                m_du = load(out / "duts" / "test_metrics.json")
                if m_ec and METRIC in m_ec:
                    data["ecssd"][cfg][size].append(m_ec[METRIC])
                if m_du and METRIC in m_du:
                    data["duts"][cfg][size].append(m_du[METRIC])
    return data


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def fmt(v):
    return f"{v:.4f}" if v is not None else "  -   "


def table(data, dataset):
    others = [c for c in CFGS if c != "base"]
    print(f"\n=== {dataset.upper()} max-F (seed-mean) ===")
    header = f"{'size':>5} | " + " | ".join(f"{c:>8}" for c in CFGS) + " || " + \
             " | ".join(f"{c+'-base':>11}" for c in others)
    print(header)
    print("-" * len(header))
    for size in SIZES:
        vals = {c: mean(data[dataset][c][size]) for c in CFGS}
        b = vals["base"]
        row = f"{size:>5} | " + " | ".join(f"{fmt(vals[c]):>8}" for c in CFGS) + " || "
        gains = []
        for c in others:
            g = (vals[c] - b) if (b is not None and vals[c] is not None) else None
            gains.append(f"{('%+.4f'%g) if g is not None else '   -   ':>11}")
        print(row + " | ".join(gains))
    print("H1: cscm-base / full-base should GROW as size shrinks.")
    print("H2: cscmfix-base > 0 (parameter-free prior also helps).")


def main():
    data = collect()
    for ds in ("ecssd", "duts"):
        table(data, ds)
    # completeness
    done = sum(len(data["ecssd"][c][s]) for c in CFGS for s in SIZES)
    print(f"\nECSSD cells filled: {done}/{len(CFGS)*len(SIZES)*2} (cfg*size*seed)")


if __name__ == "__main__":
    main()
