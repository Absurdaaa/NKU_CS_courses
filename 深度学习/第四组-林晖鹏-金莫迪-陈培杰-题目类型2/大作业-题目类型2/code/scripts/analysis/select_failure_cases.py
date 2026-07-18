"""Select failure-case samples from per-sample metric CSVs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_csv(path):
    with open(path, newline="") as f:
        return {row["name"]: {"iou": float(row["iou"]), "mae": float(row["mae"])} for row in csv.DictReader(f)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ours-c3", required=True)
    parser.add_argument("--ours-ctd", required=True)
    parser.add_argument("--baseline-files", nargs="+", required=True)
    parser.add_argument("--topk", type=int, default=2)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    c3 = read_csv(args.ours_c3)
    ctd = read_csv(args.ours_ctd)
    baselines = {Path(p).stem: read_csv(p) for p in args.baseline_files}

    names = sorted(set(c3) & set(ctd))
    for d in baselines.values():
        names = [n for n in names if n in d]

    rows = []
    for name in names:
        our_best_iou = max(c3[name]["iou"], ctd[name]["iou"])
        our_best_mae = min(c3[name]["mae"], ctd[name]["mae"])
        best_base_name, best_base_iou = max(
            ((k, v[name]["iou"]) for k, v in baselines.items()),
            key=lambda x: x[1],
        )
        avg_all_iou = (
            c3[name]["iou"]
            + ctd[name]["iou"]
            + sum(v[name]["iou"] for v in baselines.values())
        ) / (2 + len(baselines))
        rows.append(
            {
                "name": name,
                "c3_iou": c3[name]["iou"],
                "ctd_iou": ctd[name]["iou"],
                "our_best_iou": our_best_iou,
                "our_best_mae": our_best_mae,
                "best_base_name": best_base_name,
                "best_base_iou": best_base_iou,
                "baseline_gap": best_base_iou - our_best_iou,
                "avg_all_iou": avg_all_iou,
            }
        )

    def pick_unique(candidates, used):
        picked = []
        for row in candidates:
            if row["name"] in used:
                continue
            picked.append(row)
            used.add(row["name"])
            if len(picked) >= args.topk:
                break
        return picked

    used = set()
    ours_fail = pick_unique(sorted(rows, key=lambda r: (r["our_best_iou"], -r["our_best_mae"])), used)
    baseline_better = pick_unique(sorted(rows, key=lambda r: r["baseline_gap"], reverse=True), used)
    all_hard = pick_unique(sorted(rows, key=lambda r: r["avg_all_iou"]), used)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "category",
                "name",
                "c3_iou",
                "ctd_iou",
                "our_best_iou",
                "our_best_mae",
                "best_base_name",
                "best_base_iou",
                "baseline_gap",
                "avg_all_iou",
            ],
        )
        writer.writeheader()
        for category, items in (
            ("ours_fail", ours_fail),
            ("baseline_better", baseline_better),
            ("all_hard", all_hard),
        ):
            for row in items:
                writer.writerow({"category": category, **row})
    print(f"saved {out_path}")
    for category, items in (("ours_fail", ours_fail), ("baseline_better", baseline_better), ("all_hard", all_hard)):
        print(f"== {category}")
        for row in items:
            print(
                row["name"],
                f"our_best={row['our_best_iou']:.4f}",
                f"best_base={row['best_base_name']}:{row['best_base_iou']:.4f}",
                f"gap={row['baseline_gap']:.4f}",
                f"avg_all={row['avg_all_iou']:.4f}",
            )


if __name__ == "__main__":
    main()
