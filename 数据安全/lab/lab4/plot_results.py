"""
plot_results.py — 用 client.py --csv 导出的数据生成可视化图表

用法:
  python3 plot_results.py [CSV文件...]

  不传参数时自动在当前目录寻找所有 .csv 文件并逐一生成图表。
"""

import sys
import glob
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

M = 128  # 叶子容量阈值


def plot_one(csv_path):
    df = pd.read_csv(csv_path)
    base = os.path.splitext(csv_path)[0]
    n = len(df)
    recode_df = df[df["is_recode"] == 1]
    recode_count = len(recode_df)

    # 推断 rebalance 边界（每个 128 的整数倍）
    rebalance_boundaries = list(range(M, n + 1, M))

    fig = plt.figure(figsize=(14, 12))

    # ---------- 子图1: encoding 散点 + recode 标记 + rebalance 边界 ----------
    ax1 = fig.add_subplot(3, 1, 1)
    ax1.scatter(df["round"], df["final_encoding"], s=1, alpha=0.5, color="steelblue")
    for r in recode_df["round"]:
        ax1.axvline(x=r, color="red", alpha=0.3, linewidth=0.6)
    for b in rebalance_boundaries:
        ax1.axvline(x=b, color="green", alpha=0.4, linestyle="--", linewidth=0.7)
    ax1.set_ylabel("encoding")
    ax1.set_title(f"{base}  (n={n}, recode={recode_count}, green=rebalance boundary, red=recode)")
    ax1.ticklabel_format(style="plain", axis="y")

    # ---------- 子图2: 每次 recode 的 update 行数 ----------
    ax2 = fig.add_subplot(3, 1, 2, sharex=ax1)
    if len(recode_df) > 0:
        ax2.vlines(recode_df["round"], 0, recode_df["updated_rows"],
                   colors="red", alpha=0.7, linewidths=1.2)
        ax2.scatter(recode_df["round"], recode_df["updated_rows"],
                    s=8, color="red", alpha=0.9)
    ax2.set_ylabel("rows updated")
    ax2.set_title("update rows per recode event")

    # ---------- 子图3: recode 累计次数 ----------
    ax3 = fig.add_subplot(3, 1, 3, sharex=ax1)
    df["is_recode_cumsum"] = df["is_recode"].cumsum()
    ax3.plot(df["round"], df["is_recode_cumsum"], color="red", linewidth=1)
    for b in rebalance_boundaries:
        ax3.axvline(x=b, color="green", alpha=0.4, linestyle="--", linewidth=0.7)
    ax3.set_xlabel("insertion round")
    ax3.set_ylabel("cumulative recode count")
    ax3.set_title("cumulative recode events over time")

    plt.tight_layout()
    out_path = base + ".png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {out_path}  (n={n}, recode={recode_count})")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = sorted(glob.glob("*.csv"))

    if not files:
        print("no CSV files found, pass path as argument or place them in current directory")
        sys.exit(1)

    for f in files:
        plot_one(f)
